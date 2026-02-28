from fastapi.testclient import TestClient

from phases.phase_3_api.backend.api.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data.get("status") == "ok"


def test_recommendations_endpoint_returns_list():
    payload = {
        "location": "Banashankari",
        "cuisines": ["North Indian"],
        "price_range": {"min_price": 200, "max_price": 800},
        "rating_min": 3.0,
        "mood": "casual_hangout",
    }

    response = client.post("/recommendations", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

