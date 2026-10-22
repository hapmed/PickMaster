"""Tests de reglas de puntuación."""

from __future__ import annotations

from app import models
from app.rules import Rules, score_player_stats


def _stat(**kwargs: object) -> models.PlayerStat:
    """PlayerStat con defaults neutros."""
    base: dict[str, object] = {
        "player_id": 1,
        "match_id": 1,
        "minutes": 0,
        "started": False,
        "goals": 0,
        "assists": 0,
        "shots_on_target": 0,
        "key_passes": 0,
        "tackles": 0,
        "saves": 0,
        "goals_conceded": 0,
        "clean_sheet": False,
        "yellow_cards": 0,
        "red_card": False,
        "own_goal": 0,
        "penalty_saved": 0,
        "penalty_missed": 0,
    }
    base |= kwargs
    return models.PlayerStat(**base)


class TestScorePlayerStats:
    """Puntos según reglas (PROVISIONAL por defecto aquí)."""

    def test_no_play_zero_minutes(self, rules: Rules) -> None:
        assert score_player_stats(_stat(minutes=0), rules) == 0.0

    def test_under_60_minutes(self, rules: Rules) -> None:
        # 1 punto por jugar (regla provisional minutes_played)
        assert score_player_stats(_stat(minutes=45, started=True), rules) == 1.0

    def test_60_plus_bonus(self, rules: Rules) -> None:
        assert score_player_stats(_stat(minutes=60, started=True), rules) == 1.0

    def test_goal_and_assist(self, rules: Rules) -> None:
        pts = score_player_stats(
            _stat(minutes=90, goals=2, assists=1, shots_on_target=4), rules
        )
        # 1 juego + 12 goles + 4 asistencia + 4 tiros
        assert pts == 1.0 + 2 * 6 + 1 * 4 + 4 * 1

    def test_gk_save_and_clean_sheet(self, rules: Rules) -> None:
        pts = score_player_stats(
            _stat(minutes=90, saves=6, clean_sheet=True), rules
        )
        assert pts == 1.0 + 6 * 2 + 3

    def test_cards_penalize(self, rules: Rules) -> None:
        pts = score_player_stats(
            _stat(minutes=90, yellow_cards=1, red_card=True), rules
        )
        assert pts == 1.0 - 1 - 3
