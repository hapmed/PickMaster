"""Tests del scheduler (ventanas T-24h/T-6h/T-1h y evaluación post-partido)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.worker.scheduler import WINDOWS, Scheduler


def _match(db: Session, kickoff: datetime, status: str = "scheduled") -> models.Match:
    home = db.query(models.Team).first()
    away = db.get(models.Team, home.id + 1) or home
    m = models.Match(
        home_team_id=home.id, away_team_id=away.id, kickoff=kickoff, status=status
    )
    db.add(m)
    db.flush()
    return m


def test_windows_marked_for_close_match(db: Session) -> None:
    """A menos de 1h del partido: t24, t6 y t1 quedan marcadas en el ledger."""
    now = datetime.now(UTC)
    match = _match(db, now + timedelta(minutes=30))
    sched = Scheduler(db)
    ran = sched.ticker(now)
    assert ran, "debe ejecutar al menos las ventanas de los partidos vencidos"
    for kind in ("t24", "t6", "t1"):
        assert sched.done(kind, match.id), f"{kind} debió quedar marcado"


def test_no_repeat_after_mark(db: Session) -> None:
    """El ledger evita repetir corridas en la próxima pasada del ticker."""
    now = datetime.now(UTC)
    _match(db, now + timedelta(minutes=10))
    sched = Scheduler(db)
    first = sched.ticker(now)
    assert first, "primera pasada debe ejecutar algo"
    assert sched.ticker(now) == [], "segunda pasada no debe repetir acciones"


def test_far_kickoff_no_own_actions(db: Session) -> None:
    """Con kickoff a T-48h, las ventanas del nuevo partido NO se marcan."""
    now = datetime.now(UTC)
    sched = Scheduler(db)
    sched.ticker(now)  # consume las ventanas vencidas (ej. partido demo)
    far = _match(db, now + timedelta(hours=48))
    sched.ticker(now)
    assert not sched.done("t24", far.id)


def test_evaluate_after_one_hour(db: Session) -> None:
    """Tras dos pasadas todo partido terminado queda evaluado (ledger evita repetir)."""
    now = datetime.now(UTC)
    for _ in range(2):
        sched = Scheduler(db)
        sched.evaluate_loop(now)
    sched = Scheduler(db)
    assert sched.evaluate_loop(now) == []


def test_windows_constant_sorted() -> None:
    assert sorted((h for _k, h in WINDOWS), reverse=True) == [h for _k, h in WINDOWS]
