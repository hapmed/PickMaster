"""Tests de la API."""

from __future__ import annotations

from starlette.testclient import TestClient


class TestHealthAndRules:
    def test_health(self, client: TestClient) -> None:
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] in {"ok", "degraded"}
        assert "No garantiza resultados" in body["disclaimer"]

    def test_rules_state(self, client: TestClient) -> None:
        res = client.get("/api/rules")
        assert res.status_code == 200
        assert res.json()["provisional"] is True


class TestMatches:
    def test_matches_list(self, client: TestClient) -> None:
        res = client.get("/api/matches")
        assert res.status_code == 200
        rows = res.json()["matches"]
        assert rows, "deben existir partidos demo"
        assert all("kickoff" in r and "home" in r and "away" in r for r in rows)


class TestPicksAndResults:
    def test_picks_flow(self, client: TestClient) -> None:
        res = client.get("/api/matches")
        assert res.status_code == 200
        matches = res.json()["matches"]

        upcoming = [m for m in matches if m["status"] == "scheduled"]
        assert upcoming, "debe haber un partido próximo demo"
        match_id = upcoming[0]["id"]

        picks = client.get("/api/picks", params={"match_id": match_id}).json()["picks"]
        assert picks, "genera picks automáticamente al consultar"
        for p in picks:
            assert p["position"] in {"GK", "DEF", "MID", "FWD"}
            assert p["expected_points"] >= 0
            assert 0 < p["confidence"] <= 1

        res404 = client.get("/api/picks", params={"match_id": 999999})
        assert res404.status_code == 404

    def test_top_picks_fallback(self, client: TestClient) -> None:
        res = client.get("/api/matches")
        match = next(m for m in res.json()["matches"] if m["status"] == "scheduled")
        top = client.get(
            "/api/picks/top", params={"match_id": match["id"], "max_picks": 3}
        )
        assert top.status_code == 200
        rows = top.json()["top_picks"]
        assert 0 < len(rows) <= 3, "siempre devuelve picks (umbral o fallback)"
        scores = [p["top_score"] for p in rows]
        assert scores == sorted(scores, reverse=True), "orden por score"
        for p in rows:
            assert "why" in p and p["why"], "explicación siempre presente"
            if p["probability"] < 0.75:
                assert p["risk_note"], "pick bajo el umbral lleva nota de riesgo"
            else:
                assert p["risk_note"] is None

    def test_player_projection(self, client: TestClient) -> None:
        res = client.get("/api/matches")
        match = next(m for m in res.json()["matches"] if m["status"] == "scheduled")
        picks = client.get("/api/picks", params={"match_id": match["id"]}).json()["picks"]
        player_id = picks[0]["player_id"]

        proj = client.get(
            f"/api/players/{player_id}/projection", params={"match_id": match["id"]}
        )
        assert proj.status_code == 200
        body = proj.json()
        assert body["p10"] <= body["median"] <= body["p90"]

    def test_results_summary_empty(self, client: TestClient) -> None:
        res = client.get("/api/results/summary")
        assert res.status_code == 200
        assert res.json()["picks_evaluated"] == 0

    def test_evaluate_via_admin(self, client: TestClient) -> None:
        # generar picks para el próximo partido
        res = client.get("/api/matches")
        match = next(m for m in res.json()["matches"] if m["status"] == "scheduled")
        picks = client.get("/api/picks", params={"match_id": match["id"]}).json()["picks"]
        assert picks

        # marcar terminado e informar stats vía del endpoint de admin no lo hace;
        # la evaluación pide stats ya cargadas: aquí quedará "pending"
        ev = client.post("/api/admin/evaluate", params={"match_id": match["id"]})
        body = ev.json()
        assert ev.status_code == 200
        assert body["state"] == "pending"
