"""Fase 4 — Backtest reproducible con corte anti-fuga de datos.

Cómo funciona:
1. Se parten los partidos `finished` por fecha: los últimos N son la
   ventana de validación, el resto entrenó los features (los features ya
   filtran por kickoff: los picks de un partido pasado SÓLO ven historia
   estrictamente anterior).
2. Se regenera la proyección de cada jugador de esos partidos, se compara
   con los puntos reales (mismas reglas de puntaje que en producción).
3. Métricas: MAE de puntos (global y por posición, jugando ≥1 minuto),
   baseline con la mediana global, MAE de minutos, calibración de
   percentiles (cobertura observada de p25/p50/p75/p90), Brier por
   umbral y calibración de buckets de titularidad.
4. El resultado se persiste en `model_runs` (JSON) y lo sirve
   `/api/backtest`.

Nota honesta: P(X>=T) se aproxima por interpolación entre percentiles
guardados (no guardamos las 10k simulaciones por jugador).
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.projection import picks as picks_mod
from app.rules import score_player_stats

logger = logging.getLogger(__name__)

MODEL_VERSION = "v0.2-backtest"

# Umbrales para Brier (puntos fantasy provisionales)
BRIER_THRESHOLDS: tuple[float, ...] = (4.0, 6.0, 8.0)

# Cobertura esperada de cada percentil (1 - quantil)
COVERAGE_EXPECTED: dict[str, float] = {"p25": 0.75, "median": 0.5, "p75": 0.25, "p90": 0.1}

# Buckets de probabilidad de titularidad
START_BINS: tuple[tuple[float, float], ...] = ((0.0, 0.5), (0.5, 0.8), (0.8, 1.01))


@dataclass
class _Row:
    """Fila de validación: predicción vs realidad de un jugador."""

    position: str
    mean: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float
    minutes_expected: float
    start_probability: float
    actual_points: float
    actual_minutes: int
    actual_started: bool


def _predicted_prob_at(points: float, quantiles: dict[float, float]) -> float:
    """P(X>=points) interpolando entre percentiles conocidos.

    quantiles: {0.9: p10, 0.75: p25, 0.5: p50, 0.25: p75, 0.1: p90}.
    Debajo de p10 vale 0.9; por encima de p90 decae linealmente a 0 en el
    ancho dado por (p90 - p75).
    """
    if points <= quantiles[0.9]:
        return 0.9
    p90, p75 = quantiles[0.1], quantiles[0.25]
    if points > p90:
        width = p90 - p75
        if width > 0:
            tail = (points - p90) / width
            return max(0.0, round(0.1 * (1.0 - min(tail, 1.0)), 4))
        return 0.05
    edges = [0.9, 0.75, 0.5, 0.25, 0.1]
    values = [quantiles[q] for q in edges]
    for i in range(len(edges) - 1):
        if values[i] <= points < values[i + 1]:
            span = values[i + 1] - values[i]
            if span <= 0:
                continue
            t = (points - values[i]) / span
            return edges[i] + t * (edges[i + 1] - edges[i])
    return 0.5


def _row_from_projection(proj: picks_mod.PlayerProjection) -> _Row:
    return _Row(
        position=proj.position,
        mean=proj.moments["mean"],
        median=proj.moments["median"],
        p10=proj.moments["p10"],
        p25=proj.moments["p25"],
        p75=proj.moments["p75"],
        p90=proj.moments["p90"],
        minutes_expected=proj.minutes_expected,
        start_probability=proj.start_probability,
        actual_points=0.0,
        actual_minutes=0,
        actual_started=False,
    )


def _validation_rows(
    db: Session, validation_matches: int
) -> tuple[list[models.Match], list[_Row]]:
    """Regenera proyecciones de la ventana y adjunta la realidad."""
    finished: list[models.Match] = list(
        db.scalars(
            select(models.Match)
            .where(models.Match.status == "finished")
            .order_by(models.Match.kickoff)
        ).all()
    )
    val = finished[-min(validation_matches, len(finished)) :]
    rows: list[_Row] = []
    for match in val:
        stats = db.scalars(
            select(models.PlayerStat).where(models.PlayerStat.match_id == match.id)
        ).all()
        by_player = {st.player_id: st for st in stats}
        for proj in picks_mod.project_match(db, match):
            st = by_player.get(proj.player_id)
            if st is None:
                continue  # sin datos: no computable
            row = _row_from_projection(proj)
            row.actual_points = score_player_stats(st)
            row.actual_minutes = int(st.minutes)
            row.actual_started = bool(st.started)
            rows.append(row)
    return val, rows


def run_backtest(
    db: Session,
    *,
    validation_matches: int = 12,
    save: bool = True,
) -> dict[str, Any]:
    """Corrida completa del backtest; devuelve métricas y guarda model_run."""
    finished_total = db.scalar(
        select(models.Match.id).where(models.Match.status == "finished").limit(1)
    )
    if finished_total is None:
        return {
            "error": "histórico insuficiente (menos de 5 partidos finished)",
            "state": "pending",
        }
    val_matches, rows = _validation_rows(db, validation_matches)
    playing = [r for r in rows if r.actual_minutes > 0]
    if not playing:
        return {
            "error": "sin player_stats en la ventana de validación",
            "state": "pending",
        }

    # ---- MAE de puntos (mediana del modelo vs realidad) -------------------
    mae_all = statistics.mean(abs(r.median - r.actual_points) for r in playing)
    mae_position: dict[str, float] = {}
    for pos in models.PlayerPosition.ALL:
        group = [r for r in playing if r.position == pos]
        mae_position[pos] = (
            round(statistics.mean(abs(r.median - r.actual_points) for r in group), 3)
            if group
            else 0.0
        )
    global_med = statistics.median(r.actual_points for r in playing)
    mae_baseline = statistics.mean(abs(global_med - r.actual_points) for r in playing)

    # ---- MAE de minutos ----------------------------------------------------
    mae_minutes = statistics.mean(abs(r.minutes_expected - r.actual_minutes) for r in rows)

    # ---- Calibración percentilística ---------------------------------------
    coverage: dict[str, float] = {
        key: round(
            statistics.mean(float(r.actual_points >= getattr(r, key)) for r in playing),
            3,
        )
        for key in ("p25", "median", "p75", "p90")
    }

    # ---- Brier por umbral ---------------------------------------------------
    brier: dict[str, float] = {}
    for thr in BRIER_THRESHOLDS:
        preds: list[float] = []
        outcomes: list[float] = []
        for r in playing:
            q = {0.9: r.p10, 0.75: r.p25, 0.5: r.median, 0.25: r.p75, 0.1: r.p90}
            preds.append(_predicted_prob_at(thr, q))
            outcomes.append(1.0 if r.actual_points >= thr else 0.0)
        brier[str(int(thr))] = round(
            statistics.mean((p - o) ** 2 for p, o in zip(preds, outcomes, strict=False)),
            4,
        )

    # ---- Calibración de buckets de titularidad ------------------------------
    start_calibration: list[dict[str, Any]] = []
    for lo, hi in START_BINS:
        group = [r for r in rows if lo <= r.start_probability < hi]
        if group:
            start_calibration.append(
                {
                    "desde": lo,
                    "hasta": hi,
                    "observado": round(
                        statistics.mean(float(r.actual_started) for r in group), 3
                    ),
                    "n": len(group),
                }
            )

    metrics: dict[str, Any] = {
        "state": "evaluated",
        "validation_matches": len(val_matches),
        "rows": len(rows),
        "players_with_minutes": len(playing),
        "mae_points": round(mae_all, 3),
        "mae_points_by_position": mae_position,
        "mae_baseline": round(mae_baseline, 3),
        "mae_minutes": round(mae_minutes, 1),
        "quantile_coverage": coverage,
        "quantile_coverage_expected": COVERAGE_EXPECTED,
        "brier_by_threshold": brier,
        "start_probability_calibration": start_calibration,
    }

    if save:
        run = models.ModelRun(
            version=MODEL_VERSION,
            metrics_json=json.dumps(metrics),
            notes=f"backtest ventana {len(val_matches)} partidos",
        )
        db.add(run)
        db.flush()
    return metrics


def latest_run(db: Session) -> dict[str, Any] | None:
    """Último model_run persistido del backtest (para la API)."""
    run = db.scalars(
        select(models.ModelRun)
        .where(models.ModelRun.version == MODEL_VERSION)
        .order_by(models.ModelRun.run_at.desc())
        .limit(1)
    ).first()
    if run is None:
        return None
    metrics: dict[str, Any] = json.loads(run.metrics_json or "{}")
    metrics["run_at"] = None
    if run.run_at is not None:
        # naive (SQLite) o aware (Postgres): uniformar a naive
        ran = run.run_at
        if ran.tzinfo is not None:
            ran = ran.replace(tzinfo=None)
        metrics["run_at"] = ran.replace(microsecond=0).isoformat()
    return metrics
