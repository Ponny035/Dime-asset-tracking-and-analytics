from datetime import datetime, timedelta, time

import numpy as np
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.module.exportDataToGoogleSheet import export_invest_log_to_google_sheet
from src.module.stockInfo import (
    get_last_available_trading_day_closing_price,
    check_valid_trading_date,
)
from src.module.updateTracker import update_last_update_date
from src.util.auth import authenticate


def query_investment_log(
    spreadsheet_id: str,
    range_name: str,
    start_date: datetime.date,
    end_date: datetime.date,
    auth_mode: str = "oauth",
):
    """
    Query investment log data from a Google Sheet within a specified date range.

    Args:
        spreadsheet_id (str): The ID of the Google Sheet.
        range_name (str): The range of cells to retrieve data from in A1 notation (e.g., 'Sheet1!A1:B2').
        start_date (datetime.date): The start date of the date range to query.
        end_date (datetime.date): The end date of the date range to query.
        auth_mode (str): Authentication mode - "oauth" or "service_account".

    Returns:
        pandas.DataFrame or None: DataFrame containing the investment log data within the specified date range,
        or None if no data is found.
    """
    try:
        credentials = authenticate(auth_mode)
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        sheet = service.spreadsheets()
        result = (
            sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        )
        values = result.get("values", [])
        if not values:
            print("No data found.")
            return None
        investment_log = pd.DataFrame(
            values[1:], columns=values[0]
        )  # the first row contains headers
        investment_log[investment_log.columns[0]] = pd.to_datetime(
            investment_log[investment_log.columns[0]]
        )
        start_datetime, end_datetime = pd.to_datetime(start_date), pd.to_datetime(
            end_date
        )
        mask = (investment_log[investment_log.columns[0]] >= start_datetime) & (
            investment_log[investment_log.columns[0]] <= end_datetime
        )
        return investment_log.loc[mask]
    except HttpError as err:
        print(err)


def process_asset_log(
    investment_log,
    spreadsheet_id: str,
    asset_log_range_name: str,
    start_date: datetime.date,
    end_date: datetime.date,
    auth_mode: str = "oauth",
    update_tracker_params: dict = None,
):
    """
    Process asset log data by updating asset tracking information and importing it into a Google Sheet.

    Args:
        investment_log (pandas.DataFrame): DataFrame containing investment log data.
        spreadsheet_id (str): The ID of the Google Sheet.
        asset_log_range_name (str): The range of cells to update in the Google Sheet for asset tracking.
        start_date (datetime.date): The start date of the date range being processed.
        end_date (datetime.date): The end date of the date range being processed.
        auth_mode (str): Authentication mode - "oauth" or "service_account".
        update_tracker_params (dict): Parameters for updating progress tracker. Should contain:
            - 'update_range': Range for last update tracking
            - 'local_file': Local file path for tracking
            If None, progress tracking is skipped.

    Returns:
        None
    """

    temp_time = time(8, 30, 00)
    drop_columns = [
        "Type",
        "Have Dividend",
        "Stock Price (USD)",
        "Commission (USD)",
        "Tax (USD)",
        "Status",
        "Note",
    ]
    investment_log = investment_log.drop(columns=drop_columns, axis=1).astype(
        {
            "Share": np.float64,
            "Amount (USD)": np.float64,
            "Total Amount (USD)": np.float64,
        }
    )

    if start_date > end_date:
        print("Start date must not be after end date.")
        return None

    date_range = pd.date_range(start=start_date, end=end_date)
    asset_log = None
    final_df = None
    for process_date in date_range:
        print("Processing date:", process_date)
        nyse_temp_datetime = datetime.combine(process_date, temp_time)
        filtered_investment_log = investment_log[
            investment_log["Date"] == pd.to_datetime(process_date)
        ]
        if filtered_investment_log.empty:
            print("There isn't any trading data for this date yet.")

        if asset_log is None:
            print("Query asset log")
            asset_log = query_investment_log(
                spreadsheet_id,
                asset_log_range_name,
                process_date - timedelta(days=1),
                process_date - timedelta(days=1),
            )
        elif final_df is not None:
            print("Updating asset log")
            asset_log = final_df
        is_market_open = check_valid_trading_date(
            nyse_temp_datetime, "America/New_York"
        )
        if filtered_investment_log.empty:
            final_df = asset_log
        else:
            # handle multiple transactions on one trigger in one day
            grouped_data = filtered_investment_log.groupby(
                ["Product Name"], as_index=False
            ).agg(
                {
                    "Date": "first",
                    "Port": "first",
                    "Sector": "first",
                    "Industry": "first",
                    "Amount (USD)": "sum",
                    "Total Amount (USD)": "sum",
                    "Share": "sum",
                }
            )

            # Round the numeric columns to 7 decimal places
            numeric_columns = grouped_data.select_dtypes(include=["number"]).columns
            grouped_data[numeric_columns] = grouped_data[numeric_columns].round(7)

            filtered_investment_log = grouped_data
            final_df = filtered_investment_log

        if is_market_open:
            asset_log = asset_log.drop(
                columns=[
                    "Closing Stock Price",
                    "Valuation",
                    "Is Market Open",
                    "Performance",
                    "Total Performance",
                ],
                axis=1,
            ).astype(
                {
                    "Share": np.float64,
                    "Amount (USD)": np.float64,
                    "Total Amount (USD)": np.float64,
                }
            )
            if not asset_log.empty:
                merged_df = pd.merge(
                    asset_log,
                    filtered_investment_log,
                    on=["Product Name", "Port", "Sector", "Industry"],
                    how="outer",
                    suffixes=("_asset", "_filtered"),
                )
                merged_df[
                    ["Share_asset", "Amount (USD)_asset", "Total Amount (USD)_asset"]
                ] = merged_df[
                    ["Share_asset", "Amount (USD)_asset", "Total Amount (USD)_asset"]
                ].fillna(
                    0
                )
                merged_df[
                    [
                        "Share_filtered",
                        "Amount (USD)_filtered",
                        "Total Amount (USD)_filtered",
                    ]
                ] = merged_df[
                    [
                        "Share_filtered",
                        "Amount (USD)_filtered",
                        "Total Amount (USD)_filtered",
                    ]
                ].fillna(
                    0
                )
                merged_df["Share"] = (
                    merged_df["Share_asset"] + merged_df["Share_filtered"]
                ).round(7)
                merged_df["Amount (USD)"] = (
                    merged_df["Amount (USD)_asset"] + merged_df["Amount (USD)_filtered"]
                ).round(2)
                merged_df["Total Amount (USD)"] = (
                    merged_df["Total Amount (USD)_asset"]
                    + merged_df["Total Amount (USD)_filtered"]
                ).round(2)
                merged_df["Date"] = merged_df["Date_asset"]
                print(merged_df)
                final_df = merged_df[
                    [
                        "Date",
                        "Port",
                        "Product Name",
                        "Sector",
                        "Industry",
                        "Share",
                        "Amount (USD)",
                        "Total Amount (USD)",
                    ]
                ].drop_duplicates(subset=["Port", "Product Name", "Sector", "Industry"])

            stock_triggers = final_df["Product Name"].values
            closing_prices = []
            performances = []
            total_performances = []
            valuations = []
            for trigger in stock_triggers:
                print("Fetching closing price of", trigger)
                closing_price = get_last_available_trading_day_closing_price(
                    stock_name=trigger,
                    target_date=nyse_temp_datetime,
                    user_timezone="America/New_York",
                )
                closing_prices.append(closing_price)
                temp_asset_log = final_df.loc[final_df["Product Name"] == trigger].iloc[
                    0
                ]
                share, amount_usd, total_amount_usd = (
                    temp_asset_log["Share"],
                    temp_asset_log["Amount (USD)"],
                    temp_asset_log["Total Amount (USD)"],
                )
                if share != 0:
                    valuation = closing_price * share
                    valuations.append(valuation)
                    performances.append((valuation - amount_usd) / amount_usd)
                    total_performances.append(
                        (valuation - total_amount_usd) / total_amount_usd
                    )
                else:
                    valuations.append(0)
                    performances.append(0)
                    total_performances.append(0)
            final_df.insert(1, "Is Market Open", is_market_open, True)
            final_df.insert(9, "Closing Stock Price", closing_prices, True)
            final_df.insert(10, "Valuation", valuations, True)
            final_df.insert(11, "Performance", performances, True)
            final_df.insert(12, "Total Performance", total_performances, True)

        else:
            final_df = asset_log
            final_df["Is Market Open"] = False
        final_df["Date"] = process_date.strftime("%Y-%m-%d")
        print(final_df)
        export_invest_log_to_google_sheet(
            spreadsheet_id,
            asset_log_range_name,
            "USER_ENTERED",
            final_df.values.tolist(),
            auth_mode,
        )
        
        # Update progress tracker after processing each date
        if update_tracker_params:
            update_success = update_last_update_date(
                spreadsheet_id,
                update_tracker_params['update_range'],
                update_tracker_params['local_file'],
                process_date.date(),
                auth_mode
            )
            if update_success:
                print(f"Successfully updated tracking progress for {process_date.date()}")
            else:
                print(f"Warning: Failed to update tracking progress for {process_date.date()}")
