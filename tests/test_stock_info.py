import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import pytz
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError, YFTzMissingError

import src.module.delistedTickers as delistedTickers_module
import src.module.stockInfo as stockInfo_module
from src.exceptions import StockPriceFetchError, TickerNotFoundError
from src.module.stockInfo import (
    get_split_factor,
    get_splits_in_range,
    get_bulk_available_trading_day_closing_price,
    get_known_classifications,
    get_stock_basic_info,
)


class _TempNotebookMixin:
    """Redirect delisted_tickers.json to a temp dir so tests never touch the real file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.notebook_path = os.path.join(self._tmp.name, "delisted_tickers.json")
        patcher = patch.object(delistedTickers_module, "DELISTED_TICKERS_FILE", self.notebook_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def read_notebook(self):
        if not os.path.isfile(self.notebook_path):
            return {}
        with open(self.notebook_path) as f:
            return json.load(f)

    def write_notebook(self, data):
        with open(self.notebook_path, "w") as f:
            json.dump(data, f)


def _history_frame(close_series):
    """A Ticker.history-shaped frame (flat columns) from a Close Series."""
    return pd.DataFrame({"Close": close_series.values}, index=close_series.index)


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


class TestSectorIndustryFallback(unittest.TestCase):
    INVEST_LOG = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-10", "2025-06-01", "2025-03-05"]),
            "Product Name": ["DHI", "DHI", "SGOV"],
            "Sector": ["Consumer Cyclical", "Consumer Cyclical", "-"],
            "Industry": ["Residential Construction", "None", "-"],
        }
    )

    def test_known_classifications_keeps_latest_non_missing(self):
        known = get_known_classifications(self.INVEST_LOG)
        # The newer DHI row has Industry "None" — the older real value is kept
        self.assertEqual(known["DHI"], {"Sector": "Consumer Cyclical", "Industry": "Residential Construction"})
        self.assertEqual(known["SGOV"], {})

    def test_known_classifications_handles_no_log(self):
        self.assertEqual(get_known_classifications(None), {})

    @patch("src.module.stockInfo._fetch_stock_basic_info")
    def test_missing_industry_filled_from_earlier_transaction(self, mock_fetch):
        # finviz returned Industry=None (str → "None")
        mock_fetch.return_value = {"Company": "D.R. Horton", "Sector": "Consumer Cyclical",
                                   "Industry": "None", "Country": "USA", "Dividend": "1.6"}
        info = get_stock_basic_info("DHI", get_known_classifications(self.INVEST_LOG))
        self.assertEqual(info["Industry"], "Residential Construction")
        self.assertEqual(info["Sector"], "Consumer Cyclical")

    @patch("src.module.stockInfo._fetch_stock_basic_info")
    def test_missing_with_no_earlier_transaction_becomes_dash(self, mock_fetch):
        mock_fetch.return_value = {"Company": "UPS", "Sector": "None", "Industry": "None",
                                   "Country": "USA", "Dividend": "6.5"}
        info = get_stock_basic_info("UPS", get_known_classifications(self.INVEST_LOG))
        self.assertEqual(info["Sector"], "-")
        self.assertEqual(info["Industry"], "-")

    @patch("src.module.stockInfo._fetch_stock_basic_info")
    def test_online_value_wins_over_earlier_transaction(self, mock_fetch):
        mock_fetch.return_value = {"Company": "D.R. Horton", "Sector": "Consumer Cyclical",
                                   "Industry": "Homebuilding", "Country": "USA", "Dividend": "1.6"}
        info = get_stock_basic_info("DHI", get_known_classifications(self.INVEST_LOG))
        self.assertEqual(info["Industry"], "Homebuilding")


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


class TestGetBulkClosingPrice(_TempNotebookMixin, unittest.TestCase):
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
    @patch("src.module.stockInfo.yf.Ticker")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_retries_ticker_missing_from_bulk_download(self, mock_dl, mock_cal, mock_ticker, mock_sleep):
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])

        # Bulk: MSFT present, AAPL all-NaN (triggers retry)
        bulk_close = pd.DataFrame({"AAPL": [np.nan], "MSFT": [150.0]}, index=dates)
        mock_dl.return_value = _yf_download_mock(bulk_close)

        # Individual retry for AAPL goes through Ticker.history
        mock_ticker.return_value.history.return_value = _history_frame(
            pd.Series([185.0], index=dates)
        )

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
    @patch("src.module.stockInfo.yf.Ticker")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_raises_fetch_error_after_max_retries_exhausted(self, mock_dl, mock_cal, mock_ticker, mock_sleep):
        mock_cal.return_value = _nyse_mock()

        # Bulk returns empty — AAPL never lands in close_data
        bulk_mock = MagicMock()
        bulk_mock.empty = True
        mock_dl.return_value = bulk_mock

        # All individual retries are rate limited
        mock_ticker.return_value.history.side_effect = YFRateLimitError()

        with self.assertRaises(StockPriceFetchError) as ctx:
            get_bulk_available_trading_day_closing_price(
                ["AAPL"],
                start_date=datetime(2024, 1, 15),
                end_date=datetime(2024, 1, 15),
            )
        self.assertEqual(str(ctx.exception), "AAPL")
        self.assertNotIsInstance(ctx.exception, TickerNotFoundError)
        self.assertEqual(mock_ticker.return_value.history.call_count, 3)

    @patch("src.module.stockInfo.time.sleep")
    @patch("src.module.stockInfo.yf.Ticker")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_drops_nan_placeholder_before_concat_to_avoid_duplicate_column(
        self, mock_dl, mock_cal, mock_ticker, mock_sleep
    ):
        """Regression: all-NaN bulk column must be dropped before concat with retry result."""
        mock_cal.return_value = _nyse_mock()
        dates = pd.to_datetime(["2024-01-15"])

        # For single-ticker download, yfinance returns data['Close'] as a Series.
        # Bulk: AAPL all-NaN Series
        bulk_series = pd.Series([np.nan], index=dates, name="AAPL")
        mock_dl.return_value = _yf_download_mock(bulk_series)

        # Retry: real AAPL value
        mock_ticker.return_value.history.return_value = _history_frame(
            pd.Series([185.0], index=dates)
        )

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
    @patch("src.module.stockInfo.yf.Ticker")
    @patch("src.module.stockInfo.mcal.get_calendar")
    @patch("src.module.stockInfo.yf.download")
    def test_retry_sleeps_between_attempts(self, mock_dl, mock_cal, mock_ticker, mock_sleep):
        """Each retry sleeps 150 ms; a rate limit adds a growing backoff (none after the last attempt)."""
        mock_cal.return_value = _nyse_mock()

        # Bulk returns empty
        bulk_mock = MagicMock()
        bulk_mock.empty = True
        mock_dl.return_value = bulk_mock
        mock_ticker.return_value.history.side_effect = YFRateLimitError()

        with self.assertRaises(StockPriceFetchError):
            get_bulk_available_trading_day_closing_price(
                ["AAPL"],
                start_date=datetime(2024, 1, 15),
                end_date=datetime(2024, 1, 15),
            )

        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        self.assertEqual(sleeps, [0.15, 5, 0.15, 10, 0.15])


# ── Fake Yahoo for the delisted scenarios ─────────────────────────────────────
# AAPL trades every NYSE session through 2026-11-04.
# KVUE (acquired by KMB) last traded on Fri 2026-10-30 at 19.31.
_NYSE_DAYS = (
    mcal.get_calendar("NYSE")
    .valid_days(start_date="2025-10-01", end_date="2026-11-04")
    .tz_localize(None)
)
_PRICES = {
    "AAPL": pd.Series(
        np.round(np.linspace(150, 250, len(_NYSE_DAYS)), 2), index=_NYSE_DAYS
    ),
    "KVUE": pd.Series(
        np.linspace(25, 19.31, len(_NYSE_DAYS[_NYSE_DAYS <= "2026-10-30"])).round(2),
        index=_NYSE_DAYS[_NYSE_DAYS <= "2026-10-30"],
    ),
}
LAST_KVUE_CLOSE = 19.31


def _window(ticker, start, end):
    """Closes for ticker in [start, end) — yfinance's end is exclusive."""
    s = _PRICES[ticker]
    return s[(s.index >= pd.Timestamp(start)) & (s.index < pd.Timestamp(end))]


def fake_download(tickers, start, end, flat=False, **kwargs):
    """Mimics yf.download: rows with no data for any ticker are dropped, MultiIndex columns."""
    tickers = [tickers] if isinstance(tickers, str) else list(tickers)
    close = pd.DataFrame(
        {t: _window(t, start, end) if t in _PRICES else pd.Series(dtype=float) for t in tickers}
    ).dropna(how="all")
    if close.empty:
        return pd.DataFrame()
    if flat and len(tickers) == 1:
        return pd.DataFrame({"Close": close[tickers[0]], "Open": close[tickers[0]]})
    frame = pd.concat({"Close": close, "Open": close}, axis=1)
    return frame


class FakeTicker:
    """Mimics yf.Ticker(t).history with yfinance's typed errors (hide_exceptions=False)."""

    def __init__(self, ticker):
        self.ticker = ticker
        self.info = {"longName": f"{ticker} Inc"}

    def history(self, start, end, **kwargs):
        if self.ticker not in _PRICES:
            raise YFTzMissingError(self.ticker)
        closes = _window(self.ticker, start, end)
        if closes.empty:
            raise YFPricesMissingError(self.ticker, f"(1d {start} -> {end})")
        idx = closes.index.tz_localize("America/New_York")
        return pd.DataFrame({"Close": closes.values}, index=idx)


def _ny(y, m, d):
    return datetime(y, m, d)


@patch("src.module.stockInfo.time.sleep")
class TestBulkClosingPriceDelisted(_TempNotebookMixin, unittest.TestCase):
    """Delisted / rate-limit classification with a fake Yahoo and the real NYSE calendar."""

    def fetch(self, tickers, start, end, fill=None, download=fake_download, ticker_cls=FakeTicker):
        with patch("src.module.stockInfo.yf.download", side_effect=download) as dl, \
             patch("src.module.stockInfo.yf.Ticker", side_effect=ticker_cls) as tk:
            result = get_bulk_available_trading_day_closing_price(
                tickers, start_date=start, end_date=end,
                user_timezone="America/New_York", fill=fill,
            )
        self.download_mock, self.ticker_mock = dl, tk
        return result

    # ── rate limit vs delisted ──────────────────────────────────────────────

    def test_rate_limited_every_attempt_raises_fetch_error_and_stores_nothing(self, _sleep):
        class RateLimited(FakeTicker):
            def history(self, *a, **k):
                raise YFRateLimitError()

        with self.assertRaises(StockPriceFetchError) as ctx:
            self.fetch(["AAPL"], _ny(2026, 11, 2), _ny(2026, 11, 4),
                       download=lambda *a, **k: pd.DataFrame(), ticker_cls=RateLimited)
        self.assertNotIsInstance(ctx.exception, TickerNotFoundError)
        self.assertEqual(self.read_notebook(), {})

    def test_rate_limited_twice_then_ok_returns_data(self, _sleep):
        calls = {"n": 0}

        class Flaky(FakeTicker):
            def history(self, *a, **k):
                calls["n"] += 1
                if calls["n"] <= 2:
                    raise YFRateLimitError()
                return super().history(*a, **k)

        result = self.fetch(["AAPL"], _ny(2026, 11, 2), _ny(2026, 11, 4),
                            download=lambda *a, **k: pd.DataFrame(), ticker_cls=Flaky)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result.loc["2026-11-04", "AAPL"], _PRICES["AAPL"]["2026-11-04"])

    def test_delisted_ticker_returns_last_close_and_is_stored(self, _sleep):
        with self.assertLogs(level="WARNING") as logs:
            result = self.fetch(["KVUE"], _ny(2026, 11, 2), _ny(2026, 11, 4))

        self.assertEqual(list(result.index), list(pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04"])))
        self.assertTrue((result["KVUE"] == LAST_KVUE_CLOSE).all())
        self.assertTrue(any("likely delisted" in m for m in logs.output))

        entry = self.read_notebook()["KVUE"]
        self.assertEqual(entry["status"], "delisted")
        self.assertEqual(entry["last_trade_date"], "2026-10-30")
        self.assertAlmostEqual(entry["last_close"], LAST_KVUE_CLOSE)

    def test_stored_delisted_ticker_is_not_fetched(self, _sleep):
        self.write_notebook({"KVUE": {"status": "delisted", "last_trade_date": "2026-10-30",
                                      "last_close": LAST_KVUE_CLOSE}})
        result = self.fetch(["KVUE"], _ny(2026, 11, 3), _ny(2026, 11, 3), fill="ffill")

        self.assertAlmostEqual(result.loc["2026-11-03", "KVUE"], LAST_KVUE_CLOSE)
        self.download_mock.assert_not_called()
        self.ticker_mock.assert_not_called()

    def test_stored_never_recheck_ticker_is_not_fetched(self, _sleep):
        self.write_notebook({"KVUE": {"status": "never_recheck", "last_trade_date": "2026-10-30",
                                      "last_close": LAST_KVUE_CLOSE}})
        result = self.fetch(["AAPL", "KVUE"], _ny(2026, 11, 2), _ny(2026, 11, 4))

        self.assertTrue((result["KVUE"] == LAST_KVUE_CLOSE).all())
        self.assertEqual(self.download_mock.call_args.args[0], ["AAPL"])

    def test_stored_ticker_still_fetched_for_window_before_delisting(self, _sleep):
        """Backfilling dates before the last trade must use real prices, not the stored one."""
        self.write_notebook({"KVUE": {"status": "delisted", "last_trade_date": "2026-10-30",
                                      "last_close": LAST_KVUE_CLOSE}})
        result = self.fetch(["KVUE"], _ny(2026, 10, 28), _ny(2026, 11, 4))

        # fill=None: only the real trading rows, through Oct 30
        self.assertEqual(list(result.index), list(pd.to_datetime(["2026-10-28", "2026-10-29", "2026-10-30"])))
        self.assertAlmostEqual(result.loc["2026-10-28", "KVUE"], _PRICES["KVUE"]["2026-10-28"])

    def test_yahoo_dropped_whole_history_uses_recorded_close(self, _sleep):
        """Real case: Yahoo returns nothing for KVUE even for 365 days back; the asset sheet has 19.31."""
        class Purged(FakeTicker):
            def history(self, start, end, **k):
                raise YFPricesMissingError(self.ticker, f"(1d {start} -> {end})")

        with patch("src.module.stockInfo.yf.download", return_value=pd.DataFrame()), \
             patch("src.module.stockInfo.yf.Ticker", side_effect=Purged):
            result = get_bulk_available_trading_day_closing_price(
                ["KVUE"], start_date=_ny(2026, 11, 2), end_date=_ny(2026, 11, 2),
                user_timezone="America/New_York", fill="ffill",
                last_known_close={"KVUE": LAST_KVUE_CLOSE},
            )

        self.assertAlmostEqual(result.loc["2026-11-02", "KVUE"], LAST_KVUE_CLOSE)
        entry = self.read_notebook()["KVUE"]
        self.assertEqual(entry["last_trade_date"], "2026-10-30")
        self.assertAlmostEqual(entry["last_close"], LAST_KVUE_CLOSE)

    def test_yahoo_dropped_history_without_recorded_close_raises_not_found(self, _sleep):
        class Purged(FakeTicker):
            def history(self, start, end, **k):
                raise YFPricesMissingError(self.ticker, "")

        with self.assertRaises(TickerNotFoundError):
            self.fetch(["KVUE"], _ny(2026, 11, 2), _ny(2026, 11, 2), fill="ffill",
                       download=lambda *a, **k: pd.DataFrame(), ticker_cls=Purged)
        self.assertEqual(self.read_notebook(), {})

    def test_unknown_symbol_raises_ticker_not_found(self, _sleep):
        with self.assertRaises(TickerNotFoundError):
            self.fetch(["ZZZZ"], _ny(2026, 11, 2), _ny(2026, 11, 4))
        self.assertEqual(self.read_notebook(), {})

    def test_single_missed_session_is_not_treated_as_delisted(self, _sleep):
        """Yahoo may just be late publishing a close — one missed session is inconclusive."""
        with self.assertRaises(StockPriceFetchError) as ctx:
            self.fetch(["KVUE"], _ny(2026, 11, 2), _ny(2026, 11, 2))
        self.assertNotIsInstance(ctx.exception, TickerNotFoundError)
        self.assertEqual(self.read_notebook(), {})

    # ── result shape ────────────────────────────────────────────────────────

    def test_mixed_live_and_delisted(self, _sleep):
        result = self.fetch(["AAPL", "KVUE"], _ny(2026, 11, 2), _ny(2026, 11, 4))

        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result.loc["2026-11-03", "AAPL"], _PRICES["AAPL"]["2026-11-03"])
        self.assertTrue((result["KVUE"] == LAST_KVUE_CLOSE).all())

    def test_ffill_single_day_matches_asset_tracking_call(self, _sleep):
        """assetTracking calls with start == end, fill='ffill'; Nov 2 and Nov 3 must agree."""
        nov2 = self.fetch(["KVUE"], _ny(2026, 11, 2), _ny(2026, 11, 2), fill="ffill")
        nov3 = self.fetch(["KVUE"], _ny(2026, 11, 3), _ny(2026, 11, 3), fill="ffill")

        self.assertAlmostEqual(nov2.loc["2026-11-02", "KVUE"], LAST_KVUE_CLOSE)
        self.assertAlmostEqual(nov3.loc["2026-11-03", "KVUE"], LAST_KVUE_CLOSE)

    def test_single_ticker_multiindex_and_flat_columns(self, _sleep):
        for flat in (False, True):
            with self.subTest(flat=flat):
                result = self.fetch(["AAPL"], _ny(2026, 11, 4), _ny(2026, 11, 4),
                                    download=lambda *a, **k: fake_download(*a, flat=flat, **k))
                self.assertIsNotNone(result)
                self.assertAlmostEqual(result.loc["2026-11-04", "AAPL"], _PRICES["AAPL"]["2026-11-04"])
                # Served by the bulk download, no per-ticker retry needed
                self.ticker_mock.assert_not_called()

    def test_tz_aware_end_date(self, _sleep):
        ny = pytz.timezone("America/New_York")
        result = self.fetch(["AAPL"], _ny(2026, 11, 4), ny.localize(datetime(2026, 11, 4)))
        self.assertAlmostEqual(result.loc["2026-11-04", "AAPL"], _PRICES["AAPL"]["2026-11-04"])


if __name__ == "__main__":
    unittest.main()
