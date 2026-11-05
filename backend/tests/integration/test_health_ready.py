import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_ready_returns_ok_when_database_is_available(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
