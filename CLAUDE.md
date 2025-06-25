# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dime Asset Tracking and Analytics is a Python-based application that automates investment tracking for US stocks purchased through the Dime application. The system processes email confirmations, extracts transaction data from PDF attachments, and maintains asset tracking via Google Sheets integration.

## Core Architecture

### Main Pipeline
- `main.py` - Entry point with holiday/working day checks and date range processing
- `src/pipeline/processTransaction.py` - Orchestrates investment transaction and asset tracking workflows

### Key Modules
- `src/module/queryEmailRecord.py` - Email querying and PDF attachment extraction
- `src/module/PDFProcessing.py` - PDF parsing for transaction details
- `src/module/stockInfo.py` - Stock price data retrieval and formatting via yfinance and finviz
- `src/module/assetTracking.py` - Asset valuation calculations and portfolio tracking
- `src/module/exportDataToGoogleSheet.py` - Google Sheets API integration
- `src/module/checkThaiHoliday.py` - Thai financial institution holiday calendar updates

### Data Flow
1. Email scanning for Dime confirmation notes
2. PDF extraction and transaction parsing
3. Stock price enrichment from financial APIs
4. Google Sheets export for investment logs and asset tracking
5. Portfolio valuation updates with historical price data

## Development Commands

### Setup and Installation
```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (includes production + dev tools)
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
```

### Running the Application
```bash
# Standard execution (respects holidays/weekends)
python main.py

# Manual mode (bypasses working day checks)
python main.py -m
python main.py --manual
```

### Testing
```bash
# Run all tests
python -m unittest discover tests/

# Run specific test file
python -m unittest tests.test_holiday
```

## Environment Configuration

The application requires several environment variables configured in `.env`:

- `EMAIL` - Gmail address for accessing investment confirmations
- `APP_PASSWORD` - Gmail app password for authentication
- `PDF_PASSWORD` - Password for encrypted PDF confirmations (typically birthdate format)
- `SPREADSHEET_ID` - Google Sheets ID for data export
- `INVEST_LOG_RANGE_NAME` - Sheet range for transaction logs (default: "US Invest Log!A:O")
- `ASSET_TRACKING_RANGE_NAME` - Sheet range for asset tracking (default: "Asset tracking!A:M")
- `BOT_API_CLIENT_ID` - API client ID for Thai holiday calendar service
- `AUTH_MODE` - Authentication mode: 'oauth' (uses token.json) or 'service_account' (uses credentials.json)

## Key Dependencies

- `yfinance` - Stock price data retrieval
- `finvizfinance` - Additional stock market information
- `google-api-python-client` - Google Sheets integration
- `pypdf` - PDF processing capabilities
- `pandas` - Data manipulation and analysis
- `pandas_market_calendars` - Trading calendar management
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests for holiday data
- `pytz` - Timezone handling

## Authentication Modes

The application supports two authentication modes for Google Sheets access:

- **OAuth Mode (default)**: Uses `token.json` for interactive authentication. Suitable for development and personal use.
- **Service Account Mode**: Uses `credentials.json` for automated authentication. Suitable for server deployments and CI/CD.

Set `AUTH_MODE=service_account` in `.env` to use service account authentication.

## Time Zone Handling

The application handles timezone conversions between user timezone (configurable, defaults to 'Asia/Bangkok') and Bangkok time for proper date processing. Holiday checks use Thai financial institution calendars.

## Incremental Processing

The application includes timeout protection by saving progress after processing each date. If the application times out during long processing runs, it can resume from the last successfully processed date rather than starting over.

## File Structure Notes

- `credentials.json` - Google API service account credentials
- `token.json` - OAuth token for Google Sheets access
- `financial_institutions_holidays.json` - Cached holiday data
- `last_update_information.json` - Tracks last successful processing date
- `data/` - Directory for PDF storage and processing