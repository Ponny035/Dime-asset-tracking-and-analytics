import os

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow


def authenticate() -> Credentials:
    """
    Authenticates the user and returns the credentials.

    Returns:
        Credentials: The authenticated credentials.
    """
    scope = ['https://www.googleapis.com/auth/spreadsheets']

    creds = None

    try:

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', scope)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scope)
                creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())
    except Exception as error:
        print(f"Authentication Error with \n{error}")

    return creds
