import os
import json
import logging
import datetime as dt
import argparse
from dotenv import load_dotenv

from src.pipeline.processTransaction import process_asset_tracking
from src.pipeline.processTransaction import process_investment_transactions
from src.module.checkThaiHoliday import update_financial_institutions_holidays
from src.module.updateTracker import get_last_update_date, update_last_update_date

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
token_id = os.getenv("BOT_API_TOKEN_ID")
spreadsheet_id = os.getenv("SPREADSHEET_ID")
last_update_range = os.getenv("LAST_UPDATE_RANGE_NAME")
auth_mode = os.getenv("AUTH_MODE", "oauth")


def is_working_day(date):
    # Check if it's weekend (5 = Saturday, 6 = Sunday)
    if date.weekday() >= 5:
        return False

    # Read holidays from JSON file
    try:
        with open("financial_institutions_holidays.json", "r") as file:
            holidays_data = json.load(file)
            holidays = holidays_data.get("holidays", [])

            # Check if the date is in holidays list
            date_str = date.strftime("%Y-%m-%d")
            return date_str not in holidays
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error reading holidays file: {e}")
        return True  # If we can't read the file, assume it's a working day


file_name = "last_update_information.json"
user_timezone = "Asia/Bangkok"


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Process investment transactions and asset tracking"
    )
    parser.add_argument(
        "-m",
        "--manual",
        action="store_true",
        help="Run in manual mode (bypass working day check)",
    )
    args = parser.parse_args()

    # Get today's date
    today = dt.datetime.now().date()

    # Update holidays information
    print("Updating holidays information")
    update_financial_institutions_holidays(token_id)

    # Check if today is a working day (skip if manual mode)
    if not args.manual and not is_working_day(today):
        logging.info("Today is a holiday or weekend. Skipping processing.")
        logging.info("Use -m or --manual flag to bypass this check.")
        exit()

    # Get the last update date from Google Sheets (source of truth) with local file fallback
    last_update = get_last_update_date(spreadsheet_id, last_update_range, file_name, auth_mode)

    if last_update and not args.manual and last_update == today:
        logging.info('"investment log" No update needed. Already updated today.')
        logging.info("Use -m or --manual flag to force update.")
        exit()
    elif last_update:
        start_date = last_update + dt.timedelta(days=1)
        end_date = today
    else:
        # If no previous update found, start with today's date
        start_date = today
        end_date = today

    print(f"Processing from {start_date} to {end_date}")
    # Call the functions with the specified dates
    process_investment_transactions(start_date, end_date, user_timezone, auth_mode)
    process_asset_tracking(start_date, end_date, user_timezone, auth_mode)

    # Update the last update time after successful processing (both sheets and local file)
    update_success = update_last_update_date(
        spreadsheet_id, last_update_range, file_name, today, auth_mode
    )
    if not update_success:
        logging.error(
            "Failed to update last update date in both Google Sheets and local file"
        )


if __name__ == "__main__":
    main()
