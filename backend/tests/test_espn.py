"""Tests de la ingesta ESPN (mapeos puros, sin llamar la red)."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion import espn
from app.models import Lineup, Match, PlayerStat


def test_map_position() -> None:
    assert espn.map_position("G") == "GK"
    assert espn.map_position("D") == "DEF"
    assert espn.map_position("M") == "MID"
    assert espn.map_position("F") == "FWD"
    assert espn.map_position("COACH") is None
    assert espn.map_position(None) is None


def test_minutes_from_subs() -> None:
    subs = [
        {
            "type": {"type": "substitution"},
            "clock": {"value": 2700.0},
            "participants": [
                {"athlete": {"id": "2"}},  # entra
                {"athlete": {"id": "1"}},  # sale
            ],
        }
    ]
    starter = {"athlete": {"id": "9"}, "starter": True}
    subbed_out = {"athlete": {"id": "1"}, "starter": True, "subbedOut": True}
    subbed_in = {"athlete": {"id": "2"}, "starter": False, "subbedIn": True}
    bench = {"athlete": {"id": "3"}, "starter": False}

    assert espn._minutes(starter, subs) == 90
    assert espn._minutes(subbed_out, subs) == 45
    assert espn._minutes(subbed_in, subs) == 45
    assert espn._minutes(bench, subs) == 0


def test_stat_lookup() -> None:
    st = espn._stat_lookup(
        [
            {"name": "totalGoals", "value": 2.0},
            {"name": "saves", "value": None},
        ]
    )
    assert st["totalGoals"] == 2.0
    assert st["saves"] == 0.0


def test_ingest_summary_stats_and_lineup(db: Session) -> None:
    """Rosters ESPN con nombres canónicos generan stats y alineación."""
    from app.models import Player

    match = db.scalars(select(Match).where(Match.status == "scheduled")).first()
    assert match is not None
    home_team_id = match.home_team_id

    p = db.scalar(select(Player).where(Player.team_id == home_team_id))
    assert p is not None

    row: dict[str, Any] = {
        "athlete": {"id": "espn-999", "displayName": p.name},
        "starter": True,
        "stats": [
            {"name": "totalGoals", "value": 1.0},
            {"name": "goalAssists", "value": 1.0},
            {"name": "shotsOnTarget", "value": 3.0},
            {"name": "saves", "value": 0.0},
            {"name": "yellowCards", "value": 1.0},
        ],
    }
    summary = {
        "keyEvents": [],
        "rosters": [
            {
                "team": {"displayName": db_team_name(db, home_team_id)},
                "roster": [row],
            }
        ],
    }
    stored = espn._ingest_summary(db, match, summary)
    assert stored == 1

    stat = db.scalar(
        select(PlayerStat).where(
            PlayerStat.player_id == p.id, PlayerStat.match_id == match.id
        )
    )
    assert stat is not None
    assert stat.minutes == 90  # starter sin sustitución
    assert stat.goals == 1
    assert stat.assists == 1
    assert stat.shots_on_target == 3
    assert stat.yellow_cards == 1
    assert stat.clean_sheet is (stat.goals_conceded == 0)

    lineup = db.scalars(
        select(Lineup).where(
            Lineup.match_id == match.id,
            Lineup.player_id == p.id,
            Lineup.kind == "confirmed",
        )
    ).first()
    assert lineup is not None, "titular ESPN queda como confirmado"


def db_team_name(db: Session, team_id: int) -> str:
    from app.models import Team

    team = db.get(Team, team_id)
    assert team is not None
    return team.name


def test_upsert_match_dedupe_with_sportsdb(db: Session) -> None:
    """Un evento ESPN equivalente a un match existente NO crea duplicado."""
    match = db.scalars(select(Match).where(Match.status == "scheduled")).first()
    assert match is not None
    from app.models import Team

    home = db.get(Team, match.home_team_id)
    away = db.get(Team, match.away_team_id)
    assert home and away

    kickoff_utc = match.kickoff.replace(tzinfo=UTC)
    event = {
        "id": "90210",
        "date": kickoff_utc.isoformat().replace("+00:00", "Z"),
        "status": {"type": {"state": "pre"}},
        "competitions": [
            {
                "competitors": [
                    {"team": {"displayName": home.name}},
                    {"team": {"displayName": away.name}},
                ]
            }
        ],
    }
    created = espn.upsert_match_from_event(db, event)
    assert created is not None
    assert created.id == match.id, "reutiliza el partido por equipos+fecha"
    # preserva el external_id original (SportsDB); ESPN solo llena partidos nuevos

    total = len(db.scalars(select(Match)).all())
    espn.upsert_match_from_event(db, {**event, "id": "99999"})
    assert len(db.scalars(select(Match)).all()) == total, "sin duplicados"
