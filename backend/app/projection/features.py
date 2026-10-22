"""Features del modelo, con protección contra fuga de datos.

Toda función aquí usa **sólo información disponible antes del kickoff** del
partido objetivo: partidos `finished` con fecha estrictamente anterior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

INJURY_DOWNGRADE = 0.35  # multiplicador de minutos si hay lesión/sanción activa


@dataclass
class PlayerFeatures:
    """Agregados del jugador hasta el corte temporal."""

    player_id: int
    position: str
    games: int = 0
    starts: int = 0
    minutes_series: list[int] = field(default_factory=list)
    per90: dict[str, float] = field(default_factory=dict)
    team_id: int | None = None
    injured: bool = False


def matches_before(db: Session, kickoff: datetime) -> set[int]:
    """IDs de partidos terminados antes del kickoff objetivo (corte anti-fuga)."""
    rows = db.execute(
        select(models.Match.id).where(
            models.Match.status == "finished",
            models.Match.kickoff < kickoff,
        )
    ).all()
    return {int(row[0]) for row in rows}


def player_features(db: Session, player: models.Player, match: models.Match) -> PlayerFeatures:
    """Features del jugador: minutos, titularidad y tasas por 90 antes del corte."""
    cutoff = matches_before(db, match.kickoff)
    rows: list[tuple[models.PlayerStat, int]] = []
    if cutoff:
        stats = db.execute(
            select(models.PlayerStat)
            .where(models.PlayerStat.player_id == player.id)
            .order_by(models.PlayerStat.id.desc())
        ).all()
        seen: set[int] = set()
        for st, in stats:  # cada fila es 1-tupla
            if st.match_id in cutoff and st.match_id not in seen:
                seen.add(st.match_id)
                rows.append((st, st.match_id))

    minutes_series = [int(r.minutes) for r, _ in rows[:12]]
    starts = sum(1 for r, _ in rows if r.started)

    # minutos acumulados para tasas por 90 (cota mínima evita división por 0)
    total_minutes = sum(minutes_series)

    from collections import defaultdict

    totals: dict[str, int] = defaultdict(int)
    for r, _ in rows[:12]:
        totals["goals"] += r.goals
        totals["assists"] += r.assists
        totals["shots_on_target"] += r.shots_on_target
        totals["key_passes"] += r.key_passes
        totals["tackles"] += r.tackles
        totals["saves"] += r.saves
        totals["own_goal"] += r.own_goal

    per90 = {
        key: (value / max(total_minutes, 1) * 90.0) for key, value in totals.items()
    }

    injured = _is_injured(db, player, match.kickoff)
    return PlayerFeatures(
        player_id=player.id,
        position=player.position,
        games=len(minutes_series),
        starts=starts,
        minutes_series=minutes_series,
        per90=per90,
        team_id=player.team_id,
        injured=injured,
    )


def _is_injured(
    db: Session, player: models.Player, kickoff: datetime
) -> bool:
    """Lesión o sanción activa en el kickoff objetivo."""
    rows = db.execute(
        select(models.Injury).where(models.Injury.player_id == player.id)
    ).all()
    for inj, in rows:
        if inj.from_date <= kickoff and (inj.to_date is None or inj.to_date >= kickoff):
            return True
    return bool(player.suspended_until and player.suspended_until >= kickoff.strftime("%Y-%m-%d"))
