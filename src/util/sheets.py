import logging
import socket
import time as _time

from googleapiclient.errors import HttpError


def sheets_execute(request, max_retries: int = 3, base_delay: float = 2.0):
    """
    Execute a Google Sheets API request with exponential backoff retry.

    Retries on transient network errors (TimeoutError, socket.timeout, OSError,
    ConnectionError) and on rate-limit / server-side HTTP errors (429, 500, 502,
    503, 504). Non-retryable HttpErrors (e.g. 403, 404) are re-raised immediately.

    Delay sequence: 2 s → 4 s → 8 s (base_delay * 2^attempt).
    """
    for attempt in range(max_retries):
        try:
            return request.execute()
        except (TimeoutError, socket.timeout, OSError, ConnectionError) as exc:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logging.warning(
                f"Sheets API network error (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {delay:.0f}s: {exc}"
            )
            _time.sleep(delay)
        except HttpError as exc:
            if exc.resp.status in (429, 500, 502, 503, 504):
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt)
                logging.warning(
                    f"Sheets API HTTP {exc.resp.status} (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay:.0f}s"
                )
                _time.sleep(delay)
            else:
                raise
