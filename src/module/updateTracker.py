import os
import json
import logging
from datetime import datetime, date
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.util.auth import authenticate


def get_last_update_from_sheets(spreadsheet_id: str, range_name: str, auth_mode: str = "oauth") -> date:
    """
    Get the last update date from Google Sheets.

    Args:
        spreadsheet_id (str): The ID of the Google Sheet
        range_name (str): The range/cell containing the last update date
        auth_mode (str): Authentication mode - "oauth" or "service_account"

    Returns:
        date: The last update date, or None if not found
    """
    try:
        credentials = authenticate(auth_mode)
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        sheet = service.spreadsheets()

        result = (
            sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        )
        values = result.get("values", [])

        if values and values[0] and values[0][0]:
            last_update_str = values[0][0]
            return datetime.strptime(last_update_str, "%Y-%m-%d").date()
        else:
            return None

    except HttpError as err:
        logging.error(f"Error reading last update from sheets: {err}")
        return None
    except (ValueError, IndexError) as err:
        logging.error(f"Error parsing last update date: {err}")
        return None


def update_last_update_in_sheets(
    spreadsheet_id: str, range_name: str, update_date: date, auth_mode: str = "oauth"
) -> bool:
    """
    Update the last update date in Google Sheets.

    Args:
        spreadsheet_id (str): The ID of the Google Sheet
        range_name (str): The range/cell to update with the last update date
        update_date (date): The date to set as the last update
        auth_mode (str): Authentication mode - "oauth" or "service_account"

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        credentials = authenticate(auth_mode)
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        sheet = service.spreadsheets()

        values = [[update_date.strftime("%Y-%m-%d")]]
        body = {"values": values}

        result = (  # noqa: F841
            sheet.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )

        logging.info(f"Updated last update date in sheets: {update_date}")
        return True

    except HttpError as err:
        logging.error(f"Error updating last update in sheets: {err}")
        return False


def get_last_update_from_local_file(file_path: str) -> date:
    """
    Get the last update date from local JSON file.

    Args:
        file_path (str): Path to the local JSON file

    Returns:
        date: The last update date, or None if not found
    """
    try:
        if os.path.isfile(file_path):
            with open(file_path, "r") as file:
                existing_data = json.load(file)
                last_update_str = existing_data.get("update_time", "")
                if last_update_str:
                    return datetime.strptime(last_update_str, "%Y-%m-%d").date()
        return None
    except (json.JSONDecodeError, IOError, ValueError) as e:
        logging.warning(f"Problem reading local update file: {e}")
        return None


def update_last_update_in_local_file(file_path: str, update_date: date) -> bool:
    """
    Update the last update date in local JSON file.

    Args:
        file_path (str): Path to the local JSON file
        update_date (date): The date to set as the last update

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(file_path, "w") as file:
            json.dump({"update_time": update_date.strftime("%Y-%m-%d")}, file)
        logging.info(f"Updated last update date in local file: {update_date}")
        return True
    except IOError as e:
        logging.error(f"Failed to update local file: {e}")
        return False


def get_last_update_date(
    spreadsheet_id: str, sheets_range: str, local_file_path: str, auth_mode: str = "oauth"
) -> date:
    """
    Get the last update date, prioritizing Google Sheets as source of truth.
    Falls back to local file if sheets are unavailable.

    Args:
        spreadsheet_id (str): The ID of the Google Sheet
        sheets_range (str): The range/cell containing the last update date
        local_file_path (str): Path to the local JSON file
        auth_mode (str): Authentication mode - "oauth" or "service_account"

    Returns:
        date: The last update date, or None if not found anywhere
    """
    # Try Google Sheets first (source of truth)
    sheets_date = get_last_update_from_sheets(spreadsheet_id, sheets_range, auth_mode)
    if sheets_date is not None:
        logging.info(f"Got last update date from sheets: {sheets_date}")
        return sheets_date

    # Fall back to local file
    local_date = get_last_update_from_local_file(local_file_path)
    if local_date is not None:
        logging.info(f"Got last update date from local file: {local_date}")
        # Update sheets with the correct date from local file
        logging.info("Updating sheets with correct date from local file")
        update_last_update_in_sheets(spreadsheet_id, sheets_range, local_date, auth_mode)
        return local_date

    logging.info("No previous update date found")
    return None


def update_last_update_date(
    spreadsheet_id: str, sheets_range: str, local_file_path: str, update_date: date, auth_mode: str = "oauth"
) -> bool:
    """
    Update the last update date in both Google Sheets and local file.

    Args:
        spreadsheet_id (str): The ID of the Google Sheet
        sheets_range (str): The range/cell to update with the last update date
        local_file_path (str): Path to the local JSON file
        update_date (date): The date to set as the last update
        auth_mode (str): Authentication mode - "oauth" or "service_account"

    Returns:
        bool: True if at least one update succeeded, False if both failed
    """
    sheets_success = update_last_update_in_sheets(
        spreadsheet_id, sheets_range, update_date, auth_mode
    )
    local_success = update_last_update_in_local_file(local_file_path, update_date)

    if not sheets_success:
        logging.warning("Failed to update last update date in Google Sheets")
    if not local_success:
        logging.warning("Failed to update last update date in local file")

    return sheets_success or local_success