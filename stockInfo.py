from finvizfinance.quote import finvizfinance
from datetime import datetime
from typing import Literal


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
        "Dividend": str(stock_fundament["Dividend"])
    }
    return stock_basic_info


def format_transaction(price: float, commission: float, tax: float, amount: float, share: float,
                       stock_name: str = "AAPL", date: datetime = datetime.today(), portfolio: str = "Dime",
                       transaction_type: Literal['BUY', 'SEL', 'DIV'] = 'BUY',
                       status: str = "Done") -> list:
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

    Returns:
        list: A list representing the formatted transaction with detailed information.
    """
    stock_info = get_stock_basic_info(stock_name)
    has_dividend = stock_info['Dividend'] != '-'
    if transaction_type != "SEL":
        total_amount = round(amount + (commission + tax), 2)
    else:
        total_amount = round(amount - (commission + tax), 2) * -1
    transaction = [
        date, portfolio, transaction_type, stock_name, stock_info['Sector'], stock_info['Industry'], has_dividend,
        price, commission, tax, amount, total_amount, share, status
    ]
    return transaction
