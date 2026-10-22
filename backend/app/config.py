"""Configuración central. Sin secretos: valores desde variables de entorno."""

from __future__ import annotations

import pathlib
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Ajustes del servicio. El .env nunca se versiona."""

    model_config = SettingsConfigDict(
        env_prefix="PICKMASTER_",
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    env: str = "dev"
    database_url: str = "sqlite:///./pickmaster.db"
    rules_file: str = "config/contest_rules.json"
    mc_sims: int = 10_000
    smtp_host: str = ""

    @property
    def rules_path(self) -> pathlib.Path:
        p = pathlib.Path(self.rules_file)
        return p if p.is_absolute() else BASE_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
