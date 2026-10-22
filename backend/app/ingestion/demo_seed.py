"""Semilla demo determinista: equipos, jugadores y torneo sintético de Liga MX.

SOLO para desarrollo, tests y validar el pipeline; NO son datos reales.
Genera N partidos terminados (histórico) + M partidos futuros, con stats
plausibles por posición y RNG con semilla fija.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)

DEMO_TEAMS = ["América", "Chivas", "Pumas", "Cruz Azul", "Tigres", "Monterrey"]
DEMO_POSITIONS = models.PlayerPosition.ALL
TEAM_SIZE = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}

rng = np.random.default_rng(42)


def seed_demo(db: Session, *, finished: int = 8, upcoming: int = 1) -> dict[str, int]:
    """Crea datos sintéticos reproduibles y devuelve conteos."""
    counts: dict[str, int] = {}
    delete_all(db)

    teams = _seed_teams(db)
    players = _seed_players(db, teams)

    base = datetime.now(UTC) - timedelta(days=finished * 4)
    matches: list[models.Match] = []
    # round-robin simple para histórico
    for i in range(finished):
        home = teams[i % len(teams)]
        away = teams[(i + 1) % len(teams)]
        kickoff = base + timedelta(days=i * 3, hours=20)
        m = models.Match(
            external_id=f"demo-{i}",
            home_team_id=home.id,
            away_team_id=away.id,
            kickoff=kickoff,
            status="finished",
        )
        db.add(m)
        db.flush()
        matches.append(m)

    # próximos partidos (los que recibirán picks)
    upcoming_matches: list[models.Match] = []
    for j in range(upcoming):
        home = teams[(finished + j) % len(teams)]
        away = teams[(finished + j + 2) % len(teams)]
        kickoff = datetime.now(UTC) + timedelta(days=1 + j)

        m = models.Match(
            external_id=f"demo-up-{j}",
            home_team_id=home.id,
            away_team_id=away.id,
            kickoff=kickoff,
            status="scheduled",
        )
        db.add(m)
        db.flush()
        upcoming_matches.append(m)

    for m in matches:
        _simulate_match_stats(db, m, players)
    for m in upcoming_matches:
        _seed_probable_lineups(db, m, players)

    counts["teams"] = len(teams)
    counts["players"] = len(players)
    counts["finished"] = len(matches)
    counts["upcoming"] = len(upcoming_matches)
    db.commit()
    logger.info("Semilla demo cargada: %s", counts)
    return counts


def delete_all(db: Session) -> None:
    """Borra del esquema demo (en orden FK)."""
    for table in (
        models.PickResult,
        models.MatchReport,
        models.Pick,
        models.Projection,
        models.PlayerStat,
        models.Lineup,
        models.Injury,
        models.ModelRun,
        models.Match,
        models.Player,
        models.Team,
    ):
        for row in db.scalars(select(table)).all():
            db.delete(row)
    db.flush()


def _seed_teams(db: Session) -> list[models.Team]:
    for name in DEMO_TEAMS:
        db.add(models.Team(name=name, short_name=name[:3].upper()))
    db.flush()
    return list(db.scalars(select(models.Team)).all())


def _seed_players(db: Session, teams: list[models.Team]) -> list[models.Player]:
    for team in teams:
        for position, amount in TEAM_SIZE.items():
            for i in range(amount):
                name = f"{team.name}·{position}{i + 1}"
                salary = float(
                    np.clip(rng.normal(8_000_000, 2_000_000), 2_000_000, 15_000_000)
                )
                db.add(
                    models.Player(
                        external_id=f"demo-{team.id}-{position}-{i}",
                        name=name,
                        team_id=team.id,
                        position=position,
                        salary=round(salary),
                    )
                )
    db.flush()
    return list(db.scalars(select(models.Player)).all())


def _position_baseline(position: str) -> dict[str, tuple[float, float]]:
    """Media/desv. plausibles por posición en un partido de 90 min."""
    return {
        "GK": {"saves": (3.5, 1.5)},
        "DEF": {"tackles": (2.5, 1.2), "shots_on_target": (0.3, 0.5)},
        "MID": {
            "key_passes": (1.8, 1.1),
            "shots_on_target": (0.9, 0.8),
            "tackles": (1.2, 0.9),
        },
        "FWD": {"shots_on_target": (1.4, 1.0)},
    }.get(position, {})


def _simulate_match_stats(db: Session, match: models.Match, players: list[models.Player]) -> None:
    """Stats plausibles para un partido terminado (local con leve ventaja)."""
    match.home_goals = int(rng.poisson(1.3))
    match.away_goals = int(rng.poisson(1.0))

    for side, conceded, scored_against in (
        (match.home_team_id, match.away_goals, match.home_goals),
        (match.away_team_id, match.home_goals, match.away_goals),
    ):
        _ = scored_against  # reservado para features por equipo
        for player in players:
            if player.team_id != side:
                continue
            starter = np.clip(rng.normal(9, 3), 0, 12) > 2
            minutes = int(np.clip(rng.normal(78 if starter else 28, 12), 0, 90))
            stats = _stats_for_position(player.position, minutes)
            if player.position == "GK":
                stats["goals_conceded"] = conceded if minutes >= 80 else 0
                stats["clean_sheet"] = conceded == 0 and minutes >= 80
            db.add(models.PlayerStat(player_id=player.id, match_id=match.id, **stats))


def _stats_for_position(position: str, minutes: int) -> dict[str, int | bool]:
    """Eventos proporcionales a minutos con baseline por posición."""
    share = minutes / 90.0
    stats: dict[str, int | bool] = {
        "minutes": minutes,
        "started": minutes >= 55,
        "goals": 0,
        "assists": 0,
        "shots_on_target": 0,
        "key_passes": 0,
        "tackles": 0,
        "saves": 0,
        "goals_conceded": 0,
        "clean_sheet": False,
        "yellow_cards": 1 if rng.random() < 0.22 * share else 0,
        "red_card": bool(rng.random() < 0.03 * share),
        "own_goal": 0,
        "penalty_saved": 0,
        "penalty_missed": 0,
    }
    for event_name, rates in _position_baseline(position).items():
        stats[event_name] = int(rng.poisson(rates[0] * share))
    # goles y asistencias globalmente necesarios
    goal_rate = {"GK": 0.02, "DEF": 0.10, "MID": 0.30, "FWD": 0.55}[position] * share
    if rng.random() < goal_rate:
        stats["goals"] = 1
    assist_rate = {"GK": 0.02, "DEF": 0.10, "MID": 0.30, "FWD": 0.20}[position] * share
    if rng.random() < assist_rate:
        stats["assists"] = 1
    return stats


def _seed_probable_lineups(db: Session, match: models.Match, players: list[models.Player]) -> None:
    for player in players:
        if player.team_id not in (match.home_team_id, match.away_team_id):
            continue
        if rng.random() < 0.85:
            db.add(
                models.Lineup(
                    match_id=match.id,
                    player_id=player.id,
                    kind="probable",
                    lineup_position=player.position,
                )
            )
        if rng.random() < 0.05:  # ~1 baja por convocatoria
            db.add(
                models.Lineup(
                    match_id=match.id, player_id=player.id, kind="out"
                )
            )
