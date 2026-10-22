"""Monte Carlo: minutos, eventos y distribución de puntos fantasy.

10_000 simulaciones por jugador (configurable). Cada sim muestrea minutos y
eventos; los puntos se calculan con las reglas del concurso cargadas.

Sin fuga de datos: las features ya traen el corte temporal correcto.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.projection import features
from app.rules import Rules

DEFAULT_SIMS = 10_000
MINUTES_60_BONUS = 1.0  # mismo usado en score_player_stats (#reglas provisionales)
CARD_RATE: dict[str, float] = {"GK": 0.20, "DEF": 0.35, "MID": 0.25, "FWD": 0.15}


@dataclass
class EventRates:
    """Tasas por 90 minutos, ya ajustadas por rival."""

    goals: float = 0.0
    assists: float = 0.0
    shots_on_target: float = 0.0
    key_passes: float = 0.0
    tackles: float = 0.0
    saves: float = 0.0


def start_probability(feat: features.PlayerFeatures) -> float:
    """Probabilidad de titularidad con prior bayesiano (alpha=3, beta=2)."""
    alpha, beta = 3.0, 2.0
    return (feat.starts + alpha) / (feat.games + alpha + beta)


def minutes_distribution(feat: features.PlayerFeatures) -> tuple[float, float]:
    """(media, desv.) de minutos si el jugador juega; prior neutro 68±22."""
    if feat.games == 0:
        return 68.0, 22.0
    recent = feat.minutes_series
    mean = 0.6 * float(np.mean(recent[:5])) + 0.4 * float(np.mean(recent))
    std = float(np.std(recent)) if len(recent) > 1 else 20.0
    return max(mean, 5.0), max(std, 10.0)


def opponent_goal_factor(db: Session, match: models.Match, team_id: int | None) -> float:
    """Factor de la defensa del rival (menor = defensa más dura).

    Proporción entre goles que el equipo del jugador anota de media y goles
    que el rival recibe de media en partidos terminados previos al corte.
    """
    if team_id is None:
        return 1.0
    rival_id = match.away_team_id if team_id == match.home_team_id else match.home_team_id

    scored = _team_goals_per_game(db, team_id, match)
    conceded = _team_goals_conceded_per_game(db, rival_id, match)
    if scored <= 0 or conceded <= 0:
        return 1.0
    factor = conceded / scored
    return float(np.clip(factor, 0.5, 1.8))


def _team_goals_per_game(db: Session, team_id: int, match: models.Match) -> float:
    """Goles anotados por el equipo en partidos terminados previos al corte."""
    rows = db.execute(
        select(models.Match).where(
            models.Match.status == "finished",
            models.Match.kickoff < match.kickoff,
        )
    ).scalars().all()
    n_games: int = 0
    goals: int = 0
    for m in rows:
        if m.home_team_id == team_id:
            goals += m.home_goals or 0
            n_games += 1
        elif m.away_team_id == team_id:
            goals += m.away_goals or 0
            n_games += 1
    return goals / max(n_games, 1)


def _team_goals_conceded_per_game(db: Session, team_id: int, match: models.Match) -> float:
    """Goles recibidos por el equipo en partidos terminados previos al corte."""
    rows = db.execute(
        select(models.Match).where(
            models.Match.status == "finished",
            models.Match.kickoff < match.kickoff,
        )
    ).scalars().all()
    n_games: int = 0
    goals: int = 0
    for m in rows:
        if m.home_team_id == team_id:
            goals += m.away_goals or 0
            n_games += 1
        elif m.away_team_id == team_id:
            goals += m.home_goals or 0
            n_games += 1
    return goals / max(n_games, 1)


def event_rates(
    feat: features.PlayerFeatures, rival_factor: float = 1.0
) -> tuple[EventRates, float]:
    """Tasas por 90 mezcladas con prior por posición (shrinkage), factor rival.

    Devuelve (tasas, factor_de_minutos) donde el factor_downgrade < 1 aplica si
    hay lesión/sanción activa.
    """
    positional_prior: dict[str, dict[str, float]] = {
        "GK": {"saves": 3.2, "tackles": 0.2},
        "DEF": {
            "tackles": 2.4,
            "goals": 0.10,
            "shots_on_target": 0.35,
            "assists": 0.10,
        },
        "MID": {
            "goals": 0.30,
            "assists": 0.30,
            "shots_on_target": 1.00,
            "key_passes": 1.60,
            "tackles": 1.20,
        },
        "FWD": {"goals": 0.55, "assists": 0.20, "shots_on_target": 1.50},
    }
    prior = positional_prior.get(feat.position, {})
    k = 4.0  # partidos "virtuales" del prior
    merged: dict[str, float] = {}
    for name in ("goals", "assists", "shots_on_target", "key_passes", "tackles", "saves"):
        base = prior.get(name, 0.15)
        observed = feat.per90.get(name, 0.0)
        merged[name] = (observed * feat.games + base * k) / (feat.games + k) * rival_factor

    downgrade = 0.5 if feat.injured else 1.0
    return EventRates(**merged), downgrade


def simulate(
    feat: features.PlayerFeatures,
    rates: EventRates,
    minutes_factor: float,
    rules: Rules,
    n_sims: int = DEFAULT_SIMS,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Simula `n_sims` carreras por jugador y devuelve puntos fantasy."""
    rng = rng or np.random.default_rng()
    n = int(n_sims)

    p_start = start_probability(feat)
    m_mean, m_std = minutes_distribution(feat)

    minutes = np.where(
        rng.random(n) < p_start,
        rng.normal(m_mean, m_std, size=n),
        rng.normal(m_mean * 0.35, 12.0, size=n),
    )
    minutes = np.clip(minutes, 0, 90) * minutes_factor

    instr = minutes / 90.0
    points = np.zeros(n, dtype=float)

    events: dict[str, np.ndarray] = {
        "goals": rng.poisson(rates.goals * instr),
        "assists": rng.poisson(rates.assists * instr),
        "shots_on_target": rng.poisson(rates.shots_on_target * instr),
        "key_passes": rng.poisson(rates.key_passes * instr),
        "tackles": rng.poisson(rates.tackles * instr),
        "saves": rng.poisson(rates.saves * instr),
    }

    puntos_minutos = np.where(
        minutes >= 60,
        MINUTES_60_BONUS,
        np.where(minutes > 0, rules.points_for("minutes_played"), 0.0),
    )

    points += puntos_minutos
    points += events["goals"] * rules.points_for("goal")
    points += events["assists"] * rules.points_for("assist")
    points += events["shots_on_target"] * rules.points_for("shot_on_target")
    points += events["key_passes"] * rules.points_for("key_pass")
    points += events["tackles"] * rules.points_for("tackle")
    points += events["saves"] * rules.points_for("save")

    cards = rng.poisson(CARD_RATE.get(feat.position, 0.25) * instr)
    points += cards * rules.points_for("yellow_card")  # peso negativo en reglas

    return np.clip(points, -10, 100)


def summarize(points: np.ndarray) -> dict[str, float]:
    """Percentiles y media de la distribución simulada."""
    return {
        "mean": float(np.mean(points)),
        "median": float(np.median(points)),
        "p10": float(np.percentile(points, 10)),
        "p25": float(np.percentile(points, 25)),
        "p75": float(np.percentile(points, 75)),
        "p90": float(np.percentile(points, 90)),
    }
