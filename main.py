from datetime import datetime, timedelta, time
import datetime as dt

from src.pipeline.processTransaction import process_investment_transactions
from src.pipeline.processTransaction import test
from src.module.stockInfo import check_valid_trading_date

#
# Specify the start and end dates
start_date = dt.date(2023, 6, 2)
end_date = dt.date(2023, 7, 1)


# Call the function with the specified dates
# process_investment_transactions(start_date, end_date)
#
test(start_date, end_date, 'Asia/Bangkok')


# print(x)
