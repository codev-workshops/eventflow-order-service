"""Tests for expected settlement dates computed via demo-ledger-service."""

from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.settlement import expected_settlement_date, market_for_currency


class TestMarketForCurrency:
    def test_known_currencies_map_to_their_exchange(self):
        assert market_for_currency("USD") == "XNYS"
        assert market_for_currency("GBP") == "XLON"
        assert market_for_currency("EUR") == "XETR"
        assert market_for_currency("JPY") == "XTKS"

    def test_unknown_currency_falls_back_to_xnys(self):
        assert market_for_currency("INR") == "XNYS"


class TestExpectedSettlementDate:
    def test_usd_settles_t_plus_one(self):
        # Thursday -> Friday
        assert expected_settlement_date(date(2026, 3, 5), "USD") == date(2026, 3, 6)

    def test_usd_friday_settles_monday(self):
        assert expected_settlement_date(date(2026, 3, 6), "USD") == date(2026, 3, 9)

    def test_gbp_settles_t_plus_two_over_weekend(self):
        # Thursday trade in London, T+2 skips the weekend
        assert expected_settlement_date(date(2026, 3, 5), "GBP") == date(2026, 3, 9)

    def test_gbp_skips_summer_bank_holiday(self):
        # Mon 31 Aug 2026 is an XLON holiday, so T+2 from Thu 27 Aug is Tue 1 Sep
        assert expected_settlement_date(date(2026, 8, 27), "GBP") == date(2026, 9, 1)


class TestOrderCarriesSettlementDate:
    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_includes_settlement_fields(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        response = client.post("/api/orders", json=sample_order_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["settlement_market"] == "XNYS"
        created = date.fromisoformat(data["created_at"][:10])
        settles = date.fromisoformat(data["expected_settlement_date"])
        assert settles > created
        assert settles.weekday() < 5

        event = mock_publish.call_args.args[0]
        assert event.data.settlement_market == "XNYS"
        assert event.data.expected_settlement_date == settles

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_eur_order_settles_on_xetr(
        self, mock_publish, client: TestClient, sample_eur_order_payload: dict
    ):
        response = client.post("/api/orders", json=sample_eur_order_payload)

        assert response.status_code == 201
        assert response.json()["settlement_market"] == "XETR"
