import datetime

from src.pipeline.processTransaction import process_investment_transactions


# # Specify the start and end dates
start_date = datetime.date(2024, 2, 1)
end_date = datetime.date(2024, 2, 28)

# Call the function with the specified dates
process_investment_transactions(start_date, end_date)
