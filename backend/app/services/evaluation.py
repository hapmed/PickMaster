"""Evaluación post-partido: hits, parciales, fallos y no-play por pick."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.rules import score_player_stats

logger = logging.getLogger(__name__)

#: íconos para reportes por canal
ICON = {
    models.PickResultKind.HIT: "✅",
    models.PickResultKind.PARTIAL: "🟡",
    models.PickResultKind.MISS: "❌",
    models.PickResultKind.NO_PLAY: "⚪",
}


def rate_pick(
    actual_points: float,
    minutes: int,
    target_points: float,
    p25: float,
) -> tuple[str, str]:
    """(resultado, detalle) según reglas de acierto (docs/MODELO.md)."""
    if minutes == 0:
        return models.PickResultKind.NO_PLAY, "sin minutos: no corresponde como fallo del modelo"
    if actual_points >= target_points:
        return models.PickResultKind.HIT, "superó la mediana simulada"
    if actual_points >= p25:
        return models.PickResultKind.PARTIAL, "por debajo del target pero sobre p25"
    return models.PickResultKind.MISS, "por debajo de p25"


def evaluate_match(db: Session, match_id: int) -> dict[str, Any]:
    """Evalúa cada pick del partido y genera el reporte.

    Los puntos reales se calculan con las MISMAS reglas que simulan picks
    (score_player_stats). Si el partido no ha terminado devuelve `pending`.
    """
    match = db.get(models.Match, match_id)
    if match is None:
        return {"error": f"match {match_id} no existe", "state": "error"}
    if match.status != "finished":
        return {"error": "partido aún no termina", "state": "pending"}

    picks = db.scalars(
        select(models.Pick).where(models.Pick.match_id == match.id)
    ).all()
    counts: dict[str, int] = {k: 0 for k in models.PickResultKind.ALL}
    lines: dict[str, list[str]] = {k: [] for k in models.PickResultKind.ALL}

    for pick in picks:
        stat = db.scalar(
            select(models.PlayerStat).where(
                models.PlayerStat.player_id == pick.player_id,
                models.PlayerStat.match_id == match.id,
            )
        )
        if stat is None:
            result = models.PickResultKind.NO_PLAY
            actual = 0.0
            minutes = 0
            detail = "sin estadística disponible"
        else:
            actual = score_player_stats(stat)
            minutes = int(stat.minutes)
            result, detail = rate_pick(actual, minutes, pick.target_points, pick.p25)

        counts[result] += 1
        rows = db.scalars(
            select(models.Player).where(models.Player.id == pick.player_id)
        ).all()
        player_name = rows[0].name if rows else f"player#{pick.player_id}"
        lines[result].append(player_name)

        existing = db.scalar(
            select(models.PickResult).where(models.PickResult.pick_id == pick.id)
        )
        if existing is not None:
            db.delete(existing)
        db.add(
            models.PickResult(
                pick_id=pick.id,
                actual_points=round(actual, 3),
                minutes=minutes,
                error=round(actual - pick.expected_points, 3),
                result=result,
                detail=detail,
            )
        )

    total = len(picks)
    report = db.scalar(
        select(models.MatchReport).where(models.MatchReport.match_id == match.id)
    )
    if report is None:
        report = models.MatchReport(match_id=match.id)
        db.add(report)
    report.total_picks = total
    report.hits = counts[models.PickResultKind.HIT]
    report.partials = counts[models.PickResultKind.PARTIAL]
    report.misses = counts[models.PickResultKind.MISS]
    report.no_plays = counts[models.PickResultKind.NO_PLAY]
    report.hit_rate = round(counts[models.PickResultKind.HIT] / total, 4) if total else 0.0
    report.evaluated_at = now_utc()

    return {
        "state": "evaluated",
        "match_id": match.id,
        "total": total,
        "counts": counts,
        "lines": {k: {"icon": ICON[k], "players": v} for k, v in lines.items()},
        "hit_rate": report.hit_rate,
    }


def report_message(db: Session, match_id: int) -> str:
    """Texto del reporte (dashboard/telegram/email)."""
    data = evaluate_match(db, match_id)
    if data["state"] != "evaluated":
        return f"PickMaster · partido {match_id}: {data.get('error', 'sin datos')}"

    match = db.get(models.Match, match_id)
    if match is None:
        raise ValueError(f"partido {match_id} no existe")
    home = db.get(models.Team, match.home_team_id)
    away = db.get(models.Team, match.away_team_id)
    header = (
        f"PickMaster · {home.name if home else home} {match.home_goals}-{match.away_goals} "
        f"{away.name if away else ''}"
    )
    body = "\n".join(
        f"{data['lines'][k]['icon']} {label}: {', '.join(v) if v else '—'}"
        for k, label in [
            (models.PickResultKind.HIT, "Acertaron"),
            (models.PickResultKind.PARTIAL, "Parcial"),
            (models.PickResultKind.MISS, "Fallaron"),
            (models.PickResultKind.NO_PLAY, "No jugaron"),
        ]
        for v in [data["lines"][k]["players"]]
    )
    hits = data["counts"][models.PickResultKind.HIT]
    footer = f"Resultado: {hits}/{data['total']} picks acertados"
    return f"{header}\n{body}\n{footer}\n\nNo garantiza resultados. Juega con responsabilidad."


def now_utc() -> datetime:
    return datetime.now(UTC)


def summary(db: Session) -> dict[str, Any]:
    """Hit rate acumulado global (API /api/results/summary)."""
    reports = db.scalars(select(models.MatchReport)).all()
    rows = db.scalars(
        select(models.PickResult).order_by(models.PickResult.id)
    ).all()
    total = len(rows)
    hits = sum(1 for r in rows if r.result == models.PickResultKind.HIT)
    return {
        "matches_evaluated": len(reports),
        "picks_evaluated": total,
        "hits": hits,
        "partials": sum(1 for r in rows if r.result == models.PickResultKind.PARTIAL),
        "misses": sum(1 for r in rows if r.result == models.PickResultKind.MISS),
        "no_plays": sum(1 for r in rows if r.result == models.PickResultKind.NO_PLAY),
        "hit_rate": round(hits / total, 4) if total else 0.0,
    }
