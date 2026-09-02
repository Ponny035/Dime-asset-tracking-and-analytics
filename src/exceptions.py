
class StockPriceFetchError(Exception):
    """Raised when stock price fetching fails after all retries are exhausted."""
    pass

class StartDateError(Exception):
    """Raised when the start date is after the end date."""
    pass