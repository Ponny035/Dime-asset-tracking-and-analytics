import os

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow


def authenticate(auth_mode: str = "oauth") -> Credentials:
    """
    Authenticates the user and returns the credentials.

    Args:
        auth_mode (str): Authentication mode - "oauth" or "service_account"
                        - "oauth": Uses token.json for interactive authentication
                        - "service_account": Uses credentials.json for server authentication

    Returns:
        Credentials: The authenticated credentials.
    """
    scope = ["https://www.googleapis.com/auth/spreadsheets"]

    if auth_mode == "service_account":
        # Service Account mode (for server/automated use)
        try:
            if os.path.exists("credentials.json"):
                creds = ServiceAccountCredentials.from_service_account_file(
                    "credentials.json", scopes=scope
                )
                return creds
            else:
                raise FileNotFoundError("credentials.json not found for service account authentication")
        except Exception as error:
            print(f"Service Account Authentication Error: {error}")
            return None

    else:
        # OAuth mode (for interactive use) - default
        creds = None
        try:
            if os.path.exists("token.json"):
                creds = Credentials.from_authorized_user_file("token.json", scope)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "credentials.json", scope
                    )
                    creds = flow.run_local_server(port=0, open_browser=False)

                with open("token.json", "w") as token:
                    token.write(creds.to_json())
        except Exception as error:
            print(f"OAuth Authentication Error: {error}")

        return creds
