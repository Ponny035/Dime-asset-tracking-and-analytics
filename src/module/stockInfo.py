from typing import Literal
from datetime import datetime, timedelta
from finvizfinance.quote import finvizfinance
import yfinance as yf
import pandas_market_calendars as mcal
import pytz
import pandas as pd

def get_stock_basic_info(stock_name: str = "AAPL") -> dict:
    """
    Retrieves basic information about a stock from the FinvizFinance API.

    Args:
        stock_name (str): The name of the stock. Default is "AAPL" (Apple Inc.).

    Returns:
        dict: A dictionary containing the basic information of the stock.
    """
    stock = finvizfinance(stock_name)
    stock_fundament = stock.ticker_fundament()

    stock_basic_info = {
        "Company": str(stock_fundament["Company"]),
        "Sector": str(stock_fundament["Sector"]),
        "Industry": str(stock_fundament["Industry"]),
        "Country": str(stock_fundament["Country"]),
        "Dividend": str(stock_fundament["Dividend TTM"])
    }
    return stock_basic_info


def format_transaction(price: float, commission: float, tax: float, amount: float, share: float,
                       stock_name: str = "AAPL", date: datetime = datetime.today(), portfolio: str = "Dime",
                       transaction_type: Literal['BUY', 'SEL', 'DIV'] = 'BUY',
                       status: str = "Done", note: str = "-") -> list:
    """
    Formats a transaction into a list with detailed information.

    Args:
        price (float): The price of the transaction.
        commission (float): The commission for the transaction.
        tax (float): The tax for the transaction.
        amount (float): The total amount of the transaction.
        share (float): The number of shares involved in the transaction.
        stock_name (str): The name of the stock. Default is "AAPL" (Apple Inc.).
        date (datetime): The date of the transaction. Default is the current date and time.
        portfolio (str): The name of the portfolio. Default is "Dime".
        transaction_type (Literal['BUY', 'SEL', 'DIV']): The type of the transaction. Default is 'BUY'.
        status (str): The status of the transaction. Default is "Done".
        note (str): The note of the transaction. Default is "-".

    Returns:
        list: A list representing the formatted transaction with detailed information.
    """
    stock_info = get_stock_basic_info(stock_name)
    has_dividend = stock_info['Dividend'] != '-'
    if transaction_type != "SEL":
        total_amount = round(amount + (commission + tax), 2)
    else:
        total_amount = round(amount - (commission + tax), 2) * -1
        amount = -amount
        share = -share

    transaction = [
        date, portfolio, transaction_type, stock_name, stock_info['Sector'], stock_info['Industry'], has_dividend,
        price, commission, tax, amount, total_amount, share, status, note
    ]
    return transaction


def get_last_available_trading_day_closing_price(stock_name: str, target_date: datetime,
                                                 user_timezone: str = 'Asia/Bangkok') -> float | None:
    """
    Retrieves the closing price of a stock on the specific trading date prior to or on the given date,
    adjusted for the user's timezone.

    Args:
        stock_name (str): The ticker symbol of the stock for which the closing price is being fetched.
        target_date (datetime): The date for which the closing price is desired, specified in the user's local timezone.
            This function will find the closing price for the last trading day on or before this date.
        user_timezone (str): The timezone of the user, defaulting to 'Asia/Bangkok'. This is used to ensure that
            the date calculations are accurate according to the user's local time.

    Returns:
        float | None: The closing price of the stock as a float if available. If the stock market was closed on
            the target date and no trading data is available, or if any errors occur during the data fetch,
            returns None.

    Description:
        This function is designed to handle the complexities of fetching stock closing prices across different
        timezones, accounting for the New York Stock Exchange (NYSE) trading calendar. It automatically adjusts
        the input date from the user's local timezone to the NYSE timezone to determine the last available trading day.
        Then, it fetches the closing price for that day using the 'yfinance' library. This is particularly useful for
        international users who need to reconcile local dates with NYSE trading days for accurate financial analyses or
    portfolio management.

    The function first converts the target_date from the user's local timezone to the NYSE timezone and then
    calculates the last available trading day. If the target_date falls on a non-trading day (e.g., weekend or
    holiday), the function finds the most recent previous trading day. It then fetches the closing price for the
    stock on that day. This approach ensures that users always get the relevant closing price data for their
    financial calculations, regardless of their timezone or the specific trading calendar of the NYSE.

    Example Usage:
        # Fetch the closing price for Apple Inc. (AAPL) on or before October 15, 2023, from Bangkok, Thailand.
        closing_price = get_last_available_trading_day_closing_price('AAPL', datetime(2023, 10, 15), 'Asia/Bangkok')
        if closing_price is not None:
            print(f"Last available trading day's closing price for AAPL: ${closing_price}")
        else:
            print("Closing price data is not available for the specified date.")
    """

    # Create a NYSE calendar
    nyse = mcal.get_calendar('NYSE')

    # Convert target_date to NYSE timezone
    user_tz = pytz.timezone(user_timezone)
    print(stock_name, target_date, user_timezone)
    nyse_tz = pytz.timezone('America/New_York')
    target_date = user_tz.localize(target_date).astimezone(nyse_tz)

    # Adjust the date for trading day search
    adjusted_date = target_date
    trading_days = nyse.valid_days(start_date='1900-01-01', end_date=adjusted_date.strftime('%Y-%m-%d'))
    if len(trading_days) == 0:
        print("No Trading day found")
        return None  # No trading days found up to this date

    last_trading_day = trading_days[-1].date()
    print(last_trading_day)
    # Convert last trading day back to user's timezone for the yfinance request
    last_trading_day_nyse_tz = nyse_tz.localize(datetime.combine(last_trading_day, datetime.min.time()))
    last_trading_day_user_tz = last_trading_day_nyse_tz.astimezone(user_tz).date()

    # Fetch stock data
    try:
        stock_data = yf.download(stock_name, start=last_trading_day_user_tz.strftime('%Y-%m-%d'),
                                 end=(last_trading_day_user_tz + timedelta(days=1)).strftime('%Y-%m-%d'), auto_adjust=False)
        if not stock_data.empty:
            return round(stock_data['Close'][stock_name].iloc[-1],2)
    except Exception as e:
        print(f"An error occurred while fetching the stock price: {e}")
        return None

def get_bulk_available_trading_day_closing_price(
    ticker: list[str], 
    start_date: datetime, 
    end_date: datetime,
    user_timezone: str = 'Asia/Bangkok', 
    fill: Literal['ffill', 'bfill', 'zero', 'nan'] | None = None
) -> pd.DataFrame | None:
    """
    Fetch closing prices for multiple stock tickers within a given date range,
    adjusting for the user's timezone.

    Args:
        ticker (list[str]): List of stock ticker symbols (e.g., ['AAPL', 'MSFT']).
        start_date (datetime): Start of the date range (in user's local timezone).
        end_date (datetime): End of the date range (in user's local timezone).
        user_timezone (str, optional): User's timezone (default: 'Asia/Bangkok').
        fill: Fill strategy for non-trading days:
            • None: Return only trading days (default)
            • 'ffill': Forward-fill last known price
            • 'bfill': Back-fill next known price  
            • 'zero': Fill missing days with 0
            • 'nan': Insert missing days as NaN

    Returns:
        pd.DataFrame | None: DataFrame with dates as index and tickers as columns,
                            containing closing prices. Returns None if no data available.

    Notes:
        - Converts dates from user's timezone to NYSE timezone for trading day calculations.
        - Fetches closing prices for all valid trading days in the range using yfinance.
        - If fill is specified, adds non-trading days and applies the chosen fill strategy.
        - For 'ffill', automatically fetches data from the last trading day before start_date
          to ensure no NaN values at the beginning.
        - Returns None if no trading days are found or data is unavailable.

    Example:
        # Get raw trading day data only
        data = get_bulk_available_trading_day_closing_price(
            ['AAPL', 'MSFT'], 
            datetime(2025, 6, 16), 
            datetime(2025, 6, 23)
        )
        
        # Get data with weekends forward-filled
        data_filled = get_bulk_available_trading_day_closing_price(
            ['AAPL', 'MSFT'], 
            datetime(2025, 6, 16), 
            datetime(2025, 6, 23),
            fill='ffill'
        )
    """
    nyse = mcal.get_calendar('NYSE')
    user_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone('America/New_York')

    # Convert end_date to NYSE timezone
    end_date_nyse = user_tz.localize(end_date).astimezone(nyse_tz)

    # Find all valid trading days up to the adjusted end date
    trading_days = nyse.valid_days(
        start_date='2000-01-01',
        end_date=end_date_nyse.strftime('%Y-%m-%d'),
        tz=nyse_tz
    )
    if len(trading_days) == 0:
        return None

    try:
        # Determine fetch start based on fill strategy
        if fill == 'ffill':
            # Find last trading day before start_date using NYSE calendar
            # Look back up to 30 days to handle long weekends/holidays
            lookback_start = (start_date.date() - timedelta(days=30)).strftime('%Y-%m-%d')
            lookback_end = (start_date.date() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            trading_days_before = nyse.valid_days(
                start_date=lookback_start,
                end_date=lookback_end,
                tz=nyse_tz
            )
            
            if len(trading_days_before) > 0:
                # Fetch from the last trading day before start_date
                last_trading_day = trading_days_before[-1].date()
                yf_start = last_trading_day.strftime('%Y-%m-%d')
            else:
                # Fallback: no trading days found in lookback period
                yf_start = start_date.strftime('%Y-%m-%d')
        else:
            yf_start = start_date.strftime('%Y-%m-%d')
        
        # yfinance end date is exclusive, so add one day
        yf_end = (end_date.date() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Download data from yfinance
        data = yf.download(ticker, start=yf_start, end=yf_end, progress=False)
        
        if not data.empty:
            # Extract closing prices (handle both single and multi-ticker cases)
            if len(ticker) == 1:
                close_data = data['Close'].to_frame(ticker[0])
            else:
                close_data = data['Close']
            if fill is not None:
                # Create complete date range INCLUDING any historical data we fetched
                if fill == 'ffill' and yf_start < start_date.strftime('%Y-%m-%d'):
                    # Extend range to include the historical start date
                    full_range = pd.date_range(
                        start=yf_start,  # Start from where we fetched
                        end=end_date.date(), 
                        freq='D'
                    )
                else:
                    full_range = pd.date_range(
                        start=start_date.date(), 
                        end=end_date.date(), 
                        freq='D'
                    )
                
                # Reindex to include all calendar days
                close_data = close_data.reindex(full_range)
                
                # Apply fill strategy
                if fill == 'ffill':
                    close_data = close_data.ffill()
                elif fill == 'bfill':
                    close_data = close_data.bfill()
                elif fill == 'zero':
                    close_data = close_data.fillna(0)
                elif fill == 'nan':
                    pass
                
                # Trim to only the requested date range
                requested_range = pd.date_range(
                    start=start_date.date(),
                    end=end_date.date(),
                    freq='D'
                )
                close_data = close_data.loc[requested_range]
            
            # Ensure index is date type for consistent access
            close_data.index = pd.to_datetime(close_data.index).date
            
            return close_data.round(2)
            
    except Exception as e:
        print(f"Error fetching stock price: {e}")
    
    return None

def check_valid_trading_date(target_date: datetime, user_timezone: str = 'Asia/Bangkok') -> bool:
    """
    Check if a given date is a valid trading date in the NYSE calendar.

    Args:
        target_date (datetime): The date to check for trading validity.
        user_timezone (str, optional): The user's timezone. Defaults to 'Asia/Bangkok'.

    Returns:
        bool: True if the target_date is a valid trading date, False otherwise.
    """
    # Create a NYSE calendar
    nyse_calendar = mcal.get_calendar('NYSE')

    # Convert target_date to NYSE timezone
    local_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone('America/New_York')
    local_target_date = local_tz.localize(target_date).astimezone(nyse_tz)
    trading_days = nyse_calendar.valid_days(start_date=local_target_date.strftime('%Y-%m-%d'),
                                            end_date=local_target_date.strftime('%Y-%m-%d'))

    if len(trading_days) == 0:
        return False  # No trading days found up to this date
    return True
