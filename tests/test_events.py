"""Unit tests for Azure Service Bus event handling."""

import json
from unittest.mock import MagicMock

import pytest
from azure.servicebus.exceptions import ServiceBusError

from app import events
from app.models import OrderCreatedEvent, OrderEventData, OrderItem


@pytest.fixture(autouse=True)
def reset_servicebus_globals():
    """Reset module-level Service Bus state around every test."""
    events._client = None
    events._sender = None
    yield
    events._client = None
    events._sender = None


def make_order_created_event() -> OrderCreatedEvent:
    """Build a representative order-created event."""
    return OrderCreatedEvent(
        event_id="event-123",
        data=OrderEventData(
            order_id="order-123",
            customer_id="customer-123",
            currency="USD",
            amount=10997,
            items=[
                OrderItem(
                    product_id="product-123",
                    name="Test product",
                    quantity=1,
                    unit_price=10997,
                )
            ],
        ),
    )


def test_get_servicebus_client_returns_none_without_connection_string(monkeypatch):
    """No connection string should leave the client unavailable."""
    monkeypatch.setattr(events.settings, "azure_servicebus_connection_string", "")

    assert events.get_servicebus_client() is None


def test_get_servicebus_client_is_singleton(monkeypatch):
    """A configured client should be created once and then reused."""
    connection_string = "Endpoint=sb://example.servicebus.windows.net/"
    client = MagicMock()
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(
        events.settings,
        "azure_servicebus_connection_string",
        connection_string,
    )
    monkeypatch.setattr(events.ServiceBusClient, "from_connection_string", factory)

    first_client = events.get_servicebus_client()
    second_client = events.get_servicebus_client()

    assert first_client is client
    assert second_client is client
    factory.assert_called_once_with(connection_string)


def test_get_servicebus_client_returns_none_when_initialization_fails(monkeypatch):
    """Client initialization errors should be swallowed."""
    connection_string = "Endpoint=sb://example.servicebus.windows.net/"
    factory = MagicMock(side_effect=Exception("connection failed"))
    monkeypatch.setattr(
        events.settings,
        "azure_servicebus_connection_string",
        connection_string,
    )
    monkeypatch.setattr(events.ServiceBusClient, "from_connection_string", factory)

    assert events.get_servicebus_client() is None
    assert events._client is None


@pytest.mark.asyncio
async def test_publish_order_created_returns_false_without_client(monkeypatch):
    """Publishing should fail safely when Service Bus is unavailable."""
    event = make_order_created_event()
    monkeypatch.setattr(events.settings, "azure_servicebus_connection_string", "")

    assert await events.publish_order_created(event) is False


@pytest.mark.asyncio
async def test_publish_order_created_sends_expected_message(monkeypatch):
    """Publishing should send a correctly populated Service Bus message."""
    event = make_order_created_event()
    client = MagicMock()
    sender = MagicMock()
    sender.__enter__.return_value = sender
    client.get_queue_sender.return_value = sender
    monkeypatch.setattr(events, "get_servicebus_client", MagicMock(return_value=client))

    result = await events.publish_order_created(event)

    assert result is True
    client.get_queue_sender.assert_called_once_with(
        queue_name=events.settings.azure_servicebus_queue_name
    )
    sender.send_messages.assert_called_once()
    message = sender.send_messages.call_args.args[0]
    assert message.content_type == "application/json"
    assert message.subject == "OrderCreated"
    assert message.application_properties == {
        "event_type": event.event_type,
        "event_id": event.event_id,
        "currency": event.data.currency,
        "order_id": event.data.order_id,
    }
    body = json.loads(str(message))
    assert body["data"]["order_id"] == event.data.order_id
    assert body["data"]["amount"] == event.data.amount
    assert body["data"]["currency"] == event.data.currency


@pytest.mark.asyncio
async def test_publish_order_created_returns_false_on_servicebus_error(monkeypatch):
    """Service Bus publish errors should not escape the endpoint."""
    event = make_order_created_event()
    client = MagicMock()
    sender = MagicMock()
    sender.__enter__.return_value = sender
    sender.send_messages.side_effect = ServiceBusError("send failed")
    client.get_queue_sender.return_value = sender
    monkeypatch.setattr(events, "get_servicebus_client", MagicMock(return_value=client))

    assert await events.publish_order_created(event) is False


@pytest.mark.asyncio
async def test_check_servicebus_health_returns_false_without_client(monkeypatch):
    """Health checks should fail when no client is available."""
    monkeypatch.setattr(events, "get_servicebus_client", MagicMock(return_value=None))

    assert await events.check_servicebus_health() is False


@pytest.mark.asyncio
async def test_check_servicebus_health_opens_receiver(monkeypatch):
    """A receiver that opens successfully indicates healthy connectivity."""
    client = MagicMock()
    receiver = MagicMock()
    receiver.__enter__.return_value = receiver
    client.get_queue_receiver.return_value = receiver
    monkeypatch.setattr(events, "get_servicebus_client", MagicMock(return_value=client))

    assert await events.check_servicebus_health() is True
    client.get_queue_receiver.assert_called_once_with(
        queue_name=events.settings.azure_servicebus_queue_name,
        max_wait_time=1,
    )


@pytest.mark.asyncio
async def test_check_servicebus_health_returns_false_on_servicebus_error(monkeypatch):
    """Receiver errors should report an unhealthy Service Bus."""
    client = MagicMock()
    client.get_queue_receiver.side_effect = ServiceBusError("receive failed")
    monkeypatch.setattr(events, "get_servicebus_client", MagicMock(return_value=client))

    assert await events.check_servicebus_health() is False


def test_close_servicebus_client_closes_and_clears_client():
    """Closing a client should clear the singleton."""
    client = MagicMock()
    events._client = client

    events.close_servicebus_client()

    client.close.assert_called_once_with()
    assert events._client is None


def test_close_servicebus_client_clears_client_when_close_fails():
    """Close errors should still clear the singleton."""
    client = MagicMock()
    client.close.side_effect = Exception("close failed")
    events._client = client

    events.close_servicebus_client()

    client.close.assert_called_once_with()
    assert events._client is None


def test_close_servicebus_client_is_noop_without_client():
    """Closing without a client should do nothing."""
    events.close_servicebus_client()

    assert events._client is None
