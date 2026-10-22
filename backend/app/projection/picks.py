"""Generación de proyecciones y picks por partido (motor v0.1 Monte Carlo)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.projection import features as feats_module
from app.projection import simulate as sim
from app.rules import Rules, get_rules

logger = logging.getLogger(__name__)

MODEL_VERSION = "v0.1-mc"

CONFIDENCE_WEIGHTS = dict(games=0.5, lineup=0.3, injury=0.2)


def _rng_for(match: models.Match, player_id: int) -> np.random.Generator:
    """RNG reproducible por (partido, jugador)."""
    seed = hashlib.sha256(f"{match.id}:{player_id}:{MODEL_VERSION}".encode()).hexdigest()
    return np.random.default_rng(int(seed[:16], 16))


@dataclass
class PlayerProjection:
    """Resultado de la simulación de un jugador."""

    player_id: int
    position: str
    moments: dict[str, float]
    minutes_expected: float
    start_probability: float
    confidence: float
    explanation: str


def collect_match_players(db: Session, match: models.Match) -> list[models.Player]:
    """Jugadores de ambos equipos (excluye 'out' probables)."""
    player_rows = db.execute(
        select(models.Player).where(
            models.Player.team_id.in_([match.home_team_id, match.away_team_id])
        )
    ).scalars().all()

    outs = _out_players(db, match)
    return [p for p in player_rows if p.id not in outs]


def _out_players(db: Session, match: models.Match) -> set[int]:
    rows = db.execute(
        select(models.Lineup.player_id).where(
            models.Lineup.match_id == match.id,
            models.Lineup.kind == "out",
        )
    ).all()
    return {int(row[0]) for row in rows}


def _lineup_confirmed(db: Session, match: models.Match) -> bool:
    row = db.execute(
        select(models.Lineup).where(
            models.Lineup.match_id == match.id,
            models.Lineup.kind == "confirmed",
        )
    ).first()
    return row is not None


def _in_lineup(db: Session, match: models.Match, player_id: int, kind: str) -> bool:
    row = db.execute(
        select(models.Lineup).where(
            models.Lineup.match_id == match.id,
            models.Lineup.player_id == player_id,
            models.Lineup.kind == kind,
        )
    ).first()
    return row is not None


def build_confidence(feat: feats_module.PlayerFeatures, lineup_ok: bool, injured: bool) -> float:
    """Confianza 0..1: calidad de datos, estado de alineaciones y riesgo."""
    c_games = min(feat.games / 10.0, 1.0)
    c_lineup = 0.9 if lineup_ok else 0.5
    c_inj = 0.4 if injured else 1.0
    return float(
        c_games * CONFIDENCE_WEIGHTS["games"]
        + c_lineup * CONFIDENCE_WEIGHTS["lineup"]
        + c_inj * CONFIDENCE_WEIGHTS["injury"]
    )


def build_explanation(
    feat: feats_module.PlayerFeatures, rival_factor: float, lineup_ok: bool
) -> str:
    bits: list[str] = []
    p_start = sim.start_probability(feat)
    if p_start >= 0.7:
        bits.append("titular frecuente")
    elif p_start >= 0.4:
        bits.append("titularidad incierta")
    else:
        bits.append("probable suplente")
    if rival_factor > 1.15:
        bits.append("rival defensivamente débil")
    elif rival_factor < 0.85:
        bits.append("rival defensivamente fuerte")
    if feat.injured:
        bits.append("molestia reportada: baja de minutos")
    if not lineup_ok:
        bits.append("alineaciones sin confirmar")
    if feat.games < 3:
        bits.append("pocos datos históricos")
    return "; ".join(bits)


def project_match(
    db: Session, match: models.Match, rules: Rules | None = None
) -> list[PlayerProjection]:
    """Proyecta cada jugador de la convocatoria del partido."""
    rules = rules or get_rules()
    projections: list[PlayerProjection] = []
    lineup_ok = _lineup_confirmed(db, match)

    for player in collect_match_players(db, match):
        feat = feats_module.player_features(db, player, match)
        rival_factor = sim.opponent_goal_factor(db, match, player.team_id)
        rates, downgrade = sim.event_rates(feat, rival_factor)
        if not _in_lineup(db, match, player.id, "confirmed"):
            downgrade *= 0.9  # aún sin confirmar: leve castigo

        points = sim.simulate(
            feat, rates, downgrade, rules, n_sims=settings.mc_sims, rng=_rng_for(match, player.id)
        )
        moments = sim.summarize(points)
        proj = PlayerProjection(
            player_id=player.id,
            position=player.position,
            moments=moments,
            minutes_expected=float(np.clip(
                sim.minutes_distribution(feat)[0] * sim.start_probability(feat), 0, 90
            )),
            start_probability=sim.start_probability(feat),
            confidence=build_confidence(feat, lineup_ok, feat.injured),
            explanation=build_explanation(feat, rival_factor, lineup_ok),
        )
        projections.append(proj)

    return projections


def save_projections(
    db: Session, match: models.Match, projections: list[PlayerProjection]
) -> list[models.Projection]:
    """Persiste proyecciones (borra las del mismo modelo re-generadas)."""
    existing = db.execute(
        select(models.Projection).where(
            models.Projection.match_id == match.id,
            models.Projection.model_version == MODEL_VERSION,
        )
    ).scalars().all()
    for row in existing:
        db.delete(row)
    db.flush()  # asegura que UNIQUE (player, match, version) no choque en el mismo flush

    rows: list[models.Projection] = []
    for p in projections:
        row = models.Projection(
            player_id=p.player_id,
            match_id=match.id,
            model_version=MODEL_VERSION,
            mean=p.moments["mean"],
            median=p.moments["median"],
            p10=p.moments["p10"],
            p25=p.moments["p25"],
            p75=p.moments["p75"],
            p90=p.moments["p90"],
            minutes_expected=p.minutes_expected,
            start_probability=p.start_probability,
            confidence=p.confidence,
            explanation=p.explanation,
        )
        db.add(row)
        rows.append(row)
    return rows


def generate_picks(
    db: Session,
    match: models.Match,
    rules: Rules | None = None,
    top_per_position: int | None = None,
) -> list[models.Pick]:
    """Proyecta y elige top picks por posición, con confianza y motivo."""
    rules = rules or get_rules()
    picks_cfg = top_per_position or int(
        rules.picks.get("top_n_per_position", 3)  # type: ignore[call-overload]
    )

    projections = project_match(db, match, rules)
    proj_rows = save_projections(db, match, projections)

    # borra picks previos del partido para regenerar
    stale_rows = db.execute(
        select(models.Pick).where(models.Pick.match_id == match.id)
    ).scalars()
    for stale in stale_rows.all():
        db.delete(stale)

    picks_rows: list[models.Pick] = []
    for pos in models.PlayerPosition.ALL:
        in_position: list[tuple[PlayerProjection, int]] = []
        for p, row in zip_as_pairs(projections, proj_rows):
            if p.position == pos:
                in_position.append((p, row.id))
        in_position.sort(key=lambda pair: pair[0].moments["mean"], reverse=True)

        for proj, proj_row_id in in_position[:picks_cfg]:
            target = proj.moments[target_moment_key(rules)]
            partial = proj.moments["p25"]
            prob = prob_over_target(proj.moments, target)
            player = db.get(models.Player, proj.player_id)
            value = (
                round(proj.moments["mean"] / max(player.salary or 0.0, 1.0), 4)
                if player and player.salary
                else None
            )
            picks_rows.append(
                models.Pick(
                    match_id=match.id,
                    player_id=proj.player_id,
                    position=pos,
                    projection_id=proj_row_id,
                    expected_points=round(proj.moments["mean"], 3),
                    target_points=round(target, 3),
                    probability=round(prob, 4),
                    p25=round(partial, 3),
                    value_per_salary=value,
                    confidence=round(proj.confidence, 3),
                    reason=build_reason(proj),
                )
            )
    for pick_row in picks_rows:
        db.add(pick_row)
    return picks_rows


def zip_as_pairs(
    projections: list[PlayerProjection], proj_rows: list[models.Projection]
) -> list[tuple[PlayerProjection, models.Projection]]:
    """Empareja cada proyección calculada con su fila guardada (mismo orden)."""
    return list(zip(projections, proj_rows, strict=True))


#: Clave del diccionario de momentos según el `target` configurado.
TARGET_KEYS = {"p50": "median", "p25": "p25", "p75": "p75", "p90": "p90", "mean": "mean"}


def target_moment_key(rules: Rules) -> str:
    """Percentil usado como `target_points` (default p50 → mediana)."""
    raw = str(rules.picks.get("target", "p50")).lower()
    return TARGET_KEYS.get(raw, "median")


def prob_over_target(moments: dict[str, float], target: float) -> float:
    """Probabilidad aproximada de superar el target por interpolación de percentiles.

    Aproximación conservadora por tramos; en Fase 4 se calcula con la muestra
    completa de Monte Carlo.
    """
    if target <= moments["p10"]:
        return 0.95
    if target <= moments["p25"]:
        return 0.88
    if target <= moments["p75"]:
        return 0.55
    if target <= moments["p90"]:
        return 0.25
    return 0.10


def build_reason(proj: PlayerProjection) -> str:
    """Motivo legible del pick (versión compacta)."""
    explanation = proj.explanation or ""
    rango = f"{proj.moments['p10']:.1f}-{proj.moments['p90']:.1f}"
    details = f"media {proj.moments['mean']:.1f} pts, rango 10-90: {rango}"
    return f"{details} · {explanation}" if explanation else details


def as_dict(pick: models.Pick) -> dict[str, object]:
    """Serialización ligera para la API."""
    data = {
        "id": pick.id,
        "match_id": pick.match_id,
        "player_id": pick.player_id,
        "position": pick.position,
        "expected_points": pick.expected_points,
        "target_points": pick.target_points,
        "probability": pick.probability,
        "p25": pick.p25,
        "value_per_salary": pick.value_per_salary,
        "confidence": pick.confidence,
        "reason": pick.reason,
    }
    return data
