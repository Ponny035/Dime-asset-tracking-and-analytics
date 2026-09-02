import os
import logging
import datetime as dt
import argparse
from dotenv import load_dotenv

from src.exceptions import StockPriceFetchError, StartDateError
from src.pipeline.processTransaction import process_asset_tracking
from src.pipeline.processTransaction import process_investment_transactions
from src.module.checkThaiHoliday import update_financial_institutions_holidays
from src.module.updateTracker import get_last_update_date, update_last_update_date
from src.util.check_validity import check_working_day

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
token_id = os.getenv("BOT_API_TOKEN_ID")
spreadsheet_id = os.getenv("SPREADSHEET_ID")
last_update_range = os.getenv("LAST_UPDATE_RANGE_NAME")
last_invest_log_update_range = os.getenv("LAST_INVEST_LOG_UPDATE_RANGE_NAME")
last_asset_log_update_range = os.getenv("LAST_ASSET_LOG_UPDATE_RANGE_NAME")
last_performance_log_update_range = os.getenv("LAST_PERFORMANCE_LOG_UPDATE_RANGE_NAME")
auth_mode = os.getenv("AUTH_MODE", "oauth")


last_update_file_name = "last_update_information.json"
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
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Simulate execution without writing to sheets",
    )

    parser.add_argument(
        "-s",
        "--start-date",
        type=dt.date.fromisoformat,
        help='Manual start date input in ISO format (YYYY-MM-DD) eg. -s \'2026-09-01\'',
    )

    parser.add_argument(
        "-e",
        "--end-date",
        type=dt.date.fromisoformat,
        help='Manual end date input in ISO format (YYYY-MM-DD) eg. -e \'2026-09-01\'',
    )
    args = parser.parse_args()

    if args.dry_run:
        logging.info("Dry run mode")
        logging.info("Simulate execution without writing")
    
    # Get today's date
    today = dt.datetime.now().date()

    # Update holidays information
    logging.info("Updating holidays information")
    update_financial_institutions_holidays(token_id)

    # Check if today is a working day (skip if manual mode)
    if not args.manual and not check_working_day(today):
        logging.info("Today is a holiday or weekend. Skipping processing.")
        logging.info("Use -m or --manual flag to bypass this check.")
        exit()

    # Get the last update date from Google Sheets (source of truth) with local file fallback
    last_update = get_last_update_date(spreadsheet_id, last_update_range, last_update_file_name, auth_mode)
    # last_invest_log_update = get_last_update_date(spreadsheet_id, last_invest_log_update_range, last_update_file_name, auth_mode)
    # last_asset_log_update = get_last_update_date(spreadsheet_id, last_asset_log_update_range, last_update_file_name, auth_mode)
    # last_performance_log_update = get_last_update_date(spreadsheet_id, last_performance_log_update_range, last_update_file_name, auth_mode)

    if last_update and not args.manual and last_update == today and not args.start_date:
        logging.info('"investment log" No update needed. Already updated today.')
        logging.info("Use -m or --manual flag to force update.")
        exit()
    elif last_update: # check start date first the end the last update 
        if args.start_date and args.end_date:
            start_date = args.start_date
            end_date = args.end_date
        elif args.start_date and not args.end_date:
            start_date = args.start_date
            end_date = today
        elif not args.start_date and args.end_date:
            start_date = last_update + dt.timedelta(days=1)
            end_date = args.end_date
        else:
            start_date = last_update + dt.timedelta(days=1)
            end_date = today
    else:
        if args.start_date and args.end_date:
            start_date = args.start_date
            end_date = args.end_date
        elif args.start_date and not args.end_date:
            start_date = args.start_date
            end_date = today
        elif not args.start_date and args.end_date:
            start_date = today
            end_date = args.end_date
        else:
            start_date = today
            end_date = today
    if start_date > end_date:
        logging.error(
            f"The start date ({start_date}) must be on or before the end date ({end_date}). Please check the dates and try again."
        )
        exit()

    logging.info(f"Processing from {start_date} to {end_date}")
    try:
        process_investment_transactions(args.dry_run, start_date, end_date, user_timezone, auth_mode) 
        process_asset_tracking(args.dry_run, start_date, end_date, user_timezone, auth_mode)
    except StockPriceFetchError as e:
        logging.error(
            f"Failed to fetch stock price for '{e}' after all retries. "
            "All changes have been rolled back. "
            "Please wait at least 15 minutes before running again."
        )
        raise SystemExit(1)
    except StartDateError as e:
            logging.error(
                f"Unable to fetch stock prices: {e} "
                "Please correct the start and end dates, then try again."
            )
            raise SystemExit(1)

    # Update the last update time after successful processing (both sheets and local file)
    if not args.dry_run:
        update_success = update_last_update_date(
            spreadsheet_id, last_update_range, last_update_file_name, end_date, auth_mode
        )
        if not update_success:
            logging.error(
                "Failed to update last update date in both Google Sheets and local file"
            )
    else:
        logging.warning("Failed to update last update date in Google Sheets due to dry run")


if __name__ == "__main__":
    main()
