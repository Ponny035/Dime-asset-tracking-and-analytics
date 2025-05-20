import requests
import os
import json
from dotenv import load_dotenv



def get_financial_institutions_holidays_api(client_id):

    url = "https://apigw1.bot.or.th/bot/public/financial-institutions-holidays/?year=2025"

    payload = {}
    headers = {
    'X-IBM-Client-Id': client_id
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    result = response.json()['result']
    
    return result

def update_financial_institutions_holidays(client_id):
    api_result = get_financial_institutions_holidays_api(client_id)

    update_time = api_result['timestamp']
    holiday_date = []

    for day in api_result['data']:
        holiday = day['Date']
        holiday_date.append(holiday)
    
    file_name = "financial_institutions_holidays.json"
    fpath = os.path.join(file_name)

    # Create data structure to save
    data_to_save = {
        "update_time": update_time,
        "holidays": holiday_date
    }

    if os.path.isfile(fpath):
        with open(fpath, 'r') as file:
            existing_data = json.load(file)
            if existing_data.get("update_time") == update_time:
                print("No update needed, data is already current.")
                return

    # Create or overwrite the file
    with open(fpath, 'w') as file:
        json.dump(data_to_save, file, indent=2)
        print(f"Holiday data written to {fpath}")


load_dotenv()
client_id = os.getenv('BOT_API_CLIENT_ID')


update_financial_institutions_holidays(client_id)


