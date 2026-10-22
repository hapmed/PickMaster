"""Ingesta ESPN — Liga MX (mex.1) sin API key.

Fuente: endpoints públicos que alimenta la web de ESPN (site.api.espn.com).
No es una API oficial documentada: los usamos de forma mínima y respetuosa
(pocas llamadas, pausa entre peticiones y User-Agent identificable).

Qué entrega (verificado 2026-10-22):
- `/teams` → equipos de la jornada con id interno ESPN.
- `/teams/{id}/roster` → plantilla completa (G/D/M/F con posición y edad).
- `/scoreboard?dates=AAAA-MM-DD` → fixtures del día con id de evento.
- `/summary?event=…` → marcador, key events y estadísticas por jugador por
  partido (goles, asistencias, tiros, tarjetas, paradas, faltas), más el
  once inicial flag y sustituciones (subbedIn/subbedOut) para derivar minutos.
"""

from __future__ import annotations

import logging
import time
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1"
HEADERS = {"User-Agent": "PickMaster/0.2 (fantasy amateur Liga MX; repo hapmed)"}
RETRIES = 3

# Posiciones ESPN → internas. Los no mapeados (coach/staff) se descartan.
POSITION_MAP: dict[str, str] = {"G": "GK", "D": "DEF", "M": "MID", "F": "FWD"}


def map_position(raw: str | None) -> str | None:
    """G→GK, D→DEF, M→MID, F→FWD; resto (coach, staff…) → None."""
    if not raw:
        return None
    return POSITION_MAP.get(raw.strip().upper())


def fetch_json(url: str, *, polite_seconds: float = 3.0) -> dict[str, Any] | None:
    """GET JSON con reintentos cortos y pausa de cortesía. None si falla."""
    for attempt in range(1, RETRIES + 1):
        try:
            with httpx.Client(
                headers=HEADERS, timeout=15.0, follow_redirects=True
            ) as client:
                res = client.get(url)
            if res.status_code == 429:
                wait = float(res.headers.get("Retry-After", "60"))
                logger.warning("429 en %s; esperando %ss", url, wait)
                time.sleep(min(wait, 120.0))
                continue
            if res.status_code == 404:
                return None
            res.raise_for_status()
            data: dict[str, Any] = res.json()
            return data
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "intento %d/%d falló en %s: %s", attempt, RETRIES, url, exc
            )
            time.sleep(polite_seconds * attempt)
    return None


def normalize(name: str | None) -> str:
    """Minúsculas sin acentos, único espacio entre palabras."""
    if not name:
        return ""
    plain = unicodedata.normalize("NFKD", name.strip().lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return " ".join(plain.split())


# ESPN suele acortar nombres; alias explícitos a nuestro nombre canónico.
TEAM_ALIASES: dict[str, str] = {
    "santos": "Santos Laguna",
    "guadalajara": "CD Guadalajara",
    "juarez": "Juárez",
    "leon": "León",
    "necaxa": "Necaxa",
    "mazatlan": "Mazatlán",
    "atletico de san luis": "Atlético de San Luis",
    "san luis": "Atlético de San Luis",
    "america": "América",
    "unam": "Pumas UNAM",
    "tigres": "Tigres UANL",
    "queretaro": "Querétaro",
    "puebla": "Puebla",
    "atlas": "Atlas",
    "toluca": "Toluca",
    "monterrey": "Monterrey",
    "cruz azul": "Cruz Azul",
    "tijuana": "Tijuana",
}


def find_team(db: Session, name: str | None) -> models.Team | None:
    """Resuelve un Teams por alias/normalización (exacta o por contención)."""
    if not name:
        return None
    norm = normalize(name)
    target = TEAM_ALIASES.get(norm, name)
    target_norm = normalize(target)
    for team in db.scalars(select(models.Team)).all():
        row_norm = normalize(team.name)
        if target_norm == row_norm or target_norm in row_norm or row_norm in target_norm:
            return team
    return None


def find_player(
    db: Session, team_id: int, name: str | None
) -> models.Player | None:
    """Resuelve un jugador del equipo por nombre normalizado (o contención)."""
    if not name:
        return None
    norm = normalize(name)
    best: models.Player | None = None
    best_len = 0
    for player in db.scalars(
        select(models.Player).where(models.Player.team_id == team_id)
    ):
        row_norm = normalize(player.name)
        if norm == row_norm:
            return player
        if (norm in row_norm or row_norm in norm) and len(row_norm) > best_len:
            best, best_len = player, len(row_norm)
    return best


def _event_status(event: dict[str, Any]) -> str:
    # pre/in → scheduled; post → finished. Guardamos solo esos dos estados.
    state = str((event.get("status") or {}).get("type", {}).get("state") or "")
    return "finished" if state == "post" else "scheduled"


def _event_kickoff(event: dict[str, Any]) -> datetime:
    raw = event.get("date") or ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _find_duplicate(
    db: Session, home_id: int, away_id: int, kickoff: datetime
) -> models.Match | None:
    """Partido ya ingestado par compatriota ±6h (evita duplicar con SportsDB)."""
    for m in db.scalars(
        select(models.Match).where(
            models.Match.home_team_id == home_id,
            models.Match.away_team_id == away_id,
        )
    ).all():
        if abs((m.kickoff - kickoff.replace(tzinfo=None)).total_seconds()) <= 6 * 3600:
            return m
    return None


def upsert_match_from_event(db: Session, event: dict[str, Any]) -> models.Match | None:
    """Upsert de un partido ESPN por external_id o por duplicado por equipos."""
    comps = event.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    home = find_team(db, (comp.get("competitors") or [{}])[0].get("team", {}).get("displayName"))
    away = find_team(db, (comp.get("competitors") or [{}])[-1].get("team", {}).get("displayName"))
    if home is None or away is None:
        logger.warning("ESPN: no pude mapear equipos del evento %s", event.get("id"))
        return None
    kickoff = _event_kickoff(event)
    external = f"espn:{event.get('id')}"

    row = db.scalar(select(models.Match).where(models.Match.external_id == external))
    if row is None:
        row = _find_duplicate(db, home.id, away.id, kickoff)
        if row is not None and row.external_id is None:
            row.external_id = external

    if row is None:
        row = models.Match(
            external_id=external,
            tournament="Liga MX",
            home_team_id=home.id,
            away_team_id=away.id,
            kickoff=kickoff.replace(tzinfo=None),
            status=_event_status(event),
        )
        db.add(row)
        db.flush()
        return row

    # Upsert sobre existente (SportsDB): external propio se preserva.
    if row.external_id is None:
        row.external_id = external
    row.tournament = "Liga MX"
    row.home_team_id = home.id
    row.away_team_id = away.id
    row.kickoff = kickoff.replace(tzinfo=None)
    row.status = _event_status(event)
    if row.status == "finished":
        for comp_row, team_col in (
            ((comp.get("competitors") or [{}])[0], "home_goals"),
            ((comp.get("competitors") or [{}])[-1], "away_goals"),
        ):
            total = comp_row.get("score")
            if total is not None:
                setattr(row, team_col, int(total))
    return row


def scoreboard(date: str, *, polite_seconds: float = 3.0) -> list[dict[str, Any]]:
    """Eventos Liga MX de un día (A-M-D); usa formato compacto AAAAMMDD."""
    compact = date.replace("-", "")
    data = fetch_json(f"{BASE}/scoreboard?dates={compact}", polite_seconds=polite_seconds)
    if not data:
        return []
    return list(data.get("events") or [])


def _stat_lookup(stats: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in stats:
        name = str(s.get("name") or "")
        if name:
            out[name] = float(s.get("value") or 0)
    return out


def _minutes(row: dict[str, Any], subs: list[dict[str, Any]]) -> int:
    """Minutos jugados derivados de sustituciones (clock en segundos)."""
    athlete_id = str((row.get("athlete") or {}).get("id") or "")
    if row.get("starter") and not row.get("subbedOut"):
        return 90
    for ev in subs:
        participants = ev.get("participants") or []
        clock = (ev.get("clock") or {}).get("value")
        if clock is None:
            continue
        mins = int(float(clock) // 60)
        ids = [str(p.get("athlete", {}).get("id")) for p in participants]
        if row.get("subbedIn") and athlete_id in ids[:1]:
            return max(0, 90 - mins)
        if row.get("subbedOut") and athlete_id in ids[1:2]:
            return min(90, mins)
    return 90 if row.get("starter") else 0


def _subs_from_events(key_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Solo los eventos de sustitución (tienen reloj y participantes)."""
    return [
        ev
        for ev in key_events or []
        if (ev.get("type") or {}).get("type") == "substitution"
    ]


def _upsert_player_stat(
    db: Session,
    player: models.Player,
    match: models.Match,
    row: dict[str, Any],
    subs: list[dict[str, Any]],
) -> bool:
    st = _stat_lookup(row.get("stats") or [])
    started = bool(row.get("starter"))
    minutes = _minutes(row, subs)
    existing = db.scalar(
        select(models.PlayerStat).where(
            models.PlayerStat.player_id == player.id,
            models.PlayerStat.match_id == match.id,
        )
    )
    if existing is None:
        existing = models.PlayerStat(player_id=player.id, match_id=match.id)
        db.add(existing)
    existing.started = started
    existing.minutes = minutes
    existing.goals = int(st.get("totalGoals", 0))
    existing.assists = int(st.get("goalAssists", 0))
    existing.shots_on_target = int(st.get("shotsOnTarget", 0))
    existing.saves = int(st.get("saves", 0))
    existing.goals_conceded = int(st.get("goalsConceded", 0))
    existing.clean_sheet = minutes > 0 and existing.goals_conceded == 0
    existing.yellow_cards = int(st.get("yellowCards", 0))
    existing.red_card = bool(st.get("redCards", 0))
    existing.own_goal = int(st.get("ownGoals", 0))
    existing.updated_at = datetime.now(UTC).replace(tzinfo=None)
    return True


# (sin estado global: los sustituciones se calculan por summary)


def _ingest_summary(db: Session, match: models.Match, summary: dict[str, Any]) -> int:
    """Rosters + stats por jugador del summary del partido."""
    subs = _subs_from_events(summary.get("keyEvents") or [])
    stored = 0
    for team_block in summary.get("rosters") or []:
        team = find_team(db, (team_block.get("team") or {}).get("displayName"))
        if team is None:
            continue
        for row in team_block.get("roster") or []:
            athlete = row.get("athlete") or {}
            player = find_player(db, team.id, athlete.get("displayName"))
            if player is None:
                continue  # solo seguimos jugadores ya ingestado (rosters previos)
            if _upsert_player_stat(db, player, match, row, subs):
                stored += 1
            # alineación confirmada: titulares (los reservas no van)
            if row.get("starter"):
                already = db.scalar(
                    select(models.Lineup).where(
                        models.Lineup.match_id == match.id,
                        models.Lineup.player_id == player.id,
                        models.Lineup.kind == "confirmed",
                    )
                )
                if already is None:
                    db.add(
                        models.Lineup(
                            match_id=match.id,
                            player_id=player.id,
                            kind="confirmed",
                        )
                    )
    return stored


def ingest_fixtures(
    db: Session, *, days_back: int = 2, days_forward: int = 14,
    polite_seconds: float = 3.0,
) -> dict[str, int]:
    """Programación de Liga MX por rango de fechas (partidos scheduled)."""
    counts = {"matches": 0, "events": 0}
    today = datetime.now(UTC).date()
    for offset in range(-days_back, days_forward + 1):
        day = today + timedelta(days=offset)
        for event in scoreboard(day.isoformat(), polite_seconds=polite_seconds):
            counts["events"] += 1
            if upsert_match_from_event(db, event) is not None:
                counts["matches"] += 1
        db.commit()
        time.sleep(polite_seconds)
    return counts


def ingest_results(
    db: Session, *, days_back: int = 8, polite_seconds: float = 3.0
) -> dict[str, int]:
    """Resultados + stats de jugadores para partidos terminados recientes."""
    counts = {"finished": 0, "stats": 0}
    today = datetime.now(UTC).date()
    for offset in range(-days_back, 0):
        day = today + timedelta(days=offset)
        for event in scoreboard(day.isoformat(), polite_seconds=polite_seconds):
            if _event_status(event) != "finished":
                continue
            match = upsert_match_from_event(db, event)
            if match is None:
                continue
            counts["finished"] += 1
            summary = fetch_json(f"{BASE}/summary?event={event.get('id')}")
            if summary:
                stats_n = _ingest_summary(db, match, summary)
                counts["stats"] += stats_n
            db.commit()
            time.sleep(polite_seconds)
    return counts


def ingest_results_for_match(
    db: Session, match: models.Match, *, polite_seconds: float = 3.0
) -> int:
    """Sobre un partido concreto: busca su event ESPN y trae stats.

    Devuelve cantidad de player_stats almacenadas (0 = nada aún disponible).
    """
    day = match.kickoff.date()
    external = str(match.external_id or "")
    event_id = external[5:] if external.startswith("espn:") else ""
    summary: dict[str, Any] | None = None
    for date_str in (day.isoformat(), (day + timedelta(days=1)).isoformat()):
        for event in scoreboard(date_str, polite_seconds=polite_seconds):
            if not _event_same(db, event, match):
                continue
            fresh = str(event.get("id") or "")
            if _event_status(event) == "finished":
                upsert_match_from_event(db, event)
                summary = fetch_json(f"{BASE}/summary?event={fresh}")
            break
        if summary:
            break
    if not summary and event_id and event_id.isdigit():
        summary = fetch_json(f"{BASE}/summary?event={event_id}")
    if not summary:
        return 0
    return _ingest_summary(db, match, summary)


def _event_same(
    db: Session, event: dict[str, Any], match: models.Match
) -> bool:
    """Empareja un event ESPN con nuestro Match (equipos + fecha ±1 día)."""
    comps = event.get("competitions") or []
    if not comps:
        return False
    comp = comps[0]
    competitors = comp.get("competitors") or []
    if len(competitors) < 2:
        return False
    home_name = competitors[0].get("team", {}).get("displayName")
    away_name = competitors[-1].get("team", {}).get("displayName")
    home = find_team(db, home_name)
    away = find_team(db, away_name)
    if home is None or away is None:
        return False
    if {home.id, away.id} != {match.home_team_id, match.away_team_id}:
        return False
    kickoff = _event_kickoff(event)
    return (
        abs((kickoff.replace(tzinfo=None) - match.kickoff).total_seconds())
        <= 26 * 3600
    )


def ingest_rosters(db: Session, *, polite_seconds: float = 3.0) -> dict[str, int]:
    """Plantillas completas por equipo (rellena jugadores que faltan)."""
    counts = {"teams": 0, "players": 0}
    data = fetch_json(f"{BASE}/teams", polite_seconds=polite_seconds)
    if not data:
        return counts
    leagues = (data.get("sports") or [{}])[0].get("leagues") or [{}]
    for entry in (leagues[0].get("teams") or []):
        team = entry.get("team", {})
        db_team = find_team(db, team.get("displayName"))
        if db_team is None:
            continue
        counts["teams"] += 1
        roster = fetch_json(
            f"{BASE}/teams/{team.get('id')}/roster", polite_seconds=polite_seconds
        )
        for athlete in (roster or {}).get("athletes") or []:
            position = map_position((athlete.get("position") or {}).get("abbreviation"))
            if position is None:
                continue
            external = f"espn:{athlete.get('id')}"
            existing = db.scalar(
                select(models.Player).where(models.Player.external_id == external)
            )
            if existing is None:
                # Nombre exacto ya existe en el equipo (SportsDB): reutilizar.
                existing = find_player(db, db_team.id, athlete.get("displayName"))
                if existing is None:
                    existing = models.Player(
                        external_id=external,
                        team_id=db_team.id,
                        name=athlete.get("displayName") or f"ESPN {athlete.get('id')}",
                        position=position,
                    )
                    db.add(existing)
                    counts["players"] += 1
            if existing.team_id is None:
                existing.team_id = db_team.id
            existing.position = existing.position or position
        db.commit()
        time.sleep(polite_seconds)
    return counts
