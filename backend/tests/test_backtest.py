"""Tests del backtest de Fase 4 (mae/calibración/brier) sobre BD demo."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelRun
from app.services import backtest as bt


def test_run_backtest_metrics(db: Session) -> None:
    metrics: dict[str, Any] = bt.run_backtest(
        db, validation_matches=2, save=True
    )
    assert metrics["state"] == "evaluated"
    assert metrics["validation_matches"] == 2
    assert metrics["rows"] > 0
    assert metrics["mae_points"] >= 0
    assert metrics["mae_baseline"] >= 0
    for pos in ("GK", "DEF", "MID", "FWD"):
        assert pos in metrics["mae_points_by_position"]
    # coberturas en rango válido
    for value in metrics["quantile_coverage"].values():
        assert 0.0 <= value <= 1.0
    expected = metrics["quantile_coverage_expected"]
    assert expected["p25"] == 0.75 and expected["p90"] == 0.1
    # brier por umbral en [0,1]
    for value in metrics["brier_by_threshold"].values():
        assert 0.0 <= value <= 1.0
    # persistido en model_runs
    run = db.scalars(
        select(ModelRun).where(ModelRun.version == bt.MODEL_VERSION)
    ).first()
    assert run is not None
    latest = bt.latest_run(db)
    assert latest is not None and latest["state"] == "evaluated"


def test_backtest_needs_history() -> None:
    # BD vacía → pending honesto (sin sesión demo)
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    from app import models
    from app.db import Base, set_engine

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    set_engine(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    rows = session.scalars(sa.select(models.Match)).all()
    assert not rows, "BD vacía sin semilla"
    out = bt.run_backtest(session)
    assert out["state"] == "pending"
    session.close()
    engine.dispose()


def test_prob_interpolation_edges() -> None:
    q = {0.9: 1.0, 0.75: 3.0, 0.5: 5.0, 0.25: 7.0, 0.1: 9.0}
    assert bt._predicted_prob_at(0.5, q) == 0.9  # <= p10
    assert bt._predicted_prob_at(5.0, q) == 0.5  # mediana exacta
    assert bt._predicted_prob_at(20.0, q) == 0.0  # muy por encima de p90: 0
    # apenas sobre p90 la cola aún es ~0.1 y decae hacia 0
    assert 0.0 < bt._predicted_prob_at(9.1, q) < 0.1
    assert bt._predicted_prob_at(7.0, q) == 0.25  # p75 exacto
    interpolado = bt._predicted_prob_at(8.0, q)
    assert 0.1 < interpolado < 0.25  # entre p75 y p90
