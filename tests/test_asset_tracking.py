"""
Tests for src/module/assetTracking.py

Focus areas:
- Stock split detection and audit-trail SEL/BUY injection
- Idempotency: splits already recorded in the invest log are not re-added
- Dry-run mode: no sheet writes, diagnostic print instead
- Correct post-split share count in the asset tracking output
- process_asset_log parameter plumbing (invest_log_range_name)
"""
import unittest
from datetime import date, datetime
from unittest.mock import call, patch, MagicMock

import numpy as np
import pandas as pd

from src.module.assetTracking import process_asset_log


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_investment_log(extra_rows=None):
    """Minimal invest-log DataFrame (all 15 sheet columns, one original BUY)."""
    rows = [
        {
            "Date": pd.Timestamp("2024-01-15"),
            "Port": "Dime",
            "Type": "BUY",
            "Product Name": "AAPL",
            "Sector": "Technology",
            "Industry": "Consumer Electronics",
            "Have Dividend": True,
            "Stock Price (USD)": 185.0,
            "Commission (USD)": 0.0,
            "Tax (USD)": 0.0,
            "Amount (USD)": 185.0,
            "Total Amount (USD)": 185.0,
            "Share": 1.0,
            "Status": "Done",
            "Note": "-",
        }
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return pd.DataFrame(rows)


def _make_asset_log():
    """
    Minimal asset-tracking-sheet DataFrame as returned by query_investment_log.
    Mirrors the 13-column schema written by process_asset_log.
    """
    return pd.DataFrame(
        [
            {
                "Date": pd.Timestamp("2024-06-09"),
                "Is Market Open": True,
                "Port": "Dime",
                "Product Name": "AAPL",
                "Sector": "Technology",
                "Industry": "Consumer Electronics",
                "Share": 1.0,
                "Amount (USD)": 185.0,
                "Total Amount (USD)": 185.0,
                "Closing Stock Price": 190.0,
                "Valuation": 190.0,
                "Performance": 0.027,
                "Total Performance": 0.027,
            }
        ]
    )


def _make_closing_prices(date_str="2024-06-10", ticker="AAPL", price=190.0):
    """Single-row DataFrame that looks like the output of get_bulk_…_closing_price."""
    idx = pd.to_datetime([date_str])
    return pd.DataFrame({ticker: [price]}, index=idx)


# ---------------------------------------------------------------------------
# Common patches used by every test in the suite
# ---------------------------------------------------------------------------
COMMON_PATCHES = [
    "src.module.assetTracking.query_investment_log",
    "src.module.assetTracking.check_valid_trading_date",
    "src.module.assetTracking.get_splits_in_range",
    "src.module.assetTracking.get_bulk_available_trading_day_closing_price",
    "src.module.assetTracking.export_invest_log_to_google_sheet",
]


class TestProcessAssetLogSplitDetection(unittest.TestCase):
    """
    Tests that verify the audit-trail SEL/BUY injection when a stock split is
    detected during process_asset_log.
    """

    PROCESS_DATE = date(2024, 6, 10)  # Monday — market open
    SPLIT_FACTOR = 4.0
    ORIGINAL_SHARES = 1.0
    EXPECTED_NEW_SHARES = round(ORIGINAL_SHARES * SPLIT_FACTOR, 7)

    def _run(self, investment_log, mocks, is_dry_run=False):
        """Call process_asset_log with standard test parameters."""
        mock_query, mock_trading, mock_splits, mock_prices, mock_export = mocks
        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series(
            {pd.Timestamp("2024-06-10"): self.SPLIT_FACTOR}
        )
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=is_dry_run,
            investment_log=investment_log,
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=self.PROCESS_DATE,
            end_date=self.PROCESS_DATE,
            auth_mode="oauth",
            invest_log_range_name="US Invest Log!A:O",
        )

        return mock_export

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_split_writes_sel_and_buy_rows_to_invest_log(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """When a split is detected the SEL+BUY audit rows must be written to the invest log."""
        mock_export = self._run(_make_investment_log(), (mock_query, mock_trading, mock_splits, mock_prices, mock_export))

        # At least one call must target the invest log range with split rows
        invest_log_calls = [
            c for c in mock_export.call_args_list
            if c.args[1] == "US Invest Log!A:O"
        ]
        self.assertTrue(invest_log_calls, "No call to export for invest log range")

        rows = invest_log_calls[0].args[3]
        types = [r[2] for r in rows]
        self.assertIn("SEL", types)
        self.assertIn("BUY", types)

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_split_rows_have_stock_split_note(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """SEL and BUY rows must carry 'Stock Split' in the Note field (index 14)."""
        mock_export = self._run(_make_investment_log(), (mock_query, mock_trading, mock_splits, mock_prices, mock_export))

        invest_log_calls = [
            c for c in mock_export.call_args_list
            if c.args[1] == "US Invest Log!A:O"
        ]
        rows = invest_log_calls[0].args[3]
        for row in rows:
            self.assertEqual(row[14], "Stock Split", f"Expected Note='Stock Split', got {row[14]!r}")

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_sel_row_negates_original_shares(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """SEL row Share (index 12) must equal −original_shares."""
        mock_export = self._run(_make_investment_log(), (mock_query, mock_trading, mock_splits, mock_prices, mock_export))

        invest_log_calls = [c for c in mock_export.call_args_list if c.args[1] == "US Invest Log!A:O"]
        rows = invest_log_calls[0].args[3]
        sel_row = next(r for r in rows if r[2] == "SEL")
        self.assertAlmostEqual(sel_row[12], -self.ORIGINAL_SHARES)

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_buy_row_has_post_split_shares(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """BUY row Share (index 12) must equal original_shares × factor."""
        mock_export = self._run(_make_investment_log(), (mock_query, mock_trading, mock_splits, mock_prices, mock_export))

        invest_log_calls = [c for c in mock_export.call_args_list if c.args[1] == "US Invest Log!A:O"]
        rows = invest_log_calls[0].args[3]
        buy_row = next(r for r in rows if r[2] == "BUY")
        self.assertAlmostEqual(buy_row[12], self.EXPECTED_NEW_SHARES)

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_split_rows_have_zero_cost_basis(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """Splits must not change cost basis: Amount and Total Amount must be 0."""
        mock_export = self._run(_make_investment_log(), (mock_query, mock_trading, mock_splits, mock_prices, mock_export))

        invest_log_calls = [c for c in mock_export.call_args_list if c.args[1] == "US Invest Log!A:O"]
        rows = invest_log_calls[0].args[3]
        for row in rows:
            self.assertEqual(row[10], 0.00, f"Amount (USD) should be 0, got {row[10]}")
            self.assertEqual(row[11], 0.00, f"Total Amount (USD) should be 0, got {row[11]}")


class TestProcessAssetLogSplitIdempotency(unittest.TestCase):
    """
    Tests that splits already recorded in the invest log are NOT written again
    on subsequent runs (re-run safety).
    """

    PROCESS_DATE = date(2024, 6, 10)
    SPLIT_FACTOR = 4.0

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_skips_split_already_in_invest_log(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """
        If investment_log already contains a 'Stock Split' entry for this ticker
        and date, no second pair of SEL/BUY rows should be written.
        """
        # investment_log already has the SEL+BUY from a prior run
        already_recorded = _make_investment_log(
            extra_rows=[
                {
                    "Date": pd.Timestamp("2024-06-10"),
                    "Port": "Dime",
                    "Type": "SEL",
                    "Product Name": "AAPL",
                    "Sector": "Technology",
                    "Industry": "Consumer Electronics",
                    "Have Dividend": True,
                    "Stock Price (USD)": 0,
                    "Commission (USD)": 0.0,
                    "Tax (USD)": 0.0,
                    "Amount (USD)": 0.0,
                    "Total Amount (USD)": 0.0,
                    "Share": -1.0,
                    "Status": "Done",
                    "Note": "Stock Split",
                },
                {
                    "Date": pd.Timestamp("2024-06-10"),
                    "Port": "Dime",
                    "Type": "BUY",
                    "Product Name": "AAPL",
                    "Sector": "Technology",
                    "Industry": "Consumer Electronics",
                    "Have Dividend": True,
                    "Stock Price (USD)": 0,
                    "Commission (USD)": 0.0,
                    "Tax (USD)": 0.0,
                    "Amount (USD)": 0.0,
                    "Total Amount (USD)": 0.0,
                    "Share": 4.0,
                    "Status": "Done",
                    "Note": "Stock Split",
                },
            ]
        )

        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series({pd.Timestamp("2024-06-10"): self.SPLIT_FACTOR})
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=False,
            investment_log=already_recorded,
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=self.PROCESS_DATE,
            end_date=self.PROCESS_DATE,
            auth_mode="oauth",
            invest_log_range_name="US Invest Log!A:O",
        )

        invest_log_calls = [
            c for c in mock_export.call_args_list
            if c.args[1] == "US Invest Log!A:O"
        ]
        self.assertEqual(
            len(invest_log_calls), 0,
            "Should not write duplicate split rows when already recorded in invest log",
        )

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_no_split_means_no_invest_log_write(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """When get_splits_in_range returns empty, the invest log must not be touched."""
        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series(dtype=float)  # no splits
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=False,
            investment_log=_make_investment_log(),
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=date(2024, 6, 10),
            end_date=date(2024, 6, 10),
            auth_mode="oauth",
            invest_log_range_name="US Invest Log!A:O",
        )

        invest_log_calls = [
            c for c in mock_export.call_args_list
            if c.args[1] == "US Invest Log!A:O"
        ]
        self.assertEqual(len(invest_log_calls), 0)


class TestProcessAssetLogDryRun(unittest.TestCase):
    """
    Tests that dry-run mode suppresses all sheet writes including split rows.
    """

    PROCESS_DATE = date(2024, 6, 10)

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_dry_run_does_not_write_split_rows_to_sheet(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series({pd.Timestamp("2024-06-10"): 4.0})
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=True,
            investment_log=_make_investment_log(),
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=self.PROCESS_DATE,
            end_date=self.PROCESS_DATE,
            auth_mode="oauth",
            invest_log_range_name="US Invest Log!A:O",
        )

        mock_export.assert_not_called()

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_dry_run_does_not_write_asset_tracking_sheet(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """The asset tracking sheet must also not be updated in dry-run mode."""
        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series(dtype=float)
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=True,
            investment_log=_make_investment_log(),
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=self.PROCESS_DATE,
            end_date=self.PROCESS_DATE,
            auth_mode="oauth",
            invest_log_range_name="US Invest Log!A:O",
        )

        mock_export.assert_not_called()


class TestProcessAssetLogShareCount(unittest.TestCase):
    """
    Tests that the share count in the asset tracking output reflects the split.
    """

    PROCESS_DATE = date(2024, 6, 10)
    SPLIT_FACTOR = 4.0
    ORIGINAL_SHARES = 1.0

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_asset_tracking_output_has_post_split_shares(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        """
        The asset tracking sheet write must contain the post-split share count,
        not the original (pre-split) count.
        """
        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series({pd.Timestamp("2024-06-10"): self.SPLIT_FACTOR})
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=False,
            investment_log=_make_investment_log(),
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=self.PROCESS_DATE,
            end_date=self.PROCESS_DATE,
            auth_mode="oauth",
            invest_log_range_name="US Invest Log!A:O",
        )

        asset_tracking_calls = [
            c for c in mock_export.call_args_list
            if c.args[1] == "Asset tracking!A:M"
        ]
        self.assertTrue(asset_tracking_calls, "Expected a write to the asset tracking sheet")

        written_rows = asset_tracking_calls[-1].args[3]
        # Written as list-of-lists; column order from final_df:
        # Date, Is Market Open, Port, Product Name, Sector, Industry,
        # Share, Amount (USD), Total Amount (USD), Closing Stock Price,
        # Valuation, Performance, Total Performance
        # Share is at index 6
        aapl_rows = [r for r in written_rows if r[3] == "AAPL"]
        self.assertTrue(aapl_rows, "No AAPL row found in asset tracking output")
        written_share = aapl_rows[0][6]
        expected = round(self.ORIGINAL_SHARES * self.SPLIT_FACTOR, 7)
        self.assertAlmostEqual(
            float(written_share), expected,
            msg=f"Expected post-split shares {expected}, got {written_share}",
        )


class TestProcessAssetLogInvestLogRangeName(unittest.TestCase):
    """
    When invest_log_range_name is None, split detection is skipped entirely.
    """

    @patch("src.module.assetTracking.export_invest_log_to_google_sheet")
    @patch("src.module.assetTracking.get_bulk_available_trading_day_closing_price")
    @patch("src.module.assetTracking.get_splits_in_range")
    @patch("src.module.assetTracking.check_valid_trading_date")
    @patch("src.module.assetTracking.query_investment_log")
    def test_no_split_detection_without_invest_log_range(
        self, mock_query, mock_trading, mock_splits, mock_prices, mock_export
    ):
        mock_query.return_value = _make_asset_log()
        mock_trading.return_value = True
        mock_splits.return_value = pd.Series({pd.Timestamp("2024-06-10"): 4.0})
        mock_prices.return_value = _make_closing_prices()

        process_asset_log(
            is_dry_run=False,
            investment_log=_make_investment_log(),
            spreadsheet_id="test_sheet_id",
            asset_log_range_name="Asset tracking!A:M",
            start_date=date(2024, 6, 10),
            end_date=date(2024, 6, 10),
            auth_mode="oauth",
            invest_log_range_name=None,  # not provided
        )

        # get_splits_in_range should never be called
        mock_splits.assert_not_called()
        # No invest-log writes
        invest_log_calls = [
            c for c in mock_export.call_args_list
            if c.args[1] is None
        ]
        self.assertEqual(len(invest_log_calls), 0)


if __name__ == "__main__":
    unittest.main()
