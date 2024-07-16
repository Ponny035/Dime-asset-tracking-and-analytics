from datetime import datetime, timedelta, time
import datetime as dt

from src.pipeline.processTransaction import process_investment_transactions
from src.pipeline.processTransaction import process_asset_tracking
from src.module.stockInfo import check_valid_trading_date

user_timezone = 'Asia/Bangkok'

# Specify the start and end dates
start_date = dt.date(2024, 7, 12)
end_date = dt.date(2024, 7, 16)

# Call the function with the specified dates
process_investment_transactions(start_date, end_date, user_timezone)

# Specify the start and end dates
start_date = dt.date(2024, 7, 16)
end_date = dt.date(2024, 7, 16)
#
process_asset_tracking(start_date, end_date, user_timezone)
