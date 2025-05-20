import os
import time
import json
import logging
import requests

from datetime import datetime
from typing import Optional


# === Logging Setup ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def get_financial_institutions_holidays_api(
    client_id: str, retries: int = 3, delay_sec: int = 2
) -> Optional[dict]:
    """
    Fetch financial institution holidays from the BOT public API with retries.

    Args:
        client_id (str): The IBM Client ID for API authentication.
        retries (int): Number of retry attempts on failure.
        delay_sec (int): Delay in seconds between retries.

    Returns:
        dict | None: Parsed API response or None if the request fails.
    """
    url = (
        "https://apigw1.bot.or.th/bot/public/"
        "financial-institutions-holidays/?year=2025"
    )
    headers = {'X-IBM-Client-Id': client_id}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()['result']
            return result
        except (requests.RequestException, ValueError, KeyError) as e:
            logging.warning(f"Attempt {attempt}: API call failed - {e}")
            if attempt < retries:
                time.sleep(delay_sec)
            else:
                logging.error("All retries failed. Giving up.")
                return None


def update_financial_institutions_holidays(client_id: str) -> bool:
    """
    Update local holiday JSON if not already updated today.

    Args:
        client_id (str): The IBM Client ID for API authentication.

    Returns:
        bool: True if update was successful or not needed, False if API failed.
    """
    file_name = "financial_institutions_holidays.json"
    today = datetime.now().strftime('%Y-%m-%d')

    # Step 1: Check existing file
    if os.path.isfile(file_name):
        try:
            with open(file_name, 'r') as file:
                existing_data = json.load(file)
                if existing_data.get("update_time", "").startswith(today):
                    logging.info("No update needed. Already updated today.")
                    return True
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Problem reading existing file: {e}. Proceeding with update.")

    # Step 2: Fetch new data from API
    api_result = get_financial_institutions_holidays_api(client_id)
    if api_result is None:
        return False

    try:
        update_time = api_result['timestamp']
        holiday_date = [day['Date'] for day in api_result['data']]
    except (KeyError, TypeError) as e:
        logging.error(f"Unexpected response structure: {e}")
        return False

    # Step 3: Save to file
    data_to_save = {
        "update_time": update_time,
        "holidays": holiday_date
    }

    try:
        with open(file_name, 'w') as file:
            json.dump(data_to_save, file, indent=2)
        logging.info(f"Holiday data written to {file_name}")
        return True
    except IOError as e:
        logging.error(f"Failed to write holiday data: {e}")
        return False
