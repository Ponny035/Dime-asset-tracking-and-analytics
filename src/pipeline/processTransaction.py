import os
import datetime

from dotenv import load_dotenv

from src.module.queryEmailRecord import query_emails
from src.module.PDFProcessing import process_pdf
from src.module.stockInfo import format_transaction
from src.module.importDataToGoogleSheet import import_invest_log_to_google_sheet


def process_investment_transactions(start_date=None, end_date=None):
    """
    Process investment transactions by reading emails, extracting PDF attachments, parsing transaction details,
    and importing them into a Google Sheet.

    Args:
        start_date (datetime.date, optional): The start date for the email search. Defaults to None.
        end_date (datetime.date, optional): The end date for the email search. Defaults to None.

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

    if start_date is None and end_date is None:
        today = datetime.date.today()
        last_month = (today.replace(day=1) - datetime.timedelta(days=1))
        start_date = last_month.replace(day=1)
        end_date = last_month.replace(day=last_month.day)

    print(start_date, end_date)

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
