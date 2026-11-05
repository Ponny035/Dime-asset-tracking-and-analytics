import json
import logging
import os
from datetime import date

# Local notebook of tickers that stopped trading (delisted / acquired)
DELISTED_TICKERS_FILE = "delisted_tickers.json"

STATUS_DELISTED = "delisted"
STATUS_NEVER_RECHECK = "never_recheck"


def load_delisted() -> dict:
    """
    Load the delisted-ticker notebook.

    Returns:
        dict: {ticker: {"status", "last_trade_date", "last_close", "detected_on", "reason"}}.
              Empty dict if the file is missing or unreadable.
    """
    try:
        if os.path.isfile(DELISTED_TICKERS_FILE):
            with open(DELISTED_TICKERS_FILE, "r") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
                logging.warning(f"{DELISTED_TICKERS_FILE} is not a JSON object, ignoring it")
        return {}
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Problem reading {DELISTED_TICKERS_FILE}: {e}")
        return {}


def _save_delisted(data: dict) -> bool:
    try:
        with open(DELISTED_TICKERS_FILE, "w") as file:
            json.dump(data, file, indent=2)
        return True
    except IOError as e:
        logging.error(f"Failed to write {DELISTED_TICKERS_FILE}: {e}")
        return False


def mark_delisted(ticker: str, last_trade_date: date, last_close: float, reason: str) -> bool:
    """Record *ticker* as delisted with its last real trading day and close."""
    data = load_delisted()
    data[ticker] = {
        "status": STATUS_DELISTED,
        "last_trade_date": last_trade_date.strftime("%Y-%m-%d"),
        "last_close": round(float(last_close), 2),
        "detected_on": date.today().strftime("%Y-%m-%d"),
        "reason": reason,
    }
    return _save_delisted(data)


def unmark_delisted(ticker: str) -> bool:
    """Remove *ticker* from the notebook so it goes back to the normal price flow."""
    data = load_delisted()
    if data.pop(ticker, None) is None:
        return True
    return _save_delisted(data)


def mark_never_recheck(ticker: str) -> bool:
    """Keep *ticker* frozen at its last close and stop re-checking it on future runs."""
    data = load_delisted()
    if ticker not in data:
        return False
    data[ticker]["status"] = STATUS_NEVER_RECHECK
    return _save_delisted(data)
