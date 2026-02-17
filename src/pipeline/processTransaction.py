import os
from datetime import datetime, time

import pytz
from dotenv import load_dotenv

from src.module.PDFProcessing import process_pdf
from src.module.assetTracking import query_investment_log, process_asset_log, process_asset_performance
from src.module.exportDataToGoogleSheet import export_invest_log_to_google_sheet
from src.module.queryEmailRecord import query_emails
from src.module.stockInfo import format_stock_transaction, format_option_transaction


def process_investment_transactions(start_date, end_date, user_timezone="Asia/Bangkok", auth_mode="oauth"):
    """
    Process investment transactions by reading emails, extracting PDF attachments, parsing transaction details,
    and importing them into a Google Sheet.

    Args:
        start_date (datetime.date, optional): The start date for the email search. Defaults to None.
        end_date (datetime.date, optional): The end date for the email search. Defaults to None.
        user_timezone (str): The user's timezone.
        auth_mode (str): Authentication mode - "oauth" or "service_account".

    Returns:
        None
    """

    # load the variables from .env
    load_dotenv()
    email_address = os.getenv("EMAIL")
    app_password = os.getenv("APP_PASSWORD")
    pdf_password = os.getenv("PDF_PASSWORD")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    stock_range_name = os.getenv("US_STOCK_INVEST_LOG_RANGE_NAME")
    option_range_name = os.getenv("US_STOCK_OPTION_INVEST_LOG_RANGE_NAME")
    from_email = "no-reply@dime.co.th"
    subject_keyword = "Confirmation Note"

    temp_time = time(8, 30, 00)

    user_tz = pytz.timezone(user_timezone)
    bkk_tz = pytz.timezone("Asia/Bangkok")
    bkk_start_date = (
        user_tz.localize(datetime.combine(start_date, temp_time))
        .astimezone(bkk_tz)
        .date()
    )
    bkk_end_date = (
        user_tz.localize(datetime.combine(end_date, temp_time))
        .astimezone(bkk_tz)
        .date()
    )
    print("Bangkok Time Start Date : ", bkk_start_date)
    print("Bangkok Time End Date: ", bkk_end_date)

    # call the read_emails function with the start and end dates
    pdf_path_list = query_emails(
        start_date, end_date, email_address, app_password, from_email, subject_keyword
    )
    print(pdf_path_list)

    date_and_transactions = []
    for pdf_path in pdf_path_list:
        date, transactions, option_transactions = process_pdf(pdf_path, pdf_password)
        date_and_transactions.append([date, transactions, option_transactions])

    for transactions in date_and_transactions:
        date = transactions[0].strftime("%Y-%m-%d")
        for transaction in transactions[1]:
            transaction_type = transaction[0]
            stock_name = transaction[1]
            share = transaction[2]
            price = transaction[3]
            commission = transaction[4]
            tax = transaction[5]
            amount = transaction[6]
            formated_stock_transaction = format_stock_transaction(
                price,
                commission,
                tax,
                amount,
                float(share),
                stock_name,
                date,
                "Dime",
                transaction_type,
                "Done",
                "-",
            )
            print(formated_stock_transaction)
            export_invest_log_to_google_sheet(
                spreadsheet_id, stock_range_name, "USER_ENTERED", [formated_stock_transaction], auth_mode
            )

        for option_transactions in transactions[2]:
            transaction_type = option_transactions[0]
            stock_name = option_transactions[1]
            right = option_transactions[2]
            strike = option_transactions[3]
            expiry = option_transactions[4].strftime("%Y-%m-%d")
            contract = option_transactions[5]
            price = option_transactions[6]
            commission = option_transactions[7]
            withholding_tax = option_transactions[8]
            amount = option_transactions[9]          
            formated_option_transaction = format_option_transaction(
                price,
                commission,
                withholding_tax,
                amount,
                strike,
                contract,
                date,
                expiry,
                transaction_type,
                right,
                stock_name,
                "Dime",
                "Done",
                "-"
            )
            print(formated_option_transaction)
            export_invest_log_to_google_sheet(
                spreadsheet_id, option_range_name, "USER_ENTERED", [formated_option_transaction], auth_mode
            )
    return None


def process_asset_tracking(start_date, end_date, user_timezone, auth_mode="oauth"):
    """
    Process asset logs by querying investment logs and updating asset tracking table according to each investment.

    Args:
        start_date (datetime.date): The start date for processing.
        end_date (datetime.date): The end date for processing.
        user_timezone (str): The user's timezone.
        auth_mode (str): Authentication mode - "oauth" or "service_account".

    Returns:
        None
    """
    # load the variables from .env
    load_dotenv()
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    stock_range_name = os.getenv("US_STOCK_INVEST_LOG_RANGE_NAME")
    asset_track_stock_range_name = os.getenv("ASSET_TRACKING_STOCK_RANGE_NAME")

    temp_time = time(8, 30, 00)

    user_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone("America/New_York")
    nyse_start_date = (
        user_tz.localize(datetime.combine(start_date, temp_time))
        .astimezone(nyse_tz)
        .date()
    )
    nyse_end_date = (
        user_tz.localize(datetime.combine(end_date, temp_time))
        .astimezone(nyse_tz)
        .date()
    )
    print("New York Time Start Date : ", nyse_start_date)
    print("New York Time End Date: ", nyse_end_date)

    print("get investment log")

    investment_log = query_investment_log(
        spreadsheet_id=spreadsheet_id,
        range_name=stock_range_name,
        start_date=nyse_start_date,
        end_date=nyse_end_date,
        auth_mode=auth_mode,
    )

    print("process asset log")
    
    # Get update tracker parameters
    last_update_range = os.getenv("LAST_UPDATE_RANGE_NAME")
    local_file = "last_update_information.json"
    update_tracker_params = {
        'update_range': last_update_range,
        'local_file': local_file
    } if last_update_range else None
    
    process_asset_log(
        investment_log,
        spreadsheet_id,
        asset_track_stock_range_name,
        start_date=nyse_start_date,
        end_date=nyse_end_date,
        auth_mode=auth_mode,
        update_tracker_params=update_tracker_params,
    )

    return None
