"""Tests for order status updates and list limits."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_update_order_status_persists_new_status(
    client: TestClient,
    sample_order_payload: dict,
):
    """Updating an existing order should persist its new status."""
    with patch(
        "app.routers.orders.publish_order_created",
        new=AsyncMock(return_value=True),
    ):
        created = client.post("/api/orders", json=sample_order_payload)

    order_id = created.json()["order_id"]
    response = client.patch(
        f"/api/orders/{order_id}/status",
        json={"status": "paid"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paid"

    follow_up = client.get(f"/api/orders/{order_id}")
    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "paid"


def test_update_order_status_returns_not_found_for_unknown_order(client: TestClient):
    """Updating an unknown order should return a descriptive 404."""
    order_id = "missing-order-123"

    response = client.patch(
        f"/api/orders/{order_id}/status",
        json={"status": "paid"},
    )

    assert response.status_code == 404
    assert order_id in response.json()["detail"]


def test_update_order_status_requires_status(client: TestClient):
    """Updating an order without a status should fail validation."""
    response = client.patch(
        "/api/orders/missing-order-123/status",
        json={},
    )

    assert response.status_code == 422


def test_list_orders_limit_returns_most_recent_orders(
    client: TestClient,
    sample_order_payload: dict,
):
    """A list limit should return the newest order first."""
    created_ids = []
    with patch(
        "app.routers.orders.publish_order_created",
        new=AsyncMock(return_value=True),
    ):
        for customer_id in ("list-customer-1", "list-customer-2"):
            payload = {**sample_order_payload, "customer_id": customer_id}
            response = client.post("/api/orders", json=payload)
            assert response.status_code == 201
            created_ids.append(response.json()["order_id"])

    response = client.get("/api/orders", params={"limit": 1})

    assert response.status_code == 200
    orders = response.json()
    assert len(orders) == 1
    assert orders[0]["order_id"] == created_ids[-1]
