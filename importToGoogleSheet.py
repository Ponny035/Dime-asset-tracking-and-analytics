import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def authenticate():
    """
    Authenticates the user and returns the credentials.

    Returns:
        Credentials: The authenticated credentials.
    """
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def import_invest_log_to_google_sheet(creds: Credentials, spreadsheet_id: str, range_name: str,
                                      value_input_option: str, transaction: list):
    """
    Imports the investment log to a Google Sheet.

    Args:
        creds (Credentials): The authenticated credentials.
        spreadsheet_id (str): The ID of the spreadsheet.
        range_name (str): The range of cells to write the data.
        value_input_option (str): The value input option for the API.
        transaction (list): The transaction data to be imported.

    Returns:
        dict: The result of the API call.
    """
    try:
        service = build('sheets', 'v4', credentials=creds)
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
