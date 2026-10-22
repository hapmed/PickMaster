"""Rutas de la API (Fase 1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion import csv_loader
from app.models import Lineup, Match, MatchReport, Pick, PickResult, Player, Projection, Team
from app.projection.picks import generate_picks
from app.rules import get_rules
from app.services import evaluation

router = APIRouter(prefix="/api")


@router.get("/health")
def health(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Salud del servicio."""
    rules = get_rules()
    try:
        db.execute(select(1))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "rules": rules.status,
        "rules_provisional": rules.provisional,
        "version": "0.1.0",
        "disclaimer": "No garantiza resultados. Juega con responsabilidad.",
    }


@router.get("/rules")
def rules_state() -> dict[str, Any]:
    """Estado de las reglas del concurso cargadas."""
    rules = get_rules()
    return {
        "status": rules.status,
        "provisional": rules.provisional,
        "scoring": rules.scoring,
    }


@router.get("/matches")
def matches(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Partidos (los no terminados primero, por kickoff)."""
    rows = db.scalars(select(Match).order_by(Match.kickoff)).all()
    return {
        "matches": [
            {
                "id": m.id,
                "external_id": m.external_id,
                "tournament": m.tournament,
                "home": _team_name(db, m.home_team_id),
                "away": _team_name(db, m.away_team_id),
                "kickoff": m.kickoff.isoformat(),
                "status": m.status,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
            }
            for m in rows
        ]
    }


def _team_name(db: Session, team_id: int) -> str:
    team = db.get(Team, team_id)
    return team.name if team else f"team#{team_id}"


@router.get("/matches/{match_id}")
def match_detail(match_id: int, db: Session = Depends(get_session)) -> dict[str, Any]:
    """Detalle de un partido con sus picks y reporte si existe."""
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="partido no encontrado")
    picks_db = db.scalars(select(Pick).where(Pick.match_id == m.id)).all()
    report = db.scalar(select(MatchReport).where(MatchReport.match_id == m.id))
    return {
        "match": {
            "id": m.id,
            "home": _team_name(db, m.home_team_id),
            "away": _team_name(db, m.away_team_id),
            "kickoff": m.kickoff.isoformat(),
            "status": m.status,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
        },
        "picks": [pick_payload(db, p) for p in picks_db],
        "report": {
            "total": report.total_picks,
            "hits": report.hits,
            "partials": report.partials,
            "misses": report.misses,
            "no_plays": report.no_plays,
            "hit_rate": report.hit_rate,
        }
        if report
        else None,
    }


def why_list(pick: Pick, proj: Projection | None) -> list[str]:
    """Razones en lenguaje humano del porqué del pick (¿Por qué?)."""
    why: list[str] = []
    if proj is not None:
        why.extend(s for s in (proj.explanation or "").split("; ") if s)
        why.append(
            f"simuló {pick.expected_points:.1f} pts de media (mediana {pick.target_points:g})"
        )
        if pick.value_per_salary:
            why.append(f"valor por salario alto: {pick.value_per_salary:.2f} pts/mill$")
        if pick.probability >= 0.9:
            why.append("la simulación lo pone casi siempre arriba del target (90%+)")
        elif pick.probability >= 0.75:
            why.append("3 de 4 simulaciones lo dejan arriba del target")
    if not why:
        why.append("probabilidad por encima del umbral en Monte Carlo")
    why.append("Suma de minutos proyectados × eventos (poisson) × reglas del concurso")
    return why


def pick_payload(db: Session, p: Pick) -> dict[str, Any]:
    player = db.get(Player, p.player_id)
    return {
        "player_id": p.player_id,
        "player": player.name if player else f"player#{p.player_id}",
        "position": p.position,
        "expected_points": p.expected_points,
        "target_points": p.target_points,
        "probability": p.probability,
        "p25": p.p25,
        "value_per_salary": p.value_per_salary,
        "confidence": p.confidence,
        "reason": p.reason,
    }


@router.get("/picks")
def picks(match_id: int = Query(...), db: Session = Depends(get_session)) -> dict[str, Any]:
    """Picks del partido indicado."""
    if db.get(Match, match_id) is None:
        raise HTTPException(status_code=404, detail="partido no encontrado")
    rows = db.scalars(select(Pick).where(Pick.match_id == match_id)).all()
    if not rows:
        match = db.get(Match, match_id)
        if match is None:
            raise HTTPException(status_code=404, detail="partido no encontrado")
        generate_picks(db, match)
        db.commit()
        rows = db.scalars(select(Pick).where(Pick.match_id == match_id)).all()
    return {"match_id": match_id, "picks": [pick_payload(db, p) for p in rows]}


@router.get("/picks/top")
def top_picks(
    match_id: int = Query(...),
    max_picks: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """⭐ SELECCIÓN 5 ESTRELLAS ⭐ — picks sumamente probables (estadística + IA).

    Ranking por score = probabilidad × puntos esperados × confianza, usando
    las distribuciones Monte Carlo. Sólo entra quien supere el umbral de
    probabilidad; si nadie lo pasa devuelve el mejorоciano igualmente
    (etiqueta "riesgo Todoterreno", no "garantía").
    """
    if db.get(Match, match_id) is None:
        raise HTTPException(status_code=404, detail="partido no encontrado")
    rows = db.scalars(select(Pick).where(Pick.match_id == match_id)).all()
    if not rows:
        match = db.get(Match, match_id)
        if match is None:
            raise HTTPException(status_code=404, detail="partido no encontrado")
        generate_picks(db, match)
        db.commit()
        rows = db.scalars(select(Pick).where(Pick.match_id == match_id)).all()

    scored: list[tuple[float, Pick]] = []
    for pick in rows:
        score = pick.probability * max(pick.expected_points, 0.0) * pick.confidence
        if pick.probability >= TOP_PICK_PROBABILITY:
            scored.append((score, pick))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    elite = scored[:max_picks]

    result: list[dict[str, Any]] = []
    for score, pick in elite:
        proj = db.get(Projection, pick.projection_id) if pick.projection_id else None
        result.append(
            {
                **pick_payload(db, pick),
                "top_score": round(score, 4),
                "why": why_list(pick, proj),
                "statistics": {
                    "model": proj.model_version if proj else "v0.1-mc",
                    "mean": proj.mean if proj else None,
                    "median": proj.median if proj else None,
                    "p90": proj.p90 if proj else None,
                    "minutes_expected": proj.minutes_expected if proj else None,
                    "start_probability": proj.start_probability if proj else None,
                    "confidence": proj.confidence if proj else None,
                },
                "gold_status": "SUPER SHOT ATÓMICO"
                if pick.probability >= 0.9
                else "MUY PROGRAMABLE",
                "disclaimer": "Probabilidad estimada por simulación; nunca garantía",
            }
        )
    return {"match_id": match_id, "top_picks": result}


TOP_PICK_PROBABILITY = 0.75


@router.get("/lineups")
def lineups(
    match_id: int = Query(...), db: Session = Depends(get_session)
) -> dict[str, Any]:
    """Alineaciones/convocatorias por equipo (chibis a la vista).

    Devuelve roster disponible por team; kind probable = convocatoria
    estimada. NO confundir con alineación confirmada (esa llega en T-1h).
    """
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="partido no encontrado")
    rows = db.execute(
        select(Lineup, Player)
        .join(Player, Player.id == Lineup.player_id)
        .where(Lineup.match_id == match_id)
        .filter(Lineup.kind.in_(["probable", "confirmed"]))
        .order_by(Lineup.kind.desc(), Player.position, Player.name)
    ).all()

    players_by_team: dict[int, dict[str, Any]] = {}
    for _row, player in rows:
        bucket = players_by_team.setdefault(
            player.team_id or 0,
            {"team": _team_name(db, player.team_id or 0), "kind": "probable", "players": []},
        )
        bucket["players"].append(
            {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "salary": player.salary,
            }
        )
    teams = db.scalars(
        select(Team).where(Team.id.in_([m.home_team_id, m.away_team_id]))
    ).all()

    return {
        "match_id": match_id,
        "home": _team_name(db, m.home_team_id),
        "away": _team_name(db, m.away_team_id),
        "kind": "probable",
        "note": "convocatoria estimada del roster; sin XI confirmado",
        "teams": [
            players_by_team.get(t.id, {"team": t.name, "kind": "probable", "players": []})
            for t in teams
        ],
    }


@router.get("/players/{player_id}/projection")
def player_projection(
    player_id: int, match_id: int = Query(...), db: Session = Depends(get_session)
) -> dict[str, Any]:
    """Proyección más reciente del jugador para un partido."""
    row = db.scalars(
        select(Projection)
        .where(Projection.player_id == player_id, Projection.match_id == match_id)
        .order_by(Projection.created_at.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="sin proyección; genera picks primero")
    return {
        "player_id": row.player_id,
        "match_id": row.match_id,
        "model": row.model_version,
        "mean": row.mean,
        "median": row.median,
        "p10": row.p10,
        "p25": row.p25,
        "p75": row.p75,
        "p90": row.p90,
        "minutes_expected": row.minutes_expected,
        "start_probability": row.start_probability,
        "confidence": row.confidence,
        "explanation": row.explanation,
    }


@router.get("/results")
def results(match_id: int = Query(...), db: Session = Depends(get_session)) -> dict[str, Any]:
    """Resultados por pick de un partido (evaluación o pending)."""
    if db.get(Match, match_id) is None:
        raise HTTPException(status_code=404, detail="partido no encontrado")
    rows = db.execute(
        select(PickResult, Pick)
        .join(Pick, Pick.id == PickResult.pick_id)
        .where(Pick.match_id == match_id)
    ).all()
    return {
        "match_id": match_id,
        "results": [
            {
                "pick_id": pr.pick_id,
                "player_id": pick.player_id,
                "result": pr.result,
                "actual_points": pr.actual_points,
                "minutes": pr.minutes,
                "error": pr.error,
                "detail": pr.detail,
            }
            for pr, pick in rows
        ],
    }


@router.get("/results/summary")
def results_summary(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Hit rate acumulado global."""
    return evaluation.summary(db)


@router.get("/backtest")
def backtest(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Resumen de evaluación histórica (placeholder de Fase 1)."""
    summary = evaluation.summary(db)
    return {
        "note": "backtest completo en Fase 1 (mae/brier por jornada): ver CLI",
        **summary,
    }


@router.post("/admin/evaluate")
def admin_evaluate(
    match_id: int = Query(...), db: Session = Depends(get_session)
) -> dict[str, Any]:
    """Evalúa los picks de un partido terminado."""
    out = evaluation.evaluate_match(db, match_id)
    if out.get("state") == "error":
        raise HTTPException(status_code=404, detail=out["error"])
    db.commit()
    return out


@router.post("/admin/refresh")
def admin_refresh(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Regenera picks de partidos próximos y adjunta datos por CSV si existen."""
    from pathlib import Path

    loaded = {}
    data_dir = Path("data")
    if data_dir.exists():
        loaded = csv_loader.load_all(data_dir)

    upcoming = db.scalars(select(Match).where(Match.status != "finished")).all()
    generated = []
    for m in upcoming:
        generate_picks(db, m)
        generated.append(m.id)
    db.commit()
    return {"csv_loaded": loaded, "picks_regenerated_for": generated}
