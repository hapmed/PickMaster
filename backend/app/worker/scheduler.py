"""Scheduler Fase 3: ciclos T-24h / T-6h / T-1h y evaluación post-partido.

Bloques vencidos se marcan en la tabla `worker_jobs` para no repetirlos.
Notifica por el canal configurado (dashboard siempre; Telegram/email con env).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ingestion import csv_loader
from app.notify import notify
from app.projection.picks import generate_picks
from app.services import evaluation

logger = logging.getLogger("worker")


def _espn_enabled() -> bool:
    """ESPN en scheduler solo si se activa (prod compose; tests sin red)."""
    from app.config import get_settings

    return get_settings().espn_schedule == "1"

# Ventanas previas al kickoff (horas antes); orden cronológico.
WINDOWS: tuple[tuple[str, int], ...] = (("t24", 24), ("t6", 6), ("t1", 1))
# Minutos post-kickoff para esperar estadísticas finales y reintentar.
POST_RETRY_MINUTES = (60, 180)


def _aware(dt: datetime) -> datetime:
    """Normaliza datetimes naif (SQLite) aAware UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


class Scheduler:
    """Un ticker con ledger `worker_jobs` (una corrida por kind/partido)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def done(self, kind: str, match_id: int) -> bool:
        return (
            self.db.scalar(
                select(models.WorkerJob).where(
                    models.WorkerJob.job_kind == kind,
                    models.WorkerJob.match_id == match_id,
                )
            )
            is not None
        )

    def mark(self, kind: str, match_id: int) -> None:
        self.db.add(models.WorkerJob(job_kind=kind, match_id=match_id))
        self.db.flush()  # autoflush está off: visibles en este session de inmediato

    def ticker(self, now: datetime) -> list[str]:
        """Una pasada: ejecuta las ventanas vencidas de partidos próximos."""
        ran: list[str] = []
        upcoming = self.db.scalars(
            select(models.Match).where(models.Match.status != "finished")
        ).all()
        for match in upcoming:
            kickoff = _aware(match.kickoff)
            mins_a_traer = (kickoff - now).total_seconds() / 60
            for kind, hours in WINDOWS:
                if self.done(kind, match.id):
                    continue
                if mins_a_traer <= hours * 60:
                    try:
                        self.run_window(kind, match)
                    except Exception:  # noqa: BLE001
                        logger.exception("ventana %s falló en partido %s", kind, match.id)
                        self.db.rollback()
                        continue
                    self.mark(kind, match.id)
                    ran.append(kind)
        return ran

    def run_window(self, kind: str, match: models.Match) -> None:
        """ESPN fixtures (t24) + CSV si existe + regenera picks + notifica."""
        if kind == "t24" and _espn_enabled():
            # Agenda al día: programación ESPN de la semana.
            try:
                from app.ingestion import espn

                espn.ingest_fixtures(self.db, days_back=2, days_forward=7)
            except Exception:  # noqa: BLE001
                logger.exception("fixtures ESPN fallaron para partido %s", match.id)
                self.db.rollback()
        try:
            csv_loader.load_all("data")
        except Exception as exc:  # noqa: BLE001
            logger.warning("CSV en window %s falló: %s", kind, exc)
        generate_picks(self.db, match)
        self.db.commit()
        top = [
            p
            for p in self.db.scalars(
                select(models.Pick).where(models.Pick.match_id == match.id)
            ).all()
            if p.probability >= 0.75
        ][:3]
        lines = [f"PICKMASTER · {kind.upper()} · partido {match.id}"]
        lines.extend(
            f"• [{p.position}] {p.player_id}: {p.expected_points:.1f} pts "
            f"(prob {p.probability:.0%})"
            for p in top
        )
        notify("\n".join(lines), channel="dashboard")

    def evaluate_loop(self, now: datetime) -> list[int]:
        """Evalúa partidos con ≥60 min desde el kickoff (reintento implícito)."""
        ran: list[int] = []
        matches = self.db.scalars(
            select(models.Match).where(models.Match.status == "finished")
        ).all()
        for match in matches:
            kickoff = _aware(match.kickoff)
            minutos = (now - kickoff).total_seconds() / 60
            if minutos < POST_RETRY_MINUTES[0] or self.done("evaluated", match.id):
                continue
            if _espn_enabled():
                try:
                    from app.ingestion import espn

                    stored = espn.ingest_results_for_match(self.db, match)
                    self.db.commit()
                    if stored:
                        logger.info("ESPN: %d stats de partido %s", stored, match.id)
                except Exception:  # noqa: BLE001
                    logger.exception("ESPN stats falló en partido %s", match.id)
                    self.db.rollback()
            out = evaluation.evaluate_match(self.db, match.id)
            self.db.commit()
            self.mark("evaluated", match.id)
            ran.append(match.id)
            if out.get("state") == "evaluated":
                notify(evaluation.report_message(self.db, match.id), channel="dashboard")
        return ran


def run_forever(interval_seconds: float = 60.0) -> None:
    """Loop principal del contenedor worker (1 minuto entre pasadas)."""
    from app.db import new_session, setup_engine

    setup_engine()
    logger.info("Scheduler arrancando; pasadas cada %ss", interval_seconds)
    while True:
        session = new_session()()
        try:
            sched = Scheduler(session)
            ran_windows = sched.ticker(datetime.now(UTC))
            evaluar = sched.evaluate_loop(datetime.now(UTC))
            session.commit()
            if ran_windows:
                logger.info("ventanas corridas: %s", ran_windows)
            if evaluar:
                logger.info("evaluados: %s", evaluar)
        except Exception:
            session.rollback()
            logger.exception("ticker falló")
        finally:
            session.close()
        time.sleep(interval_seconds)
