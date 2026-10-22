"""Fixtures de tests: BD SQLite en memoria con esquema, datos demo y reglas fijas."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, set_engine
from app.ingestion.demo_seed import seed_demo
from app.rules import DEFAULT_SCORING, Rules

TEST_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture(name="rules")
def fixture_rules() -> Rules:
    """Reglas provisionales explícitas e iguales para todo el test."""
    return Rules(
        status="PROVISIONAL (tests)",
        scoring=dict(DEFAULT_SCORING),
        picks={"target": "p50", "partial_threshold": "p25", "top_n_per_position": 3},
        provisional=True,
    )


@pytest.fixture(autouse=True)
def _patched_rules(monkeypatch: pytest.MonkeyPatch, rules: Rules) -> None:
    """Fija get_rules() en los módulos que la referencia."""
    import app.api.routes as routes_mod
    import app.projection.picks as picks_mod
    import app.rules as rules_mod

    for module in (rules_mod, picks_mod, routes_mod):
        monkeypatch.setattr(module, "get_rules", lambda: rules)


@pytest.fixture(name="make_db")
def fixture_make_db() -> Iterator[tuple[Engine, sessionmaker]]:  # type: ignore[type-arg]
    """Engine compartido con StaticPool para que TODO use la misma BD en memoria."""
    engine = create_engine(
        TEST_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    set_engine(engine)
    yield engine, maker
    engine.dispose()


@pytest.fixture(name="db")
def fixture_db(make_db: tuple[Engine, sessionmaker[Session]]) -> Iterator[Session]:
    """Sesión con datos demo."""
    _engine, maker = make_db
    session = maker()
    seed_demo(session, finished=6, upcoming=1)
    yield session
    session.rollback()
    session.close()


@pytest.fixture(name="client")
def fixture_client(make_db: tuple[Engine, sessionmaker[Session]], db: Session) -> Iterator[object]:
    """FastAPI TestClient sobre la misma BD en memoria."""
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import create_app

    _engine, maker = make_db

    def override() -> Iterator[Session]:
        session = maker()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override

    # no volver a crear/esquema en lifespan del TestClient está bien: create_all ya corrió
    with TestClient(app) as c:
        yield c
