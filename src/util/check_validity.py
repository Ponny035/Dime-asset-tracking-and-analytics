import json
import logging

from src.exceptions import StartDateError

def check_working_day(date):
    """
        Check if a given date is working day and isn't banking financial institutions holidays.
        
        Args:
            date (date): The date to check for working day validity.
    
        Returns:
            bool: True if the target_date is a valid working day, False otherwise.
    """
    # Check if it's weekend (5 = Saturday, 6 = Sunday)
    if date.weekday() >= 5:
        return False

    # Read holidays from JSON file
    try:
        with open("financial_institutions_holidays.json", "r") as file:
            holidays_data = json.load(file)
            holidays = holidays_data.get("holidays", [])

            # Check if the date is in holidays list
            date_str = date.strftime("%Y-%m-%d")
            return date_str not in holidays
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error reading holidays file: {e}")
        return False  # If we can't read the file, assume it isn't a working day

def check_valid_date_range (start_date, end_date):
    if start_date > end_date:
        logging.error(
            f"The start date ({start_date}) must be on or before the end date ({end_date}). Please check the dates and try again."
        )
        raise StartDateError()
    return False