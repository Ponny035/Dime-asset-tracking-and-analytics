import os
import json
import logging
import datetime as dt
from dotenv import load_dotenv

from src.pipeline.processTransaction import process_asset_tracking
from src.pipeline.processTransaction import process_investment_transactions
from src.module.checkThaiHoliday import update_financial_institutions_holidays


    # fname = f"state_source_{source}.json"
    # fpath = os.path.join("data", fname)
    # if os.path.isfile(fpath):
    #     state = json_read(fpath)
    #     source = state["source"]
    #     skip = state["project_index"]


# load_dotenv()
# client_id = os.getenv('BOT_API_CLIENT_ID')


# update_financial_institutions_holidays(client_id)

file_name = "last_update_information"

start_date = dt.now().strftime('%Y-%m-%d')
end_date = start_date

if os.path.isfile(file_name):
    try:
        with open (file_name, 'r') as file:
            existing_data = json.load(file)
            if existing_data.get("update_time", "").startswith(start_date):
                logging.info("No update needed. Already updated today.")
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Problem reading existing file: {e}. Proceeding with update.")
            

else:
    # get user_input

    user_timezone = 'Asia/Bangkok'

    # Specify the start and end dates
    start_date = dt.date(2025, 5, 24)
    end_date = dt.date(2025, 5, 26)

# Call the function with the specified dates
process_investment_transactions(start_date, end_date, user_timezone)

process_asset_tracking(start_date, end_date, user_timezone)
