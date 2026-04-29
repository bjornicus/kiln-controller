#!/usr/bin/env python3

import argparse
import csv
import time
import os
import sys
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_google_sheets_service(credentials_file):
    """Create and return Google Sheets API service."""
    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service

def append_to_sheet(service, spreadsheet_id, sheet_name, row_data):
    """Append a row of data to the specified Google Sheet."""
    try:
        # Prepare the data for the API
        values = [row_data]
        body = {
            'values': values
        }

        # Append to the sheet
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:A',  # Append starting from column A
            valueInputOption='RAW',
            body=body
        ).execute()

        print(f"Appended row to Google Sheets '{sheet_name}': {row_data}")
        return result

    except HttpError as err:
        print(f"Error appending to Google Sheets '{sheet_name}': {err}")
        return None

def test_google_sheets(credentials_file, spreadsheet_id, sheet_name):
    """Test Google Sheets connection by appending a test row."""
    print(f"Testing Google Sheets connection...")
    print(f"  Credentials: {credentials_file}")
    print(f"  Spreadsheet ID: {spreadsheet_id}")
    print(f"  Sheet name: {sheet_name}")
    print()

    try:
        # Get service
        print("Connecting to Google Sheets API...")
        service = get_google_sheets_service(credentials_file)
        
        # Verify spreadsheet exists and get metadata
        print("Verifying spreadsheet access...")
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        spreadsheet_title = spreadsheet.get('properties', {}).get('title', 'Unknown')
        print(f"✓ Successfully accessed spreadsheet: {spreadsheet_title}")
        
        # Verify sheet exists
        sheets = spreadsheet.get('sheets', [])
        sheet_exists = any(sheet.get('properties', {}).get('title') == sheet_name for sheet in sheets)
        if not sheet_exists:
            sheet_names = [sheet.get('properties', {}).get('title') for sheet in sheets]
            print(f"✗ Sheet '{sheet_name}' not found. Available sheets: {sheet_names}")
            return False
        print(f"✓ Sheet '{sheet_name}' exists")
        
        # Append test row
        print(f"\nAppending test row to sheet '{sheet_name}'...")
        test_row = [
            f"TEST_{datetime.now().isoformat()}",
            "test_timestamp",
            "test_temperature",
            "test_target",
            "test_state",
            "test_heat",
            "test_totaltime",
            "test_profile"
        ]
        result = append_to_sheet(service, spreadsheet_id, sheet_name, test_row)
        
        if result:
            updated_range = result.get('updates', {}).get('updatedRange', 'Unknown')
            print(f"✓ Successfully appended test row")
            print(f"  Updated range: {updated_range}")
            print()
            print("✓ Google Sheets integration is working correctly!")
            return True
        else:
            print("✗ Failed to append test row")
            return False
            
    except HttpError as err:
        print(f"✗ Google API Error: {err}")
        if err.resp.status == 403:
            print("  Permission denied. Make sure you've shared the spreadsheet with the service account.")
        elif err.resp.status == 404:
            print("  Spreadsheet not found. Check your spreadsheet ID.")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def tail_csv_and_sync(csv_file, credentials_file, spreadsheet_id, sheet_name, poll_interval=1):
    """Tail the CSV file and sync new rows to Google Sheets."""
    service = get_google_sheets_service(credentials_file)

    # Get the initial file size
    last_size = os.path.getsize(csv_file) if os.path.exists(csv_file) else 0
    last_position = 0

    print(f"Starting to monitor {csv_file} for changes...")
    print(f"Will append new data to Google Sheets sheet: '{sheet_name}'")

    while True:
        try:
            if not os.path.exists(csv_file):
                print(f"CSV file {csv_file} does not exist yet. Waiting...")
                time.sleep(poll_interval)
                continue

            current_size = os.path.getsize(csv_file)

            if current_size > last_size:
                # File has grown, read new content
                with open(csv_file, 'r') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    last_position = f.tell()

                if new_content:
                    # Parse the new CSV lines
                    lines = new_content.strip().split('\n')
                    for line in lines:
                        if line.strip():  # Skip empty lines
                            # Parse CSV line
                            reader = csv.reader([line])
                            row = next(reader)
                            if row:  # Only append non-empty rows
                                append_to_sheet(service, spreadsheet_id, sheet_name, row)

                last_size = current_size

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("Stopping CSV monitoring...")
            break
        except Exception as e:
            print(f"Error monitoring CSV: {e}")
            time.sleep(poll_interval)

def main():
    parser = argparse.ArgumentParser(description='Sync kiln CSV log to Google Sheets in real-time.')
    parser.add_argument('--csvfile', type=str, default='/tmp/kilnstats.csv',
                        help='Path to the CSV file to monitor (default: /tmp/kilnstats.csv)')
    parser.add_argument('--credentials', type=str, required=True,
                        help='Path to Google service account credentials JSON file')
    parser.add_argument('--spreadsheet-id', type=str, required=True,
                        help='Google Sheets spreadsheet ID')
    parser.add_argument('--sheet-name', type=str, default='Sheet1',
                        help='Name of the sheet to append data to (default: Sheet1)')
    parser.add_argument('--poll-interval', type=float, default=1.0,
                        help='How often to check for new CSV data in seconds (default: 1.0)')
    parser.add_argument('--test-google-sheets', action='store_true',
                        help='Test Google Sheets connection by appending a test row and exit')

    args = parser.parse_args()

    if args.test_google_sheets:
        success = test_google_sheets(args.credentials, args.spreadsheet_id, args.sheet_name)
        sys.exit(0 if success else 1)
    else:
        tail_csv_and_sync(
            args.csvfile,
            args.credentials,
            args.spreadsheet_id,
            args.sheet_name,
            args.poll_interval
        )

if __name__ == '__main__':
    main()
