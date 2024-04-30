from datetime import datetime, timedelta, time
import datetime as dt

from src.pipeline.processTransaction import process_investment_transactions
from src.pipeline.processTransaction import process_asset_tracking
from src.module.stockInfo import check_valid_trading_date


# # Specify the start and end dates
# start_date = dt.date(2024, 4, 23)
# end_date = dt.date(2024, 4, 26)
#
#
# # Call the function with the specified dates
# process_investment_transactions(start_date, end_date, 'Asia/Bangkok')


# Specify the start and end dates
start_date = dt.date(2024, 4, 30)
end_date = dt.date(2024, 4, 30)
#
process_asset_tracking(start_date, end_date, 'Asia/Bangkok')
