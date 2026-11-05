
class StockPriceFetchError(Exception):
    """Raised when stock price fetching fails after all retries are exhausted."""
    pass

class TickerNotFoundError(StockPriceFetchError):
    """Raised when Yahoo has no price history at all for a ticker (unknown or long-dead symbol)."""
    pass

class StartDateError(Exception):
    """Raised when the start date is after the end date."""
    pass