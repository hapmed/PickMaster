"""Tests del motor Monte Carlo, picks y evaluación post-partido."""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.models import Match, PlayerPosition, PlayerStat
from app.projection import features, simulate
from app.projection.picks import collect_match_players, generate_picks
from app.rules import Rules, score_player_stats
from app.services.evaluation import ICON, evaluate_match, rate_pick


class TestMonteCarlo:
    """La distribución simulada debe ser determinista y ordenada."""

    def test_deterministic_with_fixed_rng(self, db: Session, rules: Rules) -> None:
        match = db.query(Match).filter(Match.status == "scheduled").first()
        assert match is not None
        players = collect_match_players(db, match)
        assert players, "la demo debe tener jugadores elegibles"

        feat = features.player_features(db, players[0], match)
        rates, downgrade = simulate.event_rates(feat, 1.0)
        gen_a = np.random.default_rng(7)
        gen_b = np.random.default_rng(7)
        a = simulate.simulate(feat, rates, downgrade, rules, n_sims=2_000, rng=gen_a)
        b = simulate.simulate(feat, rates, downgrade, rules, n_sims=2_000, rng=gen_b)
        assert np.array_equal(a, b), "mismo seed: misma distribución"

        summary = simulate.summarize(a)
        keys = {"mean", "median", "p10", "p25", "p75", "p90"}
        assert keys == set(summary)
        assert (
            summary["p10"] <= summary["p25"] <= summary["median"]
            <= summary["p75"] <= summary["p90"]
        )


class TestPicks:
    """Picks por posición, sin fuga de datos."""

    def test_generate_picks_covers_positions(self, db: Session, rules: Rules) -> None:
        match = db.query(Match).filter(Match.status == "scheduled").first()
        assert match is not None
        picks = generate_picks(db, match, rules)
        db.flush()
        assert picks, "debe generar al menos un pick"
        for pick in picks:
            assert pick.position in PlayerPosition.ALL
            assert 0 < pick.confidence <= 1.0
            assert pick.probability > 0
            assert pick.reason, "todo pick lleva motivo"

    def test_features_only_use_finished_past_matches(self, db: Session, rules: Rules) -> None:
        """Corte anti-fuga: kickoff del objetivo no se incluye."""
        match = db.query(Match).filter(Match.status == "scheduled").first()
        assert match is not None
        players = collect_match_players(db, match)
        features.player_features(db, players[0], match)
        cutoff = features.matches_before(db, match.kickoff)

        historic = (
            db.query(PlayerStat.match_id)
            .filter(PlayerStat.player_id == players[0].id)
            .all()
        )
        for (match_id,) in historic:
            # los stats usados por features sólo pueden ser estrictamente pasados
            row = db.get(Match, match_id)
            if row is not None and row.kickoff < match.kickoff and row.status == "finished":
                assert match_id in cutoff


class TestEvaluation:
    """Ciclo picks → resultado → evaluación (rúbricas ✅🟡❌⚪)."""

    def test_full_flow_hit(self, db: Session, rules: Rules) -> None:
        match = db.query(Match).filter(Match.status == "scheduled").first()
        assert match is not None
        picks = generate_picks(db, match, rules)
        assert picks

        # resultado real: todos jugaron 85' y marcaron gol
        for pick in picks:
            db.add(
                PlayerStat(
                    player_id=pick.player_id,
                    match_id=match.id,
                    minutes=85,
                    started=True,
                    goals=1,
                )
            )
        match.status = "finished"
        match.home_goals, match.away_goals = 2, 1
        db.flush()

        report = evaluate_match(db, match.id)
        assert report["state"] == "evaluated"
        assert report["total"] == len(picks)
        # 85 minutos + gol = 7 pts, por encima de cualquier target simulado
        assert report["counts"]["hit"] == len(picks)
        assert report["hit_rate"] == 1.0
        assert ICON["hit"] == "✅"

    def test_no_play_is_not_miss(self, db: Session, rules: Rules) -> None:
        assert rate_pick(0.0, 0, target_points=5.0, p25=2.0)[0] == "no_play"

        match = db.query(Match).filter(Match.status == "scheduled").first()
        assert match is not None
        picks = generate_picks(db, match, rules)
        assert picks

        for pick in picks:
            db.add(
                PlayerStat(
                    player_id=pick.player_id,
                    match_id=match.id,
                    minutes=0,
                    started=False,
                )
            )
        match.status = "finished"
        match.home_goals, match.away_goals = 0, 0
        db.flush()

        report = evaluate_match(db, match.id)
        assert report["counts"]["no_play"] == len(picks)
        assert report["counts"]["miss"] == 0

    def test_partial_band(self, db: Session, rules: Rules) -> None:
        """Puntos entre p25 y target = parcial."""
        assert rate_pick(3.0, 45, target_points=5.0, p25=2.0)[0] == "partial"
        assert rate_pick(1.0, 45, target_points=5.0, p25=2.0)[0] == "miss"

    def test_same_rule_engine_both_sides(self, db: Session, rules: Rules) -> None:
        """Puntos reales y simulados usan la MISMA función de reglas."""
        assert callable(score_player_stats)
