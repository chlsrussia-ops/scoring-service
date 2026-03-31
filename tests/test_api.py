from fastapi.testclient import TestClient

from scoring_service.api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready() -> None:
    client = TestClient(create_app())
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_score_endpoint() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/v1/score",
        json={
            "payload": {
                "amount": 120,
                "comment": "great profile",
                "tags": ["vip", "repeat"],
                "metadata": {"region": "eu"},
                "approved": True,
            },
            "request_id": "api-1",
            "source": "test",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["ok"] is True
    assert "review" in body
