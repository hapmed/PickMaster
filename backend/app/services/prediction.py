"""Pronóstico del partido: quién gana, marcador probable y quién anota.

Modelo Poisson transparente con corte temporal (sin fuga de datos):

- Team:  goles esperados local = (ataque local / media liga) × (defensa vs
  visita / media liga) × media liga  — i.e. ataque × debilidad del rival.
- Evento: P(local), P(empate), P(visita) y marcador más probable sobre una
  malla 0..8 (la cola es despreciable).
- Anotadores: 1 − exp(−E[goles]) por jugador usando `expected_events`
  guardado por el motor Monte Carlo.
"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

MAX_GRID = 8  # malla 0..8 goles por equipo


def goals_scored_per_game(db: Session, team_id: int, match: models.Match) -> float:
    """Media de goles anotados por el equipo en partidos terminados previos."""
    rows = db.execute(
        select(models.Match).where(
            models.Match.status == "finished",
            models.Match.kickoff < match.kickoff,
        )
    ).scalars().all()
    games, goals = 0, 0
    for m in rows:
        if m.home_team_id == team_id:
            goals += m.home_goals or 0
            games += 1
        elif m.away_team_id == team_id:
            goals += m.away_goals or 0
            games += 1
    return goals / games if games else 0.0


def goals_conceded_per_game(db: Session, team_id: int, match: models.Match) -> float:
    """Media de goles recibidos por el equipo en partidos terminados previos."""
    rows = db.execute(
        select(models.Match).where(
            models.Match.status == "finished",
            models.Match.kickoff < match.kickoff,
        )
    ).scalars().all()
    games, goals = 0, 0
    for m in rows:
        if m.home_team_id == team_id:
            goals += m.away_goals or 0
            games += 1
        elif m.away_team_id == team_id:
            goals += m.home_goals or 0
            games += 1
    return goals / games if games else 0.0


def team_lambdas(
    db: Session, match: models.Match
) -> tuple[float, float, float]:
    """(goles esperados local, goles esperados visita, media liga por equipo).

    Sin historial devuelve (0.5, 0.5, 1.0): prior neutro honesto, no invención.
    """
    att_h = goals_scored_per_game(db, match.home_team_id, match)
    att_a = goals_scored_per_game(db, match.away_team_id, match)
    def_h = goals_conceded_per_game(db, match.home_team_id, match)
    def_a = goals_conceded_per_game(db, match.away_team_id, match)
    if att_h <= 0 or att_a <= 0 or def_h <= 0 or def_a <= 0:
        return 0.5, 0.5, 1.0
    league = (att_h + att_a + def_h + def_a) / 4.0
    if league <= 0:
        return 0.5, 0.5, 1.0
    lam_h = float(min(max(att_h * def_a / league, 0.2), 4.0))
    lam_a = float(min(max(att_a * def_h / league, 0.2), 4.0))
    return lam_h, lam_a, league


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def outcome_and_score(
    lam_home: float, lam_away: float
) -> tuple[float, float, float, tuple[int, int]]:
    """(P(local), P(empate), P(visita), marcador más probable)."""
    p_home = p_draw = p_away = 0.0
    best_p, best_score = 0.0, (0, 0)
    for h in range(MAX_GRID + 1):
        for a in range(MAX_GRID + 1):
            mass = _poisson_pmf(h, lam_home) * _poisson_pmf(a, lam_away)
            if h > a:
                p_home += mass
            elif h == a:
                p_draw += mass
            else:
                p_away += mass
            if mass > best_p:
                best_p = mass
                best_score = (h, a)
    total = p_home + p_draw + p_away
    norm = total if total > 0 else 1.0
    return p_home / norm, p_draw / norm, p_away / norm, best_score


def scorer_candidates(
    db: Session, match: models.Match
) -> list[dict[str, object]]:
    """Ranking de anotadores: P(y="¿anota?") = 1 − exp(−E[goles]) por jugador."""
    rows = db.execute(
        select(models.Projection, models.Player)
        .join(models.Player, models.Player.id == models.Projection.player_id)
        .where(models.Projection.match_id == match.id)
        .order_by(models.Projection.created_at.desc())
    ).all()

    seen: set[int] = set()
    out: list[dict[str, object]] = []
    for proj, player in rows:
        if proj.player_id in seen:
            continue
        seen.add(proj.player_id)
        ev = proj.expected_events or {}
        exp_goals = float(ev.get("goals", 0.0))
        if exp_goals <= 0.01:
            continue
        out.append(
            {
                "player_id": player.id,
                "player": player.name,
                "position": player.position,
                "team": _team_name_local(db, player.team_id),
                "goals_expected": round(exp_goals, 2),
                "prob_score": round(1.0 - math.exp(-exp_goals), 3),
            }
        )
    out.sort(key=lambda d: float(str(d["prob_score"])), reverse=True)
    return out[:8]


def _team_name_local(db: Session, team_id: int | None) -> str:
    if team_id is None:
        return "equipo"
    team = db.get(models.Team, team_id)
    return team.name if team else f"team#{team_id}"


def match_prediction(db: Session, match: models.Match) -> dict[str, object]:
    """Pronóstico completo del partido en un dict listo para la API."""
    lam_h, lam_a, league = team_lambdas(db, match)
    p_home, p_draw, p_away, best = outcome_and_score(lam_h, lam_a)
    scorers = scorer_candidates(db, match)
    return {
        "match_id": match.id,
        "home": _team_name_local(db, match.home_team_id),
        "away": _team_name_local(db, match.away_team_id),
        "home_goals_expected": round(lam_h, 2),
        "away_goals_expected": round(lam_a, 2),
        "league_goals_average": round(league, 2),
        "p_home": round(p_home, 3),
        "p_draw": round(p_draw, 3),
        "p_away": round(p_away, 3),
        "most_likely_score": list(best),
        "scorers": scorers,
        "disclaimer": "Poisson con historial previo al corte; no garantiza nada",
    }
