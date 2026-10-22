"""Ingesta online desde TheSportsDB (API pública, clave de prueba '123').

Fuente pública confiable de equipos, jugadores y calendario de Liga MX
(id 4350). Respetamos sus límites: una llamada cada ~2.5 s en cargas por lotes.
NO cubre estadísticas evento-por-evento del free: sin `player_stats` el motor
usa priors por posición (confianza baja, comportamiento honesto).

Reglas Draftea y salarios siguen siendo CARGA MANUAL (sin scraping).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)

SPORTSDB_KEY = "123"  # clave pública de prueba
BASE = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
LIGA_MX_ID = "4350"

# Plantilla de nombres de equipos de Liga MX (búsqueda por nombre; el endpoint
# lookup_all_teams con la key de prueba devuelve otra liga).
LIGA_MX_TEAMS = [
    "Club America",
    "Guadalajara Chivas",
    "Cruz Azul",
    "Pumas UNAM",
    "Tigres UANL",
    "Monterrey",
    "Toluca",
    "Puebla",
    "Atlas",
    "Leon",
    "Necaxa",
    "Santos Laguna",
    "Atletico de San Luis",
    "Queretaro",
    "Mazatlan",
    "Club Tijuana",
    "FC Juarez",
    "Club Leon FC",
]

# Pausa entre llamadas para el free tier (la key de prueba cierra a pocas req/min).
SLEEP_SECONDS = 11.0

POSITION_MAP: dict[str, str] = {
    "goalkeeper": "GK",
    "defender": "DEF",
    "defensive mid" : "MID",
    "midfielder": "MID",
    "attacker": "FWD",
    "forward": "FWD",
    "striker": "FWD",
    "winger": "FWD",
    "right winger": "FWD",
    "left winger": "FWD",
    "centre forward": "FWD",
}


def map_position(raw: str | None) -> str | None:
    """Local→posición interna; Manager/otros → None (se salta)."""
    if not raw:
        return None
    low = raw.strip().lower()
    for key, pos in POSITION_MAP.items():
        if key in low:
            return pos
    return None


def fetch_json(url: str, *, retries: int = 3) -> dict[str, Any]:
    """GET con reintentos; en 429 respeta el Retry-After o espera 60s."""
    for attempt in range(retries + 1):
        try:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "60") or 60)
                logger.warning("429 en %s; esperando %ds", url, wait)
                time.sleep(max(wait, 60) if wait < 5 else wait)
                continue
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == retries:
                logger.error("GET %s falló: %s", url, exc)
                return {}
            time.sleep(SLEEP_SECONDS)
    return {}


def search_team(team_name: str) -> dict[str, Any] | None:
    """Primer equipo mexicano con ese nombre."""
    data = fetch_json(f"{BASE}/searchteams.php?t={httpx_Query(team_name)}")
    teams: list[dict[str, Any]] = data.get("teams") or []
    for team in teams:
        league = (team.get("strLeague") or "").lower()
        if "mexic" in league:
            return team
    return None


def httpx_Query(value: str) -> str:
    """Encoding seguro para querystring sin dependencia extra."""
    from urllib.parse import quote

    return quote(value)


def upsert_team(db: Session, team: dict[str, Any]) -> models.Team:
    external_id = str(team["idTeam"])
    row = db.scalar(
        select(models.Team).where(models.Team.external_id == external_id)
    )
    if row is None:
        row = models.Team(external_id=external_id, name=team["strTeam"])
        db.add(row)
        db.flush()
    row.name = team["strTeam"]
    row.short_name = team.get("strTeamAlternate") or team.get("strShortCode") or row.short_name
    row.league = team.get("strLeague") or row.league or "Liga MX"
    return row


def upsert_players(db: Session, team: models.Team) -> int:
    """Jugadores del equipo (nombres + posición)."""
    data = fetch_json(f"{BASE}/lookup_all_players.php?id={httpx_Query(team.external_id or '')}")
    players: list[dict[str, Any]] = data.get("player") or []
    count = 0
    for p in players:
        position = map_position(p.get("strPosition"))
        if position is None:  # Managers y staff no participan en fantasy
            continue
        external_id = str(p.get("idPlayer") or "")
        name = (p.get("strPlayer") or "").strip()
        if not name:
            continue
        row = db.scalar(
            select(models.Player).where(models.Player.external_id == external_id)
        )
        if row is None:
            row = models.Player(
                external_id=external_id, name=name, team_id=team.id, position=position
            )
            db.add(row)
            db.flush()
        row.name = name
        row.team_id = team.id
        row.position = position
        count += 1
    return count


def upsert_events(db: Session, events: list[dict[str, Any]], status: str) -> int:
    """Partidos desde eventos (next: scheduled, past: finished)."""
    count = 0
    for ev in events:
        external_id = str(ev.get("idEvent") or "")
        if not external_id:
            continue
        home_name = ev.get("strHomeTeam") or ""
        away_name = ev.get("strAwayTeam") or ""
        home = _team_by_name(db, home_name)
        away = _team_by_name(db, away_name)
        if home is None or away is None:
            continue
        kickoff = _parse_kickoff(ev)
        row = db.scalar(
            select(models.Match).where(models.Match.external_id == external_id)
        )
        if row is None:
            row = models.Match(
                external_id=external_id,
                tournament="Liga MX",
                home_team_id=home.id,
                away_team_id=away.id,
                kickoff=kickoff,
                status=status,
            )
            db.add(row)
            db.flush()
        row.kickoff = kickoff
        row.status = status
        if ev.get("intHomeScore") is not None:
            row.home_goals = int(ev["intHomeScore"])
            row.away_goals = int(ev.get("intAwayScore") or 0)
            row.status = "finished"
        elif status == "finished":
            row.status = "scheduled"
        count += 1
    return count


def _team_by_name(db: Session, name: str | None) -> models.Team | None:
    """Busca por id external (numérico) o por nombre normalizado."""
    if not name:
        return None
    norm = _normalize(name)
    if name.strip().isdigit():
        team = db.scalar(
            select(models.Team).where(models.Team.external_id == name.strip())
        )
        if team is not None:
            return team
    rows = db.scalars(select(models.Team)).all()
    for row in rows:
        row_norm = _normalize(row.name)
        if row_norm == norm or norm in row_norm or row_norm in norm:
            return row
    return None


def _normalize(name: str) -> str:
    dropped = name.lower()
    for source, target in (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"),
        ("ú", "u"), ("ü", "u"), ("fc", ""), ("cf", ""),
    ):
        dropped = dropped.replace(source, target)
    return dropped.strip(" _-")


def _parse_kickoff(ev: dict[str, Any]) -> datetime:
    """strTimestamp ISO > dateEvent+strTime > dateEvent+19:00 → datetime UTC."""
    date = ev.get("dateEvent") or "1970-01-01"
    stamp = (ev.get("strTimestamp") or "").strip()
    if stamp:
        try:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00")).replace(
                tzinfo=stamp.endswith("Z") and UTC or None
            ) if stamp.endswith("Z") else datetime.fromisoformat(stamp).replace(tzinfo=UTC)
        except ValueError:
            logger.warning("strTimestamp ilegible: %s", stamp)
    match_time = ((ev.get("strTimestring") or ev.get("strTime") or "").strip().split(" "))[0]
    raw = f"{date} {match_time}" if match_time else f"{date} 19:00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    logger.warning("kickoff ilegible: %s", raw)
    return datetime(1970, 1, 1, tzinfo=UTC)


def seed_probables_from_roster(db: Session, match: models.Match) -> int:
    """Convocatoria probable = todo el roster disponible del partido.

    Marcada kind='probable': NO es alineación confirmada (esas llegan por
    CSV manual o jobs T-1h). Evita inventar XI inexistente.
    """
    count = 0
    confirmed = set()
    for kind in ("probable", "confirmed"):
        confirmed |= {
            row.player_id for row in db.scalars(
                select(models.Lineup).where(
                    models.Lineup.match_id == match.id,
                    models.Lineup.kind == kind,
                )
            ).all()
        }
    players = db.scalars(
        select(models.Player).where(
            models.Player.team_id.in_([match.home_team_id, match.away_team_id])
        )
    ).all()
    for player in players:
        if player.id in confirmed:
            continue
        db.add(
            models.Lineup(
                match_id=match.id,
                player_id=player.id,
                kind="probable",
                lineup_position=player.position,
            )
        )
        count += 1
    return count



def _team_exists(db: Session, name: str) -> bool:
    """True si un equipo normalizado equivalente ya está en BD (reruns acumulativos)."""
    norm = _normalize(name)
    for row in db.scalars(select(models.Team)).all():
        row_norm = _normalize(row.name)
        if row_norm == norm or norm in row_norm or row_norm in norm:
            return True
    return False


def ingest_online(
    db: Session,
    *,
    team_names: list[str] | None = None,
    sleep_seconds: float = SLEEP_SECONDS,
) -> dict[str, int]:
    """Ingesta completa online de Liga MX (equipos, jugadores, calendario)."""
    names = team_names or LIGA_MX_TEAMS
    counts: dict[str, int] = {"teams": 0, "players": 0, "events": 0}

    next_raw = fetch_json(f"{BASE}/eventsnextleague.php?id={LIGA_MX_ID}")
    past_raw = fetch_json(f"{BASE}/eventspastleague.php?id={LIGA_MX_ID}")
    upcoming: list[dict[str, Any]] = next_raw.get("events") or []
    past: list[dict[str, Any]] = past_raw.get("events") or []
    logger.info("TheSportsDB: %d próximos, %d pasados", len(upcoming), len(past))

    for name in names:
        if _team_exists(db, name):
            logger.info("%s ya está ingestado; salto (carga acumulativa)", name)
            continue
        team = search_team(name)
        if team is None:
            logger.warning("Equipo no encontrado en API: %s", name)
            continue
        row = upsert_team(db, team)
        counts["teams"] += 1
        counts["players"] += upsert_players(db, row)
        db.commit()
        time.sleep(sleep_seconds)

    counts["events"] += upsert_events(db, upcoming, status="scheduled")
    counts["events"] += upsert_events(db, past, status="finished")

    scheduled = db.scalars(
        select(models.Match).where(models.Match.status != "finished")
    ).all()
    for m in scheduled:
        counts["lineups"] = counts.get("lineups", 0) + seed_probables_from_roster(db, m)

    db.add(
        models.AuditLog(
            entity="ingestion",
            action="sportsdb_fetch",
            detail=str(counts),
            actor="worker",
        )
    )
    db.commit()
    logger.info("Ingesta online: %s", counts)
    return counts


def now_utc() -> datetime:
    return datetime.now(UTC)
