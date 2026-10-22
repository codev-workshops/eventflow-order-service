# EventFlow Order Service

**System 1** in the EventFlow event-driven architecture demo.

A FastAPI service that accepts customer orders via REST API and publishes `OrderCreated` events to Azure Service Bus for downstream processing.

## Architecture Role

```
User → [Order Service] → Azure Service Bus → [Payment Service]
              ↓
       Application Insights
```

## Features

- REST API for order creation and retrieval
- Expected settlement date per order (T+N business days) via the shared `demo-ledger-service` library
- Event publishing to Azure Service Bus
- International currency support (USD, EUR, GBP, JPY, etc.)
- Health check and readiness endpoints
- Structured logging with correlation IDs
- OpenTelemetry instrumentation for Azure Monitor

## Tech Stack

- Python 3.11+
- FastAPI
- Azure Service Bus SDK
- OpenTelemetry + Azure Monitor
- Pydantic v2 for data validation
- [`demo-ledger-service`](https://github.com/Cognition-Partner-Workshops/demo-ledger-service) (`ledger.settlement`), pinned to a Git tag in `pyproject.toml`

## Local Development

```bash
# Install dependencies
pip install poetry
poetry install

# Set environment variables
cp .env.example .env
# Edit .env with your values

# Run the service
poetry run uvicorn app.main:app --reload --port 8001

# Run tests
poetry run pytest -v
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `AZURE_SERVICEBUS_CONNECTION_STRING` | Service Bus connection string | *(required)* |
| `AZURE_SERVICEBUS_QUEUE_NAME` | Queue name for order events | `order-events` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights connection string | *(optional)* |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Deployment environment | `development` |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/orders` | Create a new order |
| `GET` | `/api/orders/{order_id}` | Get order by ID |
| `GET` | `/api/orders` | List recent orders |
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness check (verifies Service Bus connectivity) |

## Event Schema

Published to Azure Service Bus as JSON:

```json
{
  "event_id": "uuid",
  "event_type": "OrderCreated",
  "timestamp": "2026-01-15T10:30:00Z",
  "data": {
    "order_id": "uuid",
    "customer_id": "cust-123",
    "currency": "USD",
    "amount": 4999,
    "items": [
      {
        "product_id": "prod-456",
        "name": "Widget",
        "quantity": 2,
        "unit_price": 2499
      }
    ],
    "settlement_market": "XNYS",
    "expected_settlement_date": "2026-01-16"
  }
}
```

`settlement_market` is chosen from the order currency (USD → XNYS, GBP → XLON,
EUR → XETR, JPY → XTKS, otherwise XNYS) and `expected_settlement_date` is
`ledger.settlement.settlement_date(created_at.date(), market)` from
`demo-ledger-service`: T+N business days, skipping weekends and exchange
holidays.

## Shared library dependency

`demo-ledger-service` is installed straight from GitHub at a pinned tag (no
package registry):

```toml
demo-ledger-service = { git = "https://github.com/Cognition-Partner-Workshops/demo-ledger-service.git", tag = "v0.4.0" }
```

To pick up a new library release, bump the `tag`, run `poetry lock` (Poetry
1.7.1, matching CI and the Dockerfile) and commit the updated `poetry.lock`.
CI fails if `poetry.lock` is out of date with `pyproject.toml`. The Docker
image installs `git` in the builder stage so Poetry can fetch it.

**Note:** `amount` is always in the smallest currency unit (cents for USD/EUR, yen for JPY). The downstream Payment Service is responsible for interpreting the amount based on the currency's decimal places.

## Docker

```bash
docker build -t eventflow-order-service .
docker run -p 8001:8001 --env-file .env eventflow-order-service
```
