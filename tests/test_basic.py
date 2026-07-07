import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_liveness():
    r = client.get("/health/liveness")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_health_readiness():
    r = client.get("/health/readiness")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
