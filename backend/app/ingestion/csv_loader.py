"""Ingesta manual por CSV (única vía autorizada para reglas/salarios/alineaciones).

Formatos esperados (headers fijos, UTF-8, coma):

- teams.csv:      name,short_name
- players.csv:    name,team,position,salary
- matches.csv:    home,away,kickoff(YYYY-MM-DD HH:MM),tournament
- stats.csv:      player,match_key(= home|away|kickoff),minutes,goals,assists,shots_on_target,
                  key_passes,tackles,saves,goals_conceded,clean_sheet,yellow_cards,red_card,
                  own_goal,penalty_saved,penalty_missed
- lineups.csv:    player,match_key,kind(probable|confirmed|out),lineup_position
- injuries.csv:   player,kind,detail,from(YYYY-MM-DD),to(YYYY-MM-DD)
- salaries.csv:   player,salary  (actualiza salarios)

Cada carga registra timestamp y audit_log. No scrapear ninguna fuente.
"""

from __future__ import annotations

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import new_session

logger = logging.getLogger(__name__)

POSITIONS = models.PlayerPosition.ALL


def _parse_dt(value: str, *, date_only: bool = False) -> datetime:
    if date_only:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=UTC)
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def _get_or_create_team(db: Session, name: str) -> models.Team:
    team = db.scalar(select(models.Team).where(models.Team.name == name))
    if team is None:
        team = models.Team(name=name)
        db.add(team)
        db.flush()
    return team


def _get_player(db: Session, name: str) -> models.Player | None:
    return db.scalar(select(models.Player).where(models.Player.name == name))


def load_teams(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            team = _get_or_create_team(db, row["name"].strip())
            team.short_name = row.get("short_name") or team.short_name
            count += 1
    db.commit()
    return count


def load_players(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            position = row["position"].strip().upper()
            if position not in POSITIONS:
                logger.warning("posición inválida en players.csv: %s", position)
                continue
            team = _get_or_create_team(db, row["team"].strip())
            player = _get_player(db, row["name"].strip())
            salary = row.get("salary") or None
            if player is None:
                player = models.Player(
                    name=row["name"].strip(),
                    team_id=team.id,
                    position=position,
                    salary=float(salary) if salary else None,
                )
                db.add(player)
            else:
                player.team_id = team.id
                player.position = position
                if salary:
                    player.salary = float(salary)
            count += 1
    db.commit()
    return count


def _find_match(db: Session, home: str, away: str, kickoff: datetime) -> models.Match | None:
    return db.scalar(
        select(models.Match).where(
            models.Match.kickoff == kickoff,
            models.Match.home_team_id.in_(
                select(models.Team.id).where(models.Team.name.in_([home]))
            ),
            models.Match.away_team_id.in_(
                select(models.Team.id).where(models.Team.name.in_([away]))
            ),
        )
    )


def load_matches(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            home = _get_or_create_team(db, row["home"].strip())
            away = _get_or_create_team(db, row["away"].strip())
            kickoff = _parse_dt(row["kickoff"])
            match = _find_match(db, row["home"].strip(), row["away"].strip(), kickoff)
            if match is None:
                match = models.Match(
                    tournament=row.get("tournament") or "Liga MX",
                    home_team_id=home.id,
                    away_team_id=away.id,
                    kickoff=kickoff,
                    status=row.get("status") or "scheduled",
                )
                db.add(match)
            if row.get("home_goals"):
                match.home_goals = int(row["home_goals"])
                match.away_goals = int(row["away_goals"] or 0)
                match.status = "finished"
            count += 1
    db.commit()
    return count


def load_stats(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            player = _get_player(db, row["player"].strip())
            match_key = row["match_key"].strip()
            match = db.get(models.Match, _match_id_from_key(db, match_key))
            if not player or match is None:
                logger.warning("stats.csv: fila ignorada (%s)", row)
                continue
            existing = db.scalar(
                select(models.PlayerStat).where(
                    models.PlayerStat.player_id == player.id,
                    models.PlayerStat.match_id == match.id,
                )
            )
            values = {
                "minutes": int(row.get("minutes") or 0),
                "started": (int(row.get("minutes") or 0) > 0)
                and row.get("started", "true") in {"1", "true", "True"},
                "goals": int(row.get("goals") or 0),
                "assists": int(row.get("assists") or 0),
                "shots_on_target": int(row.get("shots_on_target") or 0),
                "key_passes": int(row.get("key_passes") or 0),
                "tackles": int(row.get("tackles") or 0),
                "saves": int(row.get("saves") or 0),
                "goals_conceded": int(row.get("goals_conceded") or 0),
                "clean_sheet": row.get("clean_sheet", "false") in {"1", "true", "True"},
                "yellow_cards": int(row.get("yellow_cards") or 0),
                "red_card": row.get("red_card", "false") in {"1", "true", "True"},
                "own_goal": int(row.get("own_goal") or 0),
                "penalty_saved": int(row.get("penalty_saved") or 0),
                "penalty_missed": int(row.get("penalty_missed") or 0),
            }
            if existing is None:
                db.add(
                    models.PlayerStat(player_id=player.id, match_id=match.id, **values)
                )
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
            count += 1
    db.commit()
    return count


def _match_id_from_key(db: Session, key: str) -> int | None:
    """match_key en CSV: id interno o external_id."""
    if key.isdigit():
        return int(key)
    match_id = db.scalar(
        select(models.Match.id).where(models.Match.external_id == key)
    )
    return int(match_id) if match_id is not None else None


def load_lineups(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            player = _get_player(db, row["player"].strip())
            match = db.get(models.Match, _match_id_from_key(db, row["match_key"].strip()))
            if not player or match is None:
                continue
            kind = row["kind"].strip()
            existing = db.scalar(
                select(models.Lineup).where(
                    models.Lineup.match_id == match.id,
                    models.Lineup.player_id == player.id,
                    models.Lineup.kind == kind,
                )
            )
            if existing is None:
                db.add(
                    models.Lineup(
                        match_id=match.id,
                        player_id=player.id,
                        kind=kind,
                        lineup_position=row.get("lineup_position"),
                        confirmed=kind == "confirmed",
                        announced_at=now_utc(),
                    )
                )
            count += 1
    db.commit()
    return count


def load_injuries(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            player = _get_player(db, row["player"].strip())
            if player is None:
                continue
            db.add(
                models.Injury(
                    player_id=player.id,
                    kind=row["kind"].strip(),
                    detail=row.get("detail"),
                    from_date=_parse_dt(row["from"], date_only=True),
                    to_date=_parse_dt(row["to"], date_only=True) if row.get("to") else None,
                )
            )
            count += 1
    db.commit()
    return count


def load_salaries(db: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            player = _get_player(db, row["player"].strip())
            if player is None:
                continue
            player.salary = float(row["salary"])
            count += 1
    db.commit()
    return count


def load_all(data_dir: str | Path) -> dict[str, int]:
    """Carga en orden todos los CSV presentes en data_dir."""
    session = new_session()()
    results: dict[str, int] = {}
    try:
        root = Path(data_dir)
        loaders = {
            "teams": (load_teams, "teams.csv"),
            "players": (load_players, "players.csv"),
            "matches": (load_matches, "matches.csv"),
            "stats": (load_stats, "stats.csv"),
            "injuries": (load_injuries, "injuries.csv"),
            "lineups": (load_lineups, "lineups.csv"),
            "salaries": (load_salaries, "salaries.csv"),
        }
        for name, (loader, filename) in loaders.items():
            path = root / filename
            if path.exists():
                results[name] = loader(session, path)
                logger.info("CSV %s: %d filas", name, results[name])
        session.add(
            models.AuditLog(
                entity="ingestion",
                action="csv_load",
                detail=f"archivos={sorted(results)}",
                actor="worker",
            )
        )
        session.commit()
        return results
    finally:
        session.close()


def now_utc() -> datetime:
    return datetime.now(UTC)
