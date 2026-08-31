"""Tests for application lifecycle and health endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_lifespan_closes_servicebus_client_after_shutdown():
    """Application shutdown should close the Service Bus client."""
    with patch("app.main.close_servicebus_client") as mock_close:
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        mock_close.assert_called_once_with()


def test_readiness_check_reports_ready_when_servicebus_is_healthy():
    """Readiness should report ready when Service Bus is healthy."""
    with patch(
        "app.main.check_servicebus_health",
        new=AsyncMock(return_value=True),
    ):
        response = TestClient(app).get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["servicebus_connected"] is True


def test_health_check_reports_service_name():
    """Health should include the configured service name."""
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == settings.service_name
