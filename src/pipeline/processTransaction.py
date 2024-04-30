import os
from datetime import datetime, time

import pytz
from dotenv import load_dotenv

from src.module.PDFProcessing import process_pdf
from src.module.assetTracking import query_investment_log, process_asset_log
from src.module.importDataToGoogleSheet import import_invest_log_to_google_sheet
from src.module.queryEmailRecord import query_emails
from src.module.stockInfo import format_transaction


def process_investment_transactions(start_date, end_date, user_timezone='Asia/Bangkok'):
    """
    Process investment transactions by reading emails, extracting PDF attachments, parsing transaction details,
    and importing them into a Google Sheet.

    Args:
        start_date (datetime.date, optional): The start date for the email search. Defaults to None.
        end_date (datetime.date, optional): The end date for the email search. Defaults to None.
        user_timezone (str): The user's timezone.

    Returns:
        None
    """

    # load the variables from .env
    load_dotenv()
    username = os.getenv('USERNAME')
    app_password = os.getenv('APP_PASSWORD')
    pdf_password = os.getenv('PDF_PASSWORD')
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    range_name = os.getenv('INVEST_LOG_RANGE_NAME')
    from_email = "no-reply@dime.co.th"
    subject_keyword = "Confirmation Note"

    temp_time = time(8, 30, 00)

    user_tz = pytz.timezone(user_timezone)
    bkk_tz = pytz.timezone('Asia/Bangkok')
    bkk_start_date = user_tz.localize(datetime.combine(start_date, temp_time)).astimezone(bkk_tz).date()
    bkk_end_date = user_tz.localize(datetime.combine(end_date, temp_time)).astimezone(bkk_tz).date()
    print("Bangkok Time Start Date : ", bkk_start_date)
    print("Bangkok Time End Date: ", bkk_end_date)

    # call the read_emails function with the start and end dates
    pdf_path_list = query_emails(start_date, end_date, username, app_password, from_email, subject_keyword)
    print(pdf_path_list)

    date_and_transactions = []
    for pdf_path in pdf_path_list:
        date, transactions = process_pdf(pdf_path, pdf_password)
        date_and_transactions.append([date, transactions])

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
            formated_transaction = format_transaction(price, commission, tax, amount, float(share),
                                                      stock_name, date, "Dime", transaction_type, "Done", "-")
            print(formated_transaction)
            import_invest_log_to_google_sheet(spreadsheet_id, range_name, "USER_ENTERED", [formated_transaction])

    return None


def process_asset_tracking(start_date, end_date, user_timezone):
    """
        Process asset logs by querying investment logs and updating asset tracking table according to each investment.

        Args:
            start_date (datetime.date): The start date for processing.
            end_date (datetime.date): The end date for processing.
            user_timezone (str): The user's timezone.

        Returns:
            None
        """
    # load the variables from .env
    load_dotenv()
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    range_name = os.getenv('INVEST_LOG_RANGE_NAME')
    asset_track_range_name = os.getenv('ASSET_TRACKING_RANGE_NAME')

    temp_time = time(8, 30, 00)

    user_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone('America/New_York')
    nyse_start_date = user_tz.localize(datetime.combine(start_date, temp_time)).astimezone(nyse_tz).date()
    nyse_end_date = user_tz.localize(datetime.combine(end_date, temp_time)).astimezone(nyse_tz).date()
    print("New York Time Start Date : ", nyse_start_date)
    print("New York Time End Date: ", nyse_end_date)

    print("get investment log")

    investment_log = query_investment_log(spreadsheet_id=spreadsheet_id, range_name=range_name,
                                          start_date=nyse_start_date,
                                          end_date=nyse_end_date)

    print("process asset log")
    process_asset_log(investment_log, spreadsheet_id, asset_track_range_name, start_date=nyse_start_date,
                      end_date=nyse_end_date)

    return None
