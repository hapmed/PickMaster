"""Reglas de puntuación del concurso.

Se cargan desde `config/contest_rules.json`. Los valores en `null` se cubren con
**valores provisionales** documentados: NO son los de Draftea, sólo permiten que
el motor funcione mientras se cargan las reglas vigentes. La carga desde
config/contest_rules.json con valores reales (manual/CSV, sin scraping) sobrepasa
los provisionales e invalida el estado.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import cast

from app import models
from app.config import settings
from app.db import new_session

logger = logging.getLogger(__name__)

#: Valores provisionales. Cambiar en config/contest_rules.json con reglas reales.
DEFAULT_SCORING: dict[str, float] = {
    "minutes_played": 1.0,  # provisionales: por jugar
    "goal": 6.0,
    "assist": 4.0,
    "shot_on_target": 1.0,
    "key_pass": 1.0,
    "tackle": 1.0,
    "save": 2.0,
    "clean_sheet": 3.0,
    "goals_conceded": -0.5,
    "yellow_card": -1.0,
    "red_card": -3.0,
    "own_goal": -2.0,
    "penalty_saved": 3.0,
    "penalty_missed": -2.0,
}

#: Bonus extra si el jugador jugó 60 minutos o más (provisional).
MINUTES_60_BONUS = 1.0


@dataclass
class Rules:
    """Reglas de puntuación cargadas de config (o placeholders)."""

    platform: str = "Draftea"
    league: str = "Liga MX"
    status: str = "PROVISIONAL: reglas de Draftea pendientes de cargar"
    scoring: dict[str, float] = field(default_factory=dict)
    roster: dict[str, object] = field(default_factory=dict)
    picks: dict[str, object] = field(default_factory=dict)
    source_file: str | None = None
    provisional: bool = True

    def points_for(self, key: str) -> float:
        """Peso de un evento."""
        return float(self.scoring.get(key, DEFAULT_SCORING[key]))


def load_rules(rules_path: Path | str | None = None) -> Rules:
    """Carga contest_rules.json y rellena nulos con provisionales."""
    path = Path(rules_path) if rules_path else settings.rules_path
    scoring = dict(DEFAULT_SCORING)
    provisional = True
    payload: dict[str, object] = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = cast("dict[str, object]", payload.get("scoring") or {})
            for key, value in raw.items():
                if value is not None and isinstance(value, (int, float)):
                    scoring[key] = float(value)
            status_raw = str(payload.get("status") or "")
            provisional = any(v is None for v in raw.values()) or (
                status_raw.startswith("PENDIENTE")
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo leer %s: %s; usando provisionales", path, exc)
    else:
        logger.warning("No existe %s; usando reglas provisionales", path)

    platform = str(payload.get("platform") or "Draftea")
    league = str(payload.get("league") or "Liga MX")
    status = str(payload.get("status") or Rules.status)
    roster = cast("dict[str, object]", payload.get("roster") or {})
    picks_cfg = cast("dict[str, object]", payload.get("picks") or {})

    return Rules(
        platform=platform,
        league=league,
        status=status,
        scoring=scoring,
        roster=roster,
        picks=picks_cfg,
        source_file=str(path),
        provisional=provisional,
    )


@lru_cache
def get_rules() -> Rules:
    """Reglas en caché (por proceso)."""
    return load_rules()


def score_player_stats(rstats: models.PlayerStat, rules: Rules | None = None) -> float:
    """Puntos fantasy de un stat según las reglas del concurso."""
    rules = rules or get_rules()
    pts = 0.0
    pts += MINUTES_60_BONUS if rstats.minutes >= 60 else (
        rules.points_for("minutes_played") if rstats.minutes > 0 else 0.0
    )
    pts += rstats.goals * rules.points_for("goal")
    pts += rstats.assists * rules.points_for("assist")
    pts += rstats.shots_on_target * rules.points_for("shot_on_target")
    pts += rstats.key_passes * rules.points_for("key_pass")
    pts += rstats.tackles * rules.points_for("tackle")
    pts += rstats.saves * rules.points_for("save")
    if rstats.clean_sheet:
        pts += rules.points_for("clean_sheet")
    pts += rstats.goals_conceded * rules.points_for("goals_conceded")
    pts += rstats.yellow_cards * rules.points_for("yellow_card")
    pts += rules.points_for("red_card") if rstats.red_card else 0.0
    pts += rstats.own_goal * rules.points_for("own_goal")
    pts += rstats.penalty_saved * rules.points_for("penalty_saved")
    pts += rstats.penalty_missed * rules.points_for("penalty_missed")
    return pts


def persist_rules_snapshot(rules: Rules) -> None:
    """Guarda copia versionada en `contest_rules` para auditoría."""
    session = new_session()()
    try:
        version = f"provisional-{datetime_utc_str()}" if rules.provisional else _now_key()
        row = models.ContestRuleConfig(
            version=version,
            rules_json=json.dumps(
                {
                    "platform": rules.platform,
                    "league": rules.league,
                    "status": rules.status,
                    "scoring": rules.scoring,
                    "roster": rules.roster,
                    "picks": rules.picks,
                },
                ensure_ascii=False,
            ),
            is_provisional=rules.provisional,
        )
        session.add(row)
        session.commit()
    finally:
        session.close()


def _now_key() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("rules-%Y%m%d%H%M%S")


def datetime_utc_str() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")
