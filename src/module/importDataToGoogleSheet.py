from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.util.auth import authenticate


def import_invest_log_to_google_sheet(spreadsheet_id: str, range_name: str,
                                      value_input_option: str, transaction: list):
    """
    Imports the investment log to a Google Sheet.

    Args:
        spreadsheet_id (str): The ID of the spreadsheet.
        range_name (str): The range of cells to write the data.
        value_input_option (str): The value input option for the API.
        transaction (list): The transaction data to be imported.

    Returns:
        dict: The result of the API call.
    """
    try:
        
        credentials = authenticate()
        
        service = build('sheets', 'v4', credentials=credentials)
        body = {
            'values': transaction
        }
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption=value_input_option, body=body).execute()
        print(f"{result['updates']['updatedCells']} cells appended.")
        return result

    except HttpError as error:
        print(f"An error occurred: {error}")
        return error
