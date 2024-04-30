from typing import Literal
from datetime import datetime, timedelta
from finvizfinance.quote import finvizfinance
import yfinance as yf
import pandas_market_calendars as mcal
import pytz


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
    Retrieves the closing price of a stock on the last available trading day prior to or on the given date,
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
    nyse_tz = pytz.timezone('America/New_York')
    target_date = user_tz.localize(target_date).astimezone(nyse_tz)

    # Adjust the date for trading day search
    adjusted_date = target_date
    trading_days = nyse.valid_days(start_date='1900-01-01', end_date=adjusted_date.strftime('%Y-%m-%d'))
    if len(trading_days) == 0:
        return None  # No trading days found up to this date

    last_trading_day = trading_days[-1].date()

    # Convert last trading day back to user's timezone for the yfinance request
    last_trading_day_nyse_tz = nyse_tz.localize(datetime.combine(last_trading_day, datetime.min.time()))
    last_trading_day_user_tz = last_trading_day_nyse_tz.astimezone(user_tz).date()

    # Fetch stock data
    try:
        stock_data = yf.download(stock_name, start=last_trading_day_user_tz.strftime('%Y-%m-%d'),
                                 end=(last_trading_day_user_tz + timedelta(days=1)).strftime('%Y-%m-%d'))
        if not stock_data.empty:
            return round(stock_data['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"An error occurred while fetching the stock price: {e}")
        return None


def check_valid_trading_date(target_date: datetime, user_timezone: str = 'Asia/Bangkok') -> bool:
    # Create a NYSE calendar
    nyse = mcal.get_calendar('NYSE')

    # Convert target_date to NYSE timezone
    user_tz = pytz.timezone(user_timezone)
    nyse_tz = pytz.timezone('America/New_York')
    target_date = user_tz.localize(target_date).astimezone(nyse_tz)
    trading_days = nyse.valid_days(start_date=target_date.strftime('%Y-%m-%d'),
                                   end_date=target_date.strftime('%Y-%m-%d'))

    if len(trading_days) == 0:
        return False  # No trading days found up to this date
    return True
