import os
import time
import socket
from typing import Optional
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError

# Load environment variables
load_dotenv()


def _retry_with_backoff(func, max_retries: int, timeout: int):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries (int): Maximum number of retry attempts
        timeout (int): Timeout for socket operations
        
    Returns:
        Result of successful function call
        
    Raises:
        Exception: Last exception if all retries fail
    """
    for attempt in range(max_retries):
        try:
            # Set socket timeout for this attempt
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(timeout)
            
            result = func()
            
            # Restore original timeout
            socket.setdefaulttimeout(original_timeout)
            return result
            
        except (socket.timeout, TimeoutError, RefreshError, OSError) as e:
            # Restore original timeout
            socket.setdefaulttimeout(original_timeout)
            
            if attempt == max_retries - 1:  # Last attempt
                raise e
                
            # Exponential backoff: 1, 2, 4 seconds
            wait_time = 2 ** attempt
            print(f"Authentication attempt {attempt + 1} failed: {e}")
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            
        except Exception as e:
            # Restore original timeout
            socket.setdefaulttimeout(original_timeout)
            raise e


def authenticate(auth_mode: str = "oauth", timeout: Optional[int] = None, max_retries: Optional[int] = None) -> Optional[Credentials]:
    """
    Authenticates the user and returns the credentials.

    Args:
        auth_mode (str): Authentication mode - "oauth" or "service_account"
                        - "oauth": Uses token.json for interactive authentication
                        - "service_account": Uses credentials.json for server authentication
        timeout (Optional[int]): Timeout in seconds for authentication requests. 
                                Defaults to AUTH_TIMEOUT env var or 30 seconds.
        max_retries (Optional[int]): Maximum number of retry attempts for failed requests. 
                                    Defaults to AUTH_MAX_RETRIES env var or 3 attempts.

    Returns:
        Optional[Credentials]: The authenticated credentials, or None if authentication fails.
    """
    # Get configuration from environment variables or use defaults
    if timeout is None:
        timeout = int(os.getenv('AUTH_TIMEOUT', '30'))
    if max_retries is None:
        max_retries = int(os.getenv('AUTH_MAX_RETRIES', '3'))
        
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
                    # Retry token refresh with backoff
                    def refresh_token():
                        creds.refresh(Request())
                        return creds
                    
                    creds = _retry_with_backoff(refresh_token, max_retries, timeout)
                else:
                    # Retry OAuth flow with backoff
                    def oauth_flow():
                        flow = InstalledAppFlow.from_client_secrets_file(
                            "credentials.json", scope
                        )
                        return flow.run_local_server(port=0, open_browser=False)
                    
                    creds = _retry_with_backoff(oauth_flow, max_retries, timeout)
                
                # Save token only after successful authentication
                with open("token.json", "w") as token:
                    token.write(creds.to_json())
        except (socket.timeout, TimeoutError) as error:
            print(f"OAuth Authentication Timeout: {error}")
            print("Authentication timed out. Please check your network connection and try again.")
            return None
        except RefreshError as error:
            print(f"OAuth Token Refresh Error: {error}")
            print("Token refresh failed. Please re-authenticate by removing token.json and running again.")
            return None
        except FileNotFoundError as error:
            print(f"OAuth Configuration Error: {error}")
            print("credentials.json file not found. Please ensure it exists for OAuth authentication.")
            return None
        except Exception as error:
            print(f"OAuth Authentication Error: {error}")
            return None

        return creds
