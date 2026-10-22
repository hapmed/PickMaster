"""Modelos SQLAlchemy (Fase 1).

Tablas: teams, players, matches, player_stats, lineups, injuries,
projections, picks, pick_results, match_reports, model_runs,
contest_rules, audit_log.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app import db


def _now() -> datetime:

    return datetime.now(tz=UTC)


class PlayerPosition:
    """Catálogo de posiciones válidas."""

    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"
    ALL = (GK, DEF, MID, FWD)


class PickResultKind:
    """Resultados de evaluación de un pick (etiquetas)."""

    HIT = "hit"
    PARTIAL = "partial"
    MISS = "miss"
    NO_PLAY = "no_play"
    ALL = (HIT, PARTIAL, MISS, NO_PLAY)


class Team(db.Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    short_name: Mapped[str | None] = mapped_column(String(20))
    league: Mapped[str] = mapped_column(String(40), default="Liga MX")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Player(db.Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str] = mapped_column(String(4), index=True)
    salary: Mapped[float | None] = mapped_column(Float)  # se carga por CSV/manual
    injury_risk: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    suspended_until: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Match(db.Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    tournament: Mapped[str] = mapped_column(String(60), default="Liga MX")
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    kickoff: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|finished
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (Index("ix_matches_kickoff_status", "kickoff", "status"),)


class PlayerStat(db.Base):
    """Estadística de un jugador en un partido (historial o resultado real)."""

    __tablename__ = "player_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "match_id", name="uq_player_stat"),
        Index("ix_player_stats_match", "match_id", "started", "minutes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    minutes: Mapped[int] = mapped_column(Integer)
    started: Mapped[bool] = mapped_column(Boolean, default=False)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    shots_on_target: Mapped[int] = mapped_column(Integer, default=0)
    key_passes: Mapped[int] = mapped_column(Integer, default=0)
    tackles: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    goals_conceded: Mapped[int] = mapped_column(Integer, default=0)
    clean_sheet: Mapped[bool] = mapped_column(Boolean, default=False)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_card: Mapped[bool] = mapped_column(Boolean, default=False)
    own_goal: Mapped[int] = mapped_column(Integer, default=0)
    penalty_saved: Mapped[int] = mapped_column(Integer, default=0)
    penalty_missed: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Lineup(db.Base):
    """Alineación: probable (confirmed=False) o confirmada."""

    __tablename__ = "lineups"
    __table_args__ = (
        UniqueConstraint("match_id", "player_id", "kind", name="uq_lineup"),
        Index("ix_lineups_match", "match_id", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # probable | confirmed | out
    lineup_position: Mapped[str | None] = mapped_column(String(4))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    announced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Injury(db.Base):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # injury | suspension
    detail: Mapped[str | None] = mapped_column(Text)
    from_date: Mapped[datetime] = mapped_column(DateTime)
    to_date: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Projection(db.Base):
    """Distribución simulada de un jugador para un partido."""

    __tablename__ = "projections"
    __table_args__ = (
        UniqueConstraint("player_id", "match_id", "model_version", name="uq_projection"),
        Index("ix_projections_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(40))
    mean: Mapped[float] = mapped_column(Float)
    median: Mapped[float] = mapped_column(Float)
    p10: Mapped[float] = mapped_column(Float)
    p25: Mapped[float] = mapped_column(Float)
    p75: Mapped[float] = mapped_column(Float)
    p90: Mapped[float] = mapped_column(Float)
    minutes_expected: Mapped[float] = mapped_column(Float)
    start_probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Pick(db.Base):
    """Pick publicado por el modelo para un partido."""

    __tablename__ = "picks"
    __table_args__ = (Index("ix_picks_match", "match_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    position: Mapped[str] = mapped_column(String(4), index=True)
    projection_id: Mapped[int | None] = mapped_column(ForeignKey("projections.id"))
    expected_points: Mapped[float] = mapped_column(Float)
    target_points: Mapped[float] = mapped_column(Float)
    probability: Mapped[float] = mapped_column(Float)  # P(puntos >= target)
    p25: Mapped[float] = mapped_column(Float)
    value_per_salary: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PickResult(db.Base):
    """Evaluación post-partido de cada pick."""

    __tablename__ = "pick_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    pick_id: Mapped[int] = mapped_column(ForeignKey("picks.id"), index=True, unique=True)
    actual_points: Mapped[float] = mapped_column(Float)
    minutes: Mapped[int] = mapped_column(Integer)
    error: Mapped[float] = mapped_column(Float)  # real - esperado
    result: Mapped[str] = mapped_column(String(12), index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MatchReport(db.Base):
    """Resumen del partido: hit rate y conteos."""

    __tablename__ = "match_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True, unique=True)
    total_picks: Mapped[int] = mapped_column(Integer)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    partials: Mapped[int] = mapped_column(Integer, default=0)
    misses: Mapped[int] = mapped_column(Integer, default=0)
    no_plays: Mapped[int] = mapped_column(Integer, default=0)
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ModelRun(db.Base):
    """Trazabilidad de corridas del modelo."""

    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(40))
    run_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    metrics_json: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class ContestRuleConfig(db.Base):
    """Copias versionadas del contest_rules.json cargado."""

    __tablename__ = "contest_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(40), unique=True)
    rules_json: Mapped[str] = mapped_column(Text)
    is_provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(db.Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(40), default="worker")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class WorkerJob(db.Base):
    """Ledger del scheduler: un registro por (ciclo, partido)."""

    __tablename__ = "worker_jobs"
    __table_args__ = (
        UniqueConstraint("job_kind", "match_id", name="uq_worker_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_kind: Mapped[str] = mapped_column(String(20), index=True)  # t24|t6|t1|evaluated
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
