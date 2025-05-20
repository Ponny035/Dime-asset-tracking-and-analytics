import datetime as dt

from src.pipeline.processTransaction import process_asset_tracking
from src.pipeline.processTransaction import process_investment_transactions


    # fname = f"state_source_{source}.json"
    # fpath = os.path.join("data", fname)
    # if os.path.isfile(fpath):
    #     state = json_read(fpath)
    #     source = state["source"]
    #     skip = state["project_index"]



user_timezone = 'Asia/Bangkok'

# Specify the start and end dates
start_date = dt.date(2025, 5, 15)
end_date = dt.date(2025, 5, 15)

# Call the function with the specified dates
process_investment_transactions(start_date, end_date, user_timezone)

process_asset_tracking(start_date, end_date, user_timezone)
