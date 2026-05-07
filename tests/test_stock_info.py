import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

import numpy as np
import pandas as pd

import src.module.stockInfo as stockInfo_module
from src.module.stockInfo import (
    StockPriceFetchError,
    get_split_factor,
    get_splits_in_range,
    get_bulk_available_trading_day_closing_price,
)


def _make_splits(dates, ratios):
    """Build a plain (tz-naive) pd.Series that looks like yf.Ticker.splits."""
    return pd.Series(ratios, index=pd.DatetimeIndex(dates))


def _yf_download_mock(close_data):
    """
    Wrap a pd.Series or pd.DataFrame in a mock that looks like a yf.download result.
    close_data: Series  → single-ticker download  (data['Close'] returns the Series)
                DataFrame → multi-ticker download   (data['Close'] returns the DataFrame)
    """
    mock = MagicMock()
    mock.empty = len(close_data) == 0
    mock.__getitem__ = MagicMock(
        side_effect=lambda key: close_data if key == "Close" else MagicMock()
    )
    return mock


def _nyse_mock(dates=None):
    """Return a mock pandas_market_calendars NYSE calendar."""
    if dates is None:
        dates = pd.DatetimeIndex(["2024-01-15"], tz="America/New_York")
    m = MagicMock()
    m.valid_days.return_value = dates
    return m


class TestStockPriceFetchError(unittest.TestCase):
    def test_is_exception_subclass(self):
        self.assertTrue(issubclass(StockPriceFetchError, Exception))

    def test_stores_ticker_name(self):
        err = StockPriceFetchError("AAPL")
        self.assertEqual(str(err), "AAPL")

    def test_can_be_raised_and_caught(self):
        with self.assertRaises(StockPriceFetchError):
            raise StockPriceFetchError("MSFT")


class TestGetSplitsInRange(unittest.TestCase):
    def setUp(self):
        stockInfo_module._splits_cache.clear()

    @patch("src.module.stockInfo.yf.Ticker")
    def test_empty_series_when_ticker_has_no_splits(self, mock_ticker):
        mock_ticker.return_value.splits = pd.Series(dtype=float)
        result = get_splits_in_range("AAPL", "2023-01-01", "2024-01-01")
        self.assertTrue(result.empty)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_empty_series_when_split_is_outside_window(self, mock_ticker):
        mock_ticker.return_value.splits = _make_splits(["2022-06-01"], [2.0])
        result = get_splits_in_range("AAPL", "2023-01-01", "2024-01-01")
        self.assertTrue(result.empty)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_returns_event_inside_window(self, mock_ticker):
        mock_ticker.return_value.splits = _make_splits(["2024-06-10"], [4.0])
        result = get_splits_in_range("AAPL", "2024-06-09", "2024-06-10")
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.iloc[0], 4.0)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_from_date_boundary_is_exclusive(self, mock_ticker):
        """A split exactly ON from_date must NOT be included."""
        mock_ticker.return_value.splits = _make_splits(["2024-06-10"], [2.0])
        result = get_splits_in_range("AAPL", "2024-06-10", "2024-06-11")
        self.assertTrue(result.empty)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_to_date_boundary_is_inclusive(self, mock_ticker):
        """A split exactly ON to_date must be included."""
        mock_ticker.return_value.splits = _make_splits(["2024-06-10"], [2.0])
        result = get_splits_in_range("AAPL", "2024-06-09", "2024-06-10")
        self.assertFalse(result.empty)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_strips_timezone_from_index(self, mock_ticker):
        tz_index = pd.DatetimeIndex(["2024-06-10"]).tz_localize("UTC")
        mock_ticker.return_value.splits = pd.Series([2.0], index=tz_index)
        result = get_splits_in_range("AAPL", "2024-06-09", "2024-06-10")
        self.assertIsNone(result.index.tz)
        self.assertFalse(result.empty)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_ticker_fetched_only_once_per_session(self, mock_ticker):
        mock_ticker.return_value.splits = pd.Series(dtype=float)
        get_splits_in_range("AAPL", "2024-01-01", "2024-06-01")
        get_splits_in_range("AAPL", "2024-06-01", "2024-12-01")
        mock_ticker.assert_called_once_with("AAPL")

    @patch("src.module.stockInfo.yf.Ticker")
    def test_exception_from_yfinance_returns_empty_series(self, mock_ticker):
        mock_ticker.side_effect = Exception("network error")
        result = get_splits_in_range("AAPL", "2024-01-01", "2024-12-31")
        self.assertTrue(result.empty)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_returns_multiple_events_in_window(self, mock_ticker):
        mock_ticker.return_value.splits = _make_splits(
            ["2024-03-01", "2024-06-01"], [2.0, 3.0]
        )
        result = get_splits_in_range("AAPL", "2024-01-01", "2024-12-31")
        self.assertEqual(len(result), 2)


class TestGetSplitFactor(unittest.TestCase):
    def setUp(self):
        stockInfo_module._splits_cache.clear()

    @patch("src.module.stockInfo.yf.Ticker")
    def test_returns_1_when_no_splits(self, mock_ticker):
        mock_ticker.return_value.splits = pd.Series(dtype=float)
        self.assertEqual(get_split_factor("AAPL", "2024-01-01", "2024-12-31"), 1.0)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_returns_single_split_ratio(self, mock_ticker):
        mock_ticker.return_value.splits = _make_splits(["2024-06-10"], [4.0])
        factor = get_split_factor("AAPL", "2024-06-09", "2024-06-10")
        self.assertAlmostEqual(factor, 4.0)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_returns_product_of_multiple_splits(self, mock_ticker):
        mock_ticker.return_value.splits = _make_splits(
            ["2024-03-01", "2024-09-01"], [2.0, 3.0]
        )
        factor = get_split_factor("AAPL", "2024-01-01", "2024-12-31")
        self.assertAlmostEqual(factor, 6.0)

    @patch("src.module.stockInfo.yf.Ticker")
    def test_delegates_to_get_splits_in_range(self, mock_ticker):
        """get_split_factor should be consistent with get_splits_in_range output."""
        stockInfo_module._splits_cache.clear()
        mock_ticker.return_value.splits = _make_splits(["2024-06-10"], [5.0])
        splits = get_splits_in_range("TSLA", "2024-06-09", "2024-06-10")
        stockInfo_module._splits_cache.clear()
        mock_ticker.return_value.splits = _make_splits(["2024-06-10"], [5.0])
        factor = get_split_factor("TSLA", "2024-06-09", "2024-06-10")
        self.assertAlmostEqual(factor, float(splits.prod()))


class TestGetBulkClosingPrice(unittest.TestCase):
    """Tests for get_bulk_available_trading_day_closing_price."""

    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_passes_auto_adjust_false_to_download(self, mock_dl, mock_cal):
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])
        close = pd.Series([185.0], index=dates, name="AAPL")
        mock_dl.return_value = _yf_download_mock(close)

        get_bulk_available_trading_day_closing_price(
            ["AAPL"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        kwargs = mock_dl.call_args[1]
        self.assertFalse(kwargs.get("auto_adjust", True),
                         "auto_adjust must be False (changed default in yfinance 1.x)")

    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_passes_threads_false_to_download(self, mock_dl, mock_cal):
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])
        close = pd.Series([185.0], index=dates, name="AAPL")
        mock_dl.return_value = _yf_download_mock(close)

        get_bulk_available_trading_day_closing_price(
            ["AAPL"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        kwargs = mock_dl.call_args[1]
        self.assertFalse(kwargs.get("threads", True),
                         "threads must be False to avoid yfinance SQLite lock contention")

    @patch("src.module.stockInfo.mcal.get_calendar")
    def test_returns_none_when_no_valid_trading_days(self, mock_cal):
        nyse = MagicMock()
        nyse.valid_days.return_value = pd.DatetimeIndex([])
        mock_cal.return_value = nyse

        result = get_bulk_available_trading_day_closing_price(
            ["AAPL"],
            start_date=datetime(2024, 1, 14),  # Sunday
            end_date=datetime(2024, 1, 14),
        )
        self.assertIsNone(result)

    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_bulk_success_returns_dataframe_with_ticker_column(self, mock_dl, mock_cal):
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])
        close = pd.Series([185.0], index=dates, name="AAPL")
        mock_dl.return_value = _yf_download_mock(close)

        result = get_bulk_available_trading_day_closing_price(
            ["AAPL"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        self.assertIsNotNone(result)
        self.assertIn("AAPL", result.columns)
        self.assertAlmostEqual(result.loc["2024-01-15", "AAPL"], 185.0)

    @patch("src.module.stockInfo.time.sleep")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_retries_ticker_missing_from_bulk_download(self, mock_dl, mock_cal, mock_sleep):
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])

        # Bulk: MSFT present, AAPL all-NaN (triggers retry)
        bulk_close = pd.DataFrame({"AAPL": [np.nan], "MSFT": [150.0]}, index=dates)
        bulk_mock = _yf_download_mock(bulk_close)

        # Individual retry for AAPL returns a Series
        retry_series = pd.Series([185.0], index=dates, name="AAPL")
        retry_mock = _yf_download_mock(retry_series)

        mock_dl.side_effect = [bulk_mock, retry_mock]

        result = get_bulk_available_trading_day_closing_price(
            ["AAPL", "MSFT"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        self.assertIsNotNone(result)
        self.assertIn("AAPL", result.columns)
        self.assertAlmostEqual(result.loc["2024-01-15", "AAPL"], 185.0)
        self.assertAlmostEqual(result.loc["2024-01-15", "MSFT"], 150.0)

    @patch("src.module.stockInfo.time.sleep")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_raises_fetch_error_after_max_retries_exhausted(self, mock_dl, mock_cal, mock_sleep):
        mock_cal.return_value = _nyse_mock()

        # Bulk returns empty — AAPL never lands in close_data
        bulk_mock = MagicMock()
        bulk_mock.empty = True

        # All individual retries also empty
        empty_mock = MagicMock()
        empty_mock.empty = True

        mock_dl.side_effect = [bulk_mock] + [empty_mock] * 3  # bulk + 3 exhausted retries

        with self.assertRaises(StockPriceFetchError) as ctx:
            get_bulk_available_trading_day_closing_price(
                ["AAPL"],
                start_date=datetime(2024, 1, 15),
                end_date=datetime(2024, 1, 15),
            )
        self.assertEqual(str(ctx.exception), "AAPL")

    @patch("src.module.stockInfo.time.sleep")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_drops_nan_placeholder_before_concat_to_avoid_duplicate_column(
        self, mock_dl, mock_cal, mock_sleep
    ):
        """Regression: all-NaN bulk column must be dropped before concat with retry result."""
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])

        # For single-ticker download, yfinance returns data['Close'] as a Series.
        # Bulk: AAPL all-NaN Series
        bulk_series = pd.Series([np.nan], index=dates, name="AAPL")
        bulk_mock = _yf_download_mock(bulk_series)

        # Retry: real AAPL value
        retry_series = pd.Series([185.0], index=dates, name="AAPL")
        retry_mock = _yf_download_mock(retry_series)

        mock_dl.side_effect = [bulk_mock, retry_mock]

        result = get_bulk_available_trading_day_closing_price(
            ["AAPL"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        self.assertIsNotNone(result)
        # No duplicate AAPL columns
        self.assertEqual(list(result.columns).count("AAPL"), 1)
        # Value comes from the retry, not the NaN placeholder
        self.assertFalse(result["AAPL"].isna().all())

    @patch("src.module.stockInfo.time.sleep")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_retry_sleeps_between_attempts(self, mock_dl, mock_cal, mock_sleep):
        """Each retry attempt should sleep to respect rate limits (150 ms)."""
        mock_cal.return_value = _nyse_mock()

        # Bulk returns empty
        bulk_mock = MagicMock()
        bulk_mock.empty = True

        empty_mock = MagicMock()
        empty_mock.empty = True
        mock_dl.side_effect = [bulk_mock, empty_mock, empty_mock, empty_mock]

        with self.assertRaises(StockPriceFetchError):
            get_bulk_available_trading_day_closing_price(
                ["AAPL"],
                start_date=datetime(2024, 1, 15),
                end_date=datetime(2024, 1, 15),
            )

        # sleep called once per retry attempt (3 attempts total)
        self.assertEqual(mock_sleep.call_count, 3)
        # Each call uses 150 ms
        for call in mock_sleep.call_args_list:
            self.assertAlmostEqual(call.args[0], 0.15)


if __name__ == "__main__":
    unittest.main()
