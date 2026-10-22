"""Motor y sesiones de base de datos."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str | None = None) -> Engine:
    """Crea un engine SQLAlchemy para la URL indicada (o la del entorno).

    En SQLite activa checks de thread y PRAGMA foreign_keys=ON.
    """
    url = database_url or os.environ.get("PICKMASTER_DATABASE_URL", "")
    if not url:
        msg = "Falta PICKMASTER_DATABASE_URL"
        raise ValueError(msg)

    kwargs: dict[str, Any] = {}
    is_sqlite = url.startswith("sqlite")
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}

    eng = create_engine(url, pool_pre_ping=not is_sqlite, **kwargs)

    if is_sqlite:

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn: sqlite3.Connection, _rec: Any) -> None:
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return eng


# Engine global de la aplicación (lazy, para que los tests puedan inyectar URL).
_engine: Engine | None = None


def setup_engine() -> Engine:
    """Engine de la app según `PICKMASTER_DATABASE_URL`."""
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def set_engine(engine: Engine) -> None:
    """Inyecta un engine (usado por tests y herramientas)."""
    global _engine
    _engine = engine


def new_session() -> sessionmaker[Session]:
    """Sessionmaker ligado al engine de la app."""
    return sessionmaker(bind=setup_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por request."""
    db = new_session()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all(engine: Engine) -> None:
    """Crea el esquema completo (Fase 1; Alembic llega en despliegue)."""
    Base.metadata.create_all(engine)
