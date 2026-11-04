"""Pengujian endpoint kesehatan dan koneksi database."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """`GET /health` harus membalas status ok tanpa menyentuh database."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Document API"}


def test_health_db_returns_connected(client: TestClient) -> None:
    """`GET /health/db` harus membuktikan koneksi database hidup."""
    response = client.get("/health/db")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["result"] == 1