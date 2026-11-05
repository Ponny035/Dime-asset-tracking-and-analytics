import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError

import src.module.delistedTickers as delistedTickers_module
from src.module.delistedTickers import (
    load_delisted,
    mark_delisted,
    mark_never_recheck,
    unmark_delisted,
)
from src.module.stockInfo import recheck_delisted_tickers

KVUE_ENTRY = {
    "status": "delisted",
    "last_trade_date": "2026-10-30",
    "last_close": 19.31,
    "detected_on": "2026-11-05",
    "reason": "possibly delisted; no price data found",
}


class _NotebookTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "delisted_tickers.json")
        patcher = patch.object(delistedTickers_module, "DELISTED_TICKERS_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f)

    def read(self):
        with open(self.path) as f:
            return json.load(f)


class TestDelistedStore(_NotebookTestCase):
    def test_missing_file_is_empty(self):
        self.assertEqual(load_delisted(), {})

    def test_corrupt_file_is_treated_as_empty(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        with self.assertLogs(level="WARNING"):
            self.assertEqual(load_delisted(), {})

    def test_mark_unmark_roundtrip(self):
        mark_delisted("KVUE", pd.Timestamp("2026-10-30"), 19.314, "possibly delisted")
        entry = load_delisted()["KVUE"]
        self.assertEqual(entry["status"], "delisted")
        self.assertEqual(entry["last_trade_date"], "2026-10-30")
        self.assertEqual(entry["last_close"], 19.31)

        unmark_delisted("KVUE")
        self.assertEqual(load_delisted(), {})

    def test_mark_never_recheck_keeps_price(self):
        self.write({"KVUE": dict(KVUE_ENTRY)})
        mark_never_recheck("KVUE")
        entry = load_delisted()["KVUE"]
        self.assertEqual(entry["status"], "never_recheck")
        self.assertEqual(entry["last_close"], 19.31)


def _new_prices_frame():
    idx = pd.DatetimeIndex(["2026-11-03", "2026-11-04"]).tz_localize("America/New_York")
    return pd.DataFrame({"Close": [45.10, 45.80]}, index=idx)


@patch("src.module.stockInfo.yf.Ticker")
class TestRecheckDelistedTickers(_NotebookTestCase):
    def setUp(self):
        super().setUp()
        self.write({"KVUE": dict(KVUE_ENTRY)})

    def test_still_no_prices_keeps_entry_without_asking(self, mock_ticker):
        mock_ticker.return_value.history.side_effect = YFPricesMissingError("KVUE", "")
        ask = MagicMock()

        recheck_delisted_tickers(ask=ask)

        ask.assert_not_called()
        self.assertEqual(self.read()["KVUE"]["status"], "delisted")

    def test_yahoo_returning_old_bar_outside_window_is_not_new_prices(self, mock_ticker):
        """Regression: asked from 2026-10-31, Yahoo still sent the 2026-10-30 bar (19.31)."""
        idx = pd.DatetimeIndex(["2026-10-30"]).tz_localize("America/New_York")
        mock_ticker.return_value.history.return_value = pd.DataFrame({"Close": [19.31]}, index=idx)
        ask = MagicMock()

        recheck_delisted_tickers(ask=ask)

        ask.assert_not_called()
        self.assertEqual(self.read()["KVUE"]["status"], "delisted")

    def test_rate_limited_keeps_entry_without_asking(self, mock_ticker):
        mock_ticker.return_value.history.side_effect = YFRateLimitError()
        ask = MagicMock()

        recheck_delisted_tickers(ask=ask)

        ask.assert_not_called()
        self.assertEqual(self.read()["KVUE"]["status"], "delisted")

    def test_new_prices_and_yes_removes_entry(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _new_prices_frame()
        mock_ticker.return_value.info = {"longName": "Kenvue Inc."}
        ask = MagicMock(return_value="y")

        recheck_delisted_tickers(ask=ask)

        prompt = ask.call_args.args[0]
        self.assertIn("2026-11-03", prompt)
        self.assertIn("45.10", prompt)
        self.assertIn("Kenvue Inc.", prompt)
        self.assertEqual(self.read(), {})

    def test_new_prices_and_no_marks_never_recheck_and_stops_checking(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _new_prices_frame()
        mock_ticker.return_value.info = {"longName": "Some Other Corp"}

        recheck_delisted_tickers(ask=MagicMock(return_value="n"))
        self.assertEqual(self.read()["KVUE"]["status"], "never_recheck")

        # Next run: no Yahoo call, no prompt
        mock_ticker.reset_mock()
        ask = MagicMock()
        recheck_delisted_tickers(ask=ask)
        mock_ticker.assert_not_called()
        ask.assert_not_called()

    def test_no_terminal_keeps_entry_for_next_run(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _new_prices_frame()
        mock_ticker.return_value.info = {}

        recheck_delisted_tickers(ask=MagicMock(side_effect=EOFError))

        self.assertEqual(self.read()["KVUE"]["status"], "delisted")

    def test_unclear_answer_keeps_entry_for_next_run(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _new_prices_frame()
        mock_ticker.return_value.info = {}

        recheck_delisted_tickers(ask=MagicMock(return_value=""))

        self.assertEqual(self.read()["KVUE"]["status"], "delisted")


if __name__ == "__main__":
    unittest.main()
