import yfinance as yf
import pandas_market_calendars as mcal
import pytz
import pandas as pd
import time
import logging
import os
import tempfile

from typing import Literal
from datetime import datetime, timedelta
from finvizfinance.quote import finvizfinance
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError, YFTzMissingError

from src.exceptions import StockPriceFetchError, TickerNotFoundError
from src.module.delistedTickers import (
    STATUS_NEVER_RECHECK,
    load_delisted,
    mark_delisted,
    mark_never_recheck,
    unmark_delisted,
)

# Give each process its own yfinance cache directory to avoid SQLite locking
# when multiple downloads run in quick succession
_yf_cache_dir = os.path.join(tempfile.gettempdir(), f'py-yfinance-{os.getpid()}')
os.makedirs(_yf_cache_dir, exist_ok=True)
yf.set_tz_cache_location(_yf_cache_dir)





# Session-level cache so each ticker's split history is fetched only once per run
_splits_cache: dict = {}


def get_splits_in_range(ticker: str, from_date, to_date) -> pd.Series:
    """
    Returns each split/reverse-split event for *ticker* that occurred strictly
    after *from_date* and on or before *to_date* as a pd.Series
    (DatetimeIndex → ratio, e.g. 10.0 for a 10-for-1 split).
    Returns an empty Series when there are no events in the window.
    """
    global _splits_cache
    if ticker not in _splits_cache:
        try:
            raw = yf.Ticker(ticker).splits
            # yfinance may return a DataFrame (e.g. with a "Stock Splits" column)
            # or a Series directly depending on version.  Normalise to a Series.
            if isinstance(raw, pd.DataFrame):
                if "Stock Splits" in raw.columns:
                    splits = raw["Stock Splits"]
                elif not raw.empty:
                    splits = raw.iloc[:, 0]
                else:
                    splits = pd.Series(dtype=float)
            else:
                splits = raw
            # Normalise to a plain tz-naive DatetimeIndex regardless of what
            # yfinance returns (object index, tz-aware DatetimeIndex, etc.)
            if not splits.empty:
                if not isinstance(splits.index, pd.DatetimeIndex):
                    splits.index = pd.to_datetime(splits.index, utc=True).tz_convert(None)
                elif splits.index.tz is not None:
                    splits.index = splits.index.tz_convert(None)
            _splits_cache[ticker] = splits
        except Exception as e:
            logging.warning(f"Could not fetch split data for {ticker}: {e}")
            _splits_cache[ticker] = pd.Series(dtype=float)

    splits = _splits_cache[ticker]
    if splits.empty:
        return pd.Series(dtype=float)

    from_ts = pd.Timestamp(from_date)
    to_ts = pd.Timestamp(to_date)
    return splits[(splits.index > from_ts) & (splits.index <= to_ts)]


def get_split_factor(ticker: str, from_date, to_date) -> float:
    """
    Returns the cumulative split/reverse-split factor for *ticker* for any
    corporate actions that occurred strictly after *from_date* and on or
    before *to_date*.

    Returns 1.0 when no splits occurred in that window.
    A 2-for-1 split returns 2.0; a 1-for-10 reverse split returns 0.1.
    """
    relevant = get_splits_in_range(ticker, from_date, to_date)
    if relevant.empty:
        return 1.0
    return float(relevant.prod())


CLASSIFICATION_KEYS = ("Sector", "Industry")


def _is_missing(value) -> bool:
    return value is None or str(value).strip() in ("", "-", "None", "nan")


def get_known_classifications(investment_log: pd.DataFrame | None) -> dict:
    """
    Collect the latest non-missing Sector and Industry per ticker from earlier
    invest-log rows, to fill in what finviz/yfinance can't find.

    Args:
        investment_log (pd.DataFrame | None): Invest log (first column is the date).

    Returns:
        dict: {ticker: {"Sector": ..., "Industry": ...}} — keys only present when known.
    """
    known = {}
    if investment_log is None or investment_log.empty:
        return known
    for _, row in investment_log.sort_values(investment_log.columns[0]).iterrows():
        entry = known.setdefault(row["Product Name"], {})
        for key in CLASSIFICATION_KEYS:
            if not _is_missing(row.get(key)):
                entry[key] = str(row[key])
    return known


def get_stock_basic_info(stock_name: str = "AAPL", known_classifications: dict | None = None) -> dict:
    """
    Retrieves basic information about a stock.
    Tries finvizfinance first, falls back to yfinance if finviz scraping fails.
    A Sector/Industry neither source has is taken from an earlier transaction of
    the same ticker (known_classifications), otherwise set to "-".

    Args:
        stock_name (str): The name of the stock. Default is "AAPL" (Apple Inc.).
        known_classifications (dict, optional): Output of get_known_classifications().

    Returns:
        dict: A dictionary containing the basic information of the stock.
    """
    info = _fetch_stock_basic_info(stock_name)
    known = (known_classifications or {}).get(stock_name, {})
    for key in CLASSIFICATION_KEYS:
        if not _is_missing(info[key]):
            continue
        if key in known:
            logging.info(f"{stock_name}: {key} not found online, using '{known[key]}' from an earlier transaction")
            info[key] = known[key]
        else:
            logging.warning(f"{stock_name}: {key} not found online or in earlier transactions, using '-'")
            info[key] = "-"
    return info


def _fetch_stock_basic_info(stock_name: str) -> dict:
    try:
        stock = finvizfinance(stock_name)
        stock_fundament = stock.ticker_fundament()
        return {
            "Company": str(stock_fundament["Company"]),
            "Sector": str(stock_fundament["Sector"]),
            "Industry": str(stock_fundament["Industry"]),
            "Country": str(stock_fundament["Country"]),
            "Dividend": str(stock_fundament.get("Dividend TTM", "-")),
        }
    except Exception as finviz_err:
        logging.warning(f"finvizfinance failed for {stock_name} ({finviz_err}), falling back to yfinance")

    info = yf.Ticker(stock_name).info
    if not info or info.get("quoteType") is None:
        raise RuntimeError(f"Both finvizfinance and yfinance failed to fetch info for {stock_name}")
    dividend = info.get("trailingAnnualDividendRate") or info.get("dividendRate")
    return {
        "Company": str(info.get("longName") or info.get("shortName") or stock_name),
        "Sector": str(info.get("sector") or "-"),
        "Industry": str(info.get("industry") or "-"),
        "Country": str(info.get("country") or "-"),
        "Dividend": str(dividend) if dividend else "-",
    }


def format_stock_transaction(
    price: float,
    commission: float,
    tax: float,
    amount: float,
    share: float,
    stock_name: str = "AAPL",
    date: datetime = datetime.today(),
    portfolio: str = "Dime",
    transaction_type: Literal["BUY", "SEL", "DIV"] = "BUY",
    status: str = "Done",
    note: str = "-",
    known_classifications: dict | None = None,
) -> list:
    """
    Formats a transaction into a list with detailed information.

    Args:
        price (float): The price of the transaction.
        commission (float): The commission for the transaction.
        tax (float): The tax for the transaction.
        amount (float): The total amount of the transaction.
        share (float): The number of shares involved in the transaction.
        stock_name (str): The name of the stock. Default is "AAPL" (Apple Inc.).
        date (datetime): The date of the transaction. Default is the current date and time.
        portfolio (str): The name of the portfolio. Default is "Dime".
        transaction_type (Literal['BUY', 'SEL', 'DIV']): The type of the transaction. Default is 'BUY'.
        status (str): The status of the transaction. Default is "Done".
        note (str): The note of the transaction. Default is "-".
        known_classifications (dict, optional): Sector/Industry from earlier transactions,
            used when finviz/yfinance can't find them (see get_known_classifications).

    Returns:
        list: A list representing the formatted transaction with detailed information.
    """
    stock_info = get_stock_basic_info(stock_name, known_classifications)
    has_dividend = stock_info["Dividend"] != "-"
    if transaction_type != "SEL":
        total_amount = round(amount + (commission + tax), 2)
    else:
        total_amount = round(amount - (commission + tax), 2) * -1
        amount = -amount
        share = -share

    transaction = [
        date,
        portfolio,
        transaction_type,
        stock_name,
        stock_info["Sector"],
        stock_info["Industry"],
        has_dividend,
        price,
        commission,
        tax,
        amount,
        total_amount,
        share,
        status,
        note,
    ]
    return transaction


def format_option_transaction(
    price: float,
    commission: float,
    tax: float,
    amount: float,
    strike: float,
    contract: float,
    date: datetime = datetime.today(),
    expiry: datetime = datetime.today(),
    transaction_type: Literal["BUY", "SEL", "DIV"] = "BUY",
    right: Literal["PUT", "CALL"] = "CALL",
    stock_name: str = "AAPL",
    portfolio: str = "Dime",
    status: str = "Done",
    note: str = "-",
    known_classifications: dict | None = None,
) -> list:
    """
    Formats a transaction into a list with detailed information.

    Args:
        price (float): The price of the transaction.
        commission (float): The commission for the transaction.
        tax (float): The tax for the transaction.
        amount (float): The total amount of the transaction.
        strike (float): The strike price of option involved in the transaction.
        contract (float): The number of contract. (1 contract is equal to 100 shares)
        date (datetime): The date of the transaction. Default is the current date and time.
        expiry (datetime): The expriation date of the option.
        transaction_type (Literal['BUY', 'SEL', 'DIV']): The type of the transaction. Default is 'BUY'.
        right (Literal['PUT', 'CALL']): The type of the option. Default is 'CALL'.
        stock_name (str): The name of the stock. Default is "AAPL" (Apple Inc.).
        portfolio (str): The name of the portfolio. Default is "Dime".
        status (str): The status of the transaction. Default is "Done".
        note (str): The note of the transaction. Default is "-".
        known_classifications (dict, optional): Sector/Industry from earlier transactions,
            used when finviz/yfinance can't find them (see get_known_classifications).

    Returns:
        list: A list representing the formatted transaction with detailed information.
    """
    stock_info = get_stock_basic_info(stock_name, known_classifications)
    if transaction_type != "SEL":
        total_amount = round(amount + (commission + tax), 2)
    else:
        total_amount = round(amount - (commission + tax), 2) * -1
        amount = -amount
        contract = -contract

    transaction = [
        date,
        portfolio,
        transaction_type,
        stock_name,
        stock_info["Sector"],
        stock_info["Industry"],
        right,
        strike,
        expiry,
        contract,
        price,
        commission,
        tax,
        amount,
        total_amount,
        status,
        note,
    ]
    return transaction


def get_last_available_trading_day_closing_price(
    stock_name: str, target_date: datetime, user_timezone: str = "Asia/Bangkok"
) -> float | None:
    """
    Retrieves the closing price of a stock on the specific trading date prior to or on the given date,
    adjusted for the user's timezone.

    Args:
        stock_name (str): The ticker symbol of the stock for which the closing price is being fetched.
        target_date (datetime): The date for which the closing price is desired, specified in the user's local timezone.
            This function will find the closing price for the last trading day on or before this date.
        user_timezone (str): The timezone of the user, defaulting to 'Asia/Bangkok'. This is used to ensure that
            the date calculations are accurate according to the user's local time.

    Returns:
        float | None: The closing price of the stock as a float if available. If the stock market was closed on
            the target date and no trading data is available, or if any errors occur during the data fetch,
            returns None.

    Description:
        This function is designed to handle the complexities of fetching stock closing prices across different
        timezones, accounting for the New York Stock Exchange (NYSE) trading calendar. It automatically adjusts
        the input date from the user's local timezone to the NYSE timezone to determine the last available trading day.
        Then, it fetches the closing price for that day using the 'yfinance' library. This is particularly useful for
        international users who need to reconcile local dates with NYSE trading days for accurate financial analyses or
    portfolio management.

    The function first converts the target_date from the user's local timezone to the NYSE timezone and then
    calculates the last available trading day. If the target_date falls on a non-trading day (e.g., weekend or
    holiday), the function finds the most recent previous trading day. It then fetches the closing price for the
    stock on that day. This approach ensures that users always get the relevant closing price data for their
    financial calculations, regardless of their timezone or the specific trading calendar of the NYSE.

    Example Usage:
        # Fetch the closing price for Apple Inc. (AAPL) on or before October 15, 2023, from Bangkok, Thailand.
        closing_price = get_last_available_trading_day_closing_price('AAPL', datetime(2023, 10, 15), 'Asia/Bangkok')
        if closing_price is not None:
            print(f"Last available trading day's closing price for AAPL: ${closing_price}")
        else:
            print("Closing price data is not available for the specified date.")
    """

    # Create a NYSE calendar
    nyse = mcal.get_calendar("NYSE")

    # Convert target_date to NYSE timezone
    user_tz = pytz.timezone(user_timezone)
    print(stock_name, target_date, user_timezone)
    nyse_tz = pytz.timezone("America/New_York")
    target_date = user_tz.localize(target_date).astimezone(nyse_tz)

    # Adjust the date for trading day search
    adjusted_date = target_date
    trading_days = nyse.valid_days(
        start_date="1900-01-01", end_date=adjusted_date.strftime("%Y-%m-%d")
    )
    if len(trading_days) == 0:
        print("No Trading day found")
        return None  # No trading days found up to this date

    last_trading_day = trading_days[-1].date()
    print(last_trading_day)
    # Convert last trading day back to user's timezone for the yfinance request
    last_trading_day_nyse_tz = nyse_tz.localize(
        datetime.combine(last_trading_day, datetime.min.time())
    )
    last_trading_day_user_tz = last_trading_day_nyse_tz.astimezone(user_tz).date()

    # Fetch stock data
    try:
        stock_data = yf.download(
            stock_name,
            start=last_trading_day_user_tz.strftime("%Y-%m-%d"),
            end=(last_trading_day_user_tz + timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=False,
        )
        if not stock_data.empty:
            return round(stock_data["Close"][stock_name].iloc[-1], 2)
    except Exception as e:
        print(f"An error occurred while fetching the stock price: {e}")
        return None

# Per-ticker fetch outcomes returned by _history()
HISTORY_OK = "ok"
HISTORY_TRANSIENT = "transient"      # rate limited / network error — worth retrying
HISTORY_MISSING = "missing"          # "possibly delisted; no price data found"
HISTORY_NO_SYMBOL = "no_symbol"      # Yahoo has no metadata for the symbol at all

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 0.15
RATE_LIMIT_BACKOFF_SECONDS = 5
DELISTED_LOOKBACK_DAYS = 365
# A ticker must have missed at least this many NYSE sessions to count as delisted,
# so a close Yahoo simply hasn't published yet is not mistaken for a delisting
DELISTED_MIN_MISSED_SESSIONS = 2


def _extract_close(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """
    Return raw['Close'] as a DataFrame with one column per ticker and a tz-naive index.
    Handles both flat columns (Close is a Series) and yfinance 1.x MultiIndex columns
    (Close is a DataFrame, even for a single ticker).
    """
    close = raw['Close']
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    elif len(tickers) == 1:
        close = close.rename(columns={close.columns[0]: tickers[0]})
    else:
        close = close.copy()
    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    return close


def _history(ticker: str, start: str, end: str) -> tuple[str, pd.Series, str]:
    """
    Fetch one ticker's closing prices with Ticker.history, which (unlike yf.download)
    raises typed errors so a rate limit can be told apart from a delisting.

    Returns:
        (status, closes, reason): status is one of the HISTORY_* constants, closes is a
        non-NaN Series with a tz-naive index (empty unless status is HISTORY_OK).
    """
    empty = pd.Series(dtype=float)
    previous = yf.config.debug.hide_exceptions
    yf.config.debug.hide_exceptions = False
    try:
        raw = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    except YFRateLimitError as e:
        return HISTORY_TRANSIENT, empty, str(e)
    except YFTzMissingError as e:
        return HISTORY_NO_SYMBOL, empty, str(e)
    except YFPricesMissingError as e:
        return HISTORY_MISSING, empty, str(e)
    except Exception as e:
        # Network errors and anything unexpected are treated as transient
        return HISTORY_TRANSIENT, empty, repr(e)
    finally:
        yf.config.debug.hide_exceptions = previous

    if raw is None or raw.empty or 'Close' not in raw.columns:
        return HISTORY_MISSING, empty, "no price data returned"
    closes = _extract_close(raw, [ticker])[ticker].dropna()
    # Yahoo can return its last bar even when it falls outside [start, end) — drop those rows
    closes = closes[(closes.index >= pd.Timestamp(start)) & (closes.index < pd.Timestamp(end))]
    if closes.empty:
        return HISTORY_MISSING, empty, f"no price data between {start} and {end}"
    return HISTORY_OK, closes, ""


def _confirm_delisted(
    ticker: str,
    start_date: datetime,
    yf_start: str,
    yf_end: str,
    trading_days: pd.DatetimeIndex,
    last_known_close: dict[str, float],
) -> tuple[pd.Timestamp, float]:
    """
    Called after Yahoo reported no prices for *ticker* in the requested window.
    Looks back DELISTED_LOOKBACK_DAYS to decide whether the ticker stopped trading.

    Yahoo sometimes removes the whole history of an acquired ticker. In that case the
    caller's last recorded close (e.g. from the asset tracking sheet) is used instead.

    Returns:
        (last_trade_date, last_close) when the ticker is confirmed delisted.

    Raises:
        TickerNotFoundError: Yahoo has no price history at all and there is no recorded close.
        StockPriceFetchError: the check was inconclusive (rate limited, or the last
            price is too recent to rule out Yahoo simply being late).
    """
    lookback_start = (start_date.date() - timedelta(days=DELISTED_LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    status, closes, reason = _history(ticker, lookback_start, yf_end)
    if status in (HISTORY_NO_SYMBOL, HISTORY_MISSING):
        if ticker in last_known_close:
            # Yahoo dropped the ticker entirely; the last trade was before this window
            days_before = trading_days[trading_days < pd.Timestamp(start_date.date())]
            last_trade_date = days_before[-1] if len(days_before) else pd.Timestamp(start_date.date()) - timedelta(days=1)
            logging.warning(
                f"{ticker}: Yahoo has no price history at all any more ({reason}); "
                f"using last recorded close {float(last_known_close[ticker]):.2f}"
            )
            return last_trade_date, float(last_known_close[ticker])
        logging.error(f"{ticker}: no price history in the last {DELISTED_LOOKBACK_DAYS} days ({reason})")
        raise TickerNotFoundError(ticker)
    if status == HISTORY_TRANSIENT:
        logging.warning(f"{ticker}: could not confirm delisting — {reason}")
        raise StockPriceFetchError(ticker)

    last_trade_date = closes.index[-1]
    if last_trade_date >= pd.Timestamp(yf_start):
        # Yahoo does have prices in the window after all, so the earlier miss was transient
        raise StockPriceFetchError(ticker)

    missed_sessions = trading_days[trading_days > last_trade_date]
    if len(missed_sessions) < DELISTED_MIN_MISSED_SESSIONS:
        logging.warning(
            f"{ticker}: no price since {last_trade_date.date()}, but only {len(missed_sessions)} "
            "NYSE session(s) missed — Yahoo may just be late, not treating it as delisted"
        )
        raise StockPriceFetchError(ticker)
    return last_trade_date, float(closes.iloc[-1])


def get_bulk_available_trading_day_closing_price(
    ticker: list[str],
    start_date: datetime,
    end_date: datetime,
    user_timezone: str = 'Asia/Bangkok',
    fill: Literal['ffill', 'bfill', 'zero', 'nan'] | None = None,
    last_known_close: dict[str, float] | None = None,
) -> pd.DataFrame | None:
    """
    Fetch closing prices for multiple stock tickers within a given date range,
    adjusting for the user's timezone.

    Args:
        ticker (list[str]): List of stock ticker symbols (e.g., ['AAPL', 'MSFT']).
        start_date (datetime): Start of the date range (in user's local timezone).
        end_date (datetime): End of the date range (in user's local timezone).
        user_timezone (str, optional): User's timezone (default: 'Asia/Bangkok').
        fill: Fill strategy for non-trading days:
            • None: Return only trading days (default)
            • 'ffill': Forward-fill last known price
            • 'bfill': Back-fill next known price
            • 'zero': Fill missing days with 0
            • 'nan': Insert missing days as NaN
        last_known_close (dict[str, float], optional): Last recorded close per ticker
            (e.g. from the asset tracking sheet). Used when Yahoo has dropped a ticker's
            whole history, so an acquired holding is not mistaken for an unknown symbol.

    Returns:
        pd.DataFrame | None: DataFrame with dates as index and tickers as columns,
                            containing closing prices. Returns None if no data available.

    Raises:
        StockPriceFetchError: A ticker could not be fetched after retries (e.g. rate limited).
        TickerNotFoundError: Yahoo has no price history at all for a ticker.

    Notes:
        - Converts dates from user's timezone to NYSE timezone for trading day calculations.
        - Fetches closing prices for all valid trading days in the range using yfinance.
        - If fill is specified, adds non-trading days and applies the chosen fill strategy.
        - For 'ffill', automatically fetches data from the last trading day before start_date
          to ensure no NaN values at the beginning.
        - Delisted / acquired tickers: when Yahoo has no prices in the window but the ticker
          traded before and has missed at least DELISTED_MIN_MISSED_SESSIONS NYSE sessions,
          it is recorded in delisted_tickers.json and its last real close is returned for
          every row. Tickers already in that file are not fetched for windows after their
          last trade date (see recheck_delisted_tickers for how they come back).
        - Returns None if no trading days are found or data is unavailable.

    Example:
        # Get raw trading day data only
        data = get_bulk_available_trading_day_closing_price(
            ['AAPL', 'MSFT'],
            datetime(2025, 6, 16),
            datetime(2025, 6, 23)
        )

        # Get data with weekends forward-filled
        data_filled = get_bulk_available_trading_day_closing_price(
            ['AAPL', 'MSFT'],
            datetime(2025, 6, 16),
            datetime(2025, 6, 23),
            fill='ffill'
        )
    """
    nyse = mcal.get_calendar('NYSE')
    user_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone('America/New_York')

    # Convert end_date to NYSE timezone
    if end_date.tzinfo is None:
        end_date_nyse = user_tz.localize(end_date).astimezone(nyse_tz)
    else:
        end_date_nyse = end_date.astimezone(nyse_tz)

    # Trading days from 30 days before start_date (ffill lookback) up to the adjusted end date
    trading_days = nyse.valid_days(
        start_date=(start_date.date() - timedelta(days=30)).strftime('%Y-%m-%d'),
        end_date=end_date_nyse.strftime('%Y-%m-%d'),
        tz='America/New_York'
    )
    if len(trading_days) == 0:
        return None
    trading_days = trading_days.tz_localize(None).normalize()
    start_ts = pd.Timestamp(start_date.date())
    end_ts = pd.Timestamp(end_date.date())

    try:
        # Determine fetch start based on fill strategy
        if fill == 'ffill':
            # Find last trading day before start_date using NYSE calendar
            trading_days_before = trading_days[trading_days < start_ts]

            if len(trading_days_before) > 0:
                # Fetch from the last trading day before start_date
                last_trading_day = trading_days_before[-1].date()
                yf_start = last_trading_day.strftime('%Y-%m-%d')
            else:
                # Fallback: no trading days found in lookback period
                yf_start = start_date.strftime('%Y-%m-%d')
        else:
            yf_start = start_date.strftime('%Y-%m-%d')

        # yfinance end date is exclusive, so add one day
        yf_end = (end_date.date() + timedelta(days=1)).strftime('%Y-%m-%d')

        # Tickers already known to be delisted before this window use their last close, no fetch
        known_delisted = load_delisted()
        delisted = {
            t: float(known_delisted[t]['last_close'])
            for t in ticker
            if t in known_delisted and pd.Timestamp(known_delisted[t]['last_trade_date']) < start_ts
        }
        live = [t for t in ticker if t not in delisted]

        # Bulk download — threads=False prevents SQLite lock contention in yfinance cache
        data = pd.DataFrame()
        if live:
            try:
                data = yf.download(live, start=yf_start, end=yf_end, progress=False, auto_adjust=False, threads=False)
            except Exception as e:
                logging.error(f"Bulk download failed: {e}")

        close_data = _extract_close(data, live) if not data.empty else pd.DataFrame()

        # Retry only tickers that came back missing/all-NaN individually
        missing = [t for t in live if t not in close_data.columns or close_data[t].isna().all()]
        if missing:
            logging.warning(f"Bulk download missing {missing}, retrying individually...")
            for t in missing:
                for attempt in range(MAX_RETRIES):
                    time.sleep(RETRY_SLEEP_SECONDS)
                    status, closes, reason = _history(t, yf_start, yf_end)
                    if status == HISTORY_OK:
                        # Drop the all-NaN placeholder column before assigning
                        if t in close_data.columns:
                            close_data = close_data.drop(columns=[t])
                        close_data = pd.concat([close_data, closes.rename(t).to_frame()], axis=1)
                        break
                    if status in (HISTORY_MISSING, HISTORY_NO_SYMBOL):
                        last_trade_date, last_close = _confirm_delisted(
                            t, start_date, yf_start, yf_end, trading_days, last_known_close or {}
                        )
                        logging.warning(
                            f"{t}: no price data since {last_trade_date.date()} — likely delisted/acquired. "
                            f"Using last close {last_close:.2f}. Record the corporate action to stop tracking it."
                        )
                        mark_delisted(t, last_trade_date, last_close, reason)
                        delisted[t] = last_close
                        break
                    logging.warning(f"{t}: attempt {attempt + 1}/{MAX_RETRIES} failed — {reason}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1))
                else:
                    raise StockPriceFetchError(t)

        if close_data.empty:
            if not delisted:
                return None
            # Only delisted tickers: build the rows their last close is attached to
            if fill is None:
                index = trading_days[(trading_days >= start_ts) & (trading_days <= end_ts)]
            else:
                index = pd.date_range(start=start_ts, end=end_ts, freq='D')
            if len(index) == 0:
                return None
            close_data = pd.DataFrame(index=index)

        if fill is not None:
            # Create complete date range INCLUDING any historical data we fetched
            if fill == 'ffill' and yf_start < start_date.strftime('%Y-%m-%d'):
                # Extend range to include the historical start date
                full_range = pd.date_range(
                    start=yf_start,  # Start from where we fetched
                    end=end_date.date(),
                    freq='D'
                )
            else:
                full_range = pd.date_range(
                    start=start_date.date(),
                    end=end_date.date(),
                    freq='D'
                )

            # Reindex to include all calendar days
            close_data = close_data.reindex(full_range)

            # Apply fill strategy
            if fill == 'ffill':
                close_data = close_data.ffill()
            elif fill == 'bfill':
                close_data = close_data.bfill()
            elif fill == 'zero':
                close_data = close_data.fillna(0)
            elif fill == 'nan':
                pass

            # Trim to only the requested date range
            requested_range = pd.date_range(
                start=start_date.date(),
                end=end_date.date(),
                freq='D'
            )
            close_data = close_data.loc[requested_range]

        # Delisted tickers keep their last real close on every row
        for t, last_close in delisted.items():
            close_data[t] = last_close

        result = close_data.round(2)

        # Validate that all requested tickers have data for the requested range
        missing_tickers = [t for t in ticker if t not in result.columns or result[t].isna().all()]
        partial_tickers = [t for t in ticker if t in result.columns and result[t].isna().any() and not result[t].isna().all()]
        if missing_tickers:
            logging.error(f"Validation failed: no data at all for {missing_tickers}")
        if partial_tickers:
            logging.warning(f"Validation warning: partial NaN values for {partial_tickers}")
        if not missing_tickers and not partial_tickers:
            logging.info(f"Validation passed: all {len(ticker)} tickers have complete data")

        return result

    except StockPriceFetchError:
        raise  # Always propagate so callers can handle exhausted retries
    except Exception as e:
        logging.error(f"get_bulk_available_trading_day_closing_price failed: {e}", exc_info=True)

    return None


def _company_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info or {}
        return str(info.get("longName") or info.get("shortName") or "unknown")
    except Exception:
        return "unknown"


def recheck_delisted_tickers(ask=input) -> None:
    """
    Run once at startup. For each ticker in delisted_tickers.json (except those marked
    never_recheck), check whether Yahoo has prices after its last trade date. If it does,
    show the evidence and ask the user whether it is the same stock:
        • yes → remove it from the file so it goes back to the normal price flow
        • no  → mark it never_recheck (the symbol was reused by another company)
    Any other answer, or no terminal to answer from, leaves it as is and asks again next run.

    Args:
        ask: Function used to prompt the user (default: input). Injectable for tests.
    """
    known = load_delisted()
    for t, info in known.items():
        if info.get("status") == STATUS_NEVER_RECHECK:
            continue

        last_trade_date = pd.Timestamp(info["last_trade_date"])
        last_close = float(info["last_close"])
        status, closes, reason = _history(
            t,
            (last_trade_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d'),
        )
        if status == HISTORY_TRANSIENT:
            logging.warning(f"{t}: could not re-check delisted status ({reason}), will try again next run")
            continue
        if status != HISTORY_OK:
            logging.info(f"{t}: still no price data since {last_trade_date.date()}, keeping it as delisted")
            continue

        first_new_date = closes.index[0]
        new_close = float(closes.iloc[0])
        gap_sessions = len(mcal.get_calendar('NYSE').valid_days(
            start_date=(last_trade_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            end_date=first_new_date.strftime('%Y-%m-%d'),
        )) - 1
        change = (new_close - last_close) / last_close * 100 if last_close else float('nan')
        prompt = (
            f"\n{t} was marked delisted (last close {last_close:.2f} on {last_trade_date.date()}), "
            f"but Yahoo has prices again from {first_new_date.date()}.\n"
            f"  new close: {new_close:.2f} ({change:+.1f}% vs last close), "
            f"gap: {gap_sessions} trading day(s), Yahoo name now: {_company_name(t)}\n"
            f"  If this is NOT the stock you hold (symbol reused by another company), answer n.\n"
            f"Bring {t} back to normal price tracking? [y/n]: "
        )
        logging.warning(f"{t}: has prices again from {first_new_date.date()}, asking user to confirm")
        try:
            answer = ask(prompt).strip().lower()
        except EOFError:
            logging.warning(f"{t}: no terminal to confirm relisting, will ask again next run")
            continue

        if answer in ("y", "yes"):
            unmark_delisted(t)
            logging.info(f"{t}: removed from delisted list, back to normal price tracking")
        elif answer in ("n", "no"):
            mark_never_recheck(t)
            logging.info(f"{t}: kept at last close {last_close:.2f}, will not be re-checked again")
        else:
            logging.warning(f"{t}: no clear answer, will ask again next run")

def check_valid_trading_date(
    target_date: datetime, user_timezone: str = "Asia/Bangkok"
) -> bool:
    """
    Check if a given date is a valid trading date in the NYSE calendar.

    Args:
        target_date (datetime): The date to check for trading validity.
        user_timezone (str, optional): The user's timezone. Defaults to 'Asia/Bangkok'.

    Returns:
        bool: True if the target_date is a valid trading date, False otherwise.
    """
    # Create a NYSE calendar
    nyse_calendar = mcal.get_calendar("NYSE")

    # Convert target_date to NYSE timezone
    local_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone("America/New_York")
    local_target_date = local_tz.localize(target_date).astimezone(nyse_tz)
    trading_days = nyse_calendar.valid_days(
        start_date=local_target_date.strftime("%Y-%m-%d"),
        end_date=local_target_date.strftime("%Y-%m-%d"),
    )

    if len(trading_days) == 0:
        return False  # No trading days found up to this date
    return True
