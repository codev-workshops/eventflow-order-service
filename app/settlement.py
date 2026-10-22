"""Expected settlement dates for accepted orders, via the shared ledger library."""

from datetime import date

from ledger.settlement import settlement_date

# Exchange on which an order in a given currency is assumed to settle.
# Falls back to XNYS (T+1) for currencies without a listed market.
MARKET_BY_CURRENCY: dict[str, str] = {
    "USD": "XNYS",
    "CAD": "XNYS",
    "GBP": "XLON",
    "EUR": "XETR",
    "CHF": "XETR",
    "JPY": "XTKS",
}
DEFAULT_MARKET = "XNYS"


def market_for_currency(currency: str) -> str:
    """Return the MIC of the market used to settle orders in ``currency``."""
    return MARKET_BY_CURRENCY.get(currency, DEFAULT_MARKET)


def expected_settlement_date(trade_date: date, currency: str) -> date:
    """T+N business days after ``trade_date`` on the market for ``currency``.

    Business days exclude weekends and the market's exchange holidays, as
    defined by ``demo-ledger-service``.
    """
    return settlement_date(trade_date, market_for_currency(currency))
