Google Sheets Live Sync
========================

The `kiln-google-sync.py` script monitors the CSV log file produced by `kiln-logger.py` and automatically appends new rows to a Google Spreadsheet in real-time. This allows you to monitor kiln firing progress live from anywhere with internet access.

## Setup

### 1. Google Cloud Project Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it

### 2. Service Account Creation

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service account"
3. Give it a name like "kiln-controller-sync"
4. **Skip the role assignment for now** (you'll grant permissions when sharing the spreadsheet)
5. Create a key (JSON format) and download it
6. Note the service account email address (it will look like `name@project.iam.gserviceaccount.com`)

### 3. Google Spreadsheet Setup

1. Create a new Google Spreadsheet
2. Copy the spreadsheet ID from the URL (the long string between `/d/` and `/edit`)
3. Share the spreadsheet with the service account email noted above (can be found in the JSON key file as well)
4. Optionally rename the first sheet to something descriptive like "KilnData"

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

Run the sync script alongside your kiln logger:

```bash
# Terminal 1: Run your kiln logger
python kiln-logger.py --csvfile /tmp/kilnstats.csv

# Terminal 2: Run the Google Sheets sync
python kiln-google-sync.py \
    --credentials /path/to/service-account-key.json \
    --spreadsheet-id YOUR_SPREADSHEET_ID \
    --sheet-name sheet1 \
    --csvfile /tmp/kilnstats.csv
```

If you don't want every data point uploaded to google sheets, but instead want a regular sampling, you can use the `--upload-every-nth` option.  For example, if your kiln logger is writing every 2 seconds and you want to upload only one row per minute, use:

```bash
python kiln-google-sync.py \
    --credentials /path/to/service-account-key.json \
    --spreadsheet-id YOUR_SPREADSHEET_ID \
    --sheet-name sheet1 \
    --csvfile /tmp/kilnstats.csv \
    --upload-every-nth 30
```

When you start the sync script, if there's existing data in the CSV file, you'll be prompted:
```
Do you want to upload existing data to Google Sheets before monitoring new changes? (y/n) [default: n]:
```

- Answer `y` to upload all existing data to the spreadsheet (useful for backfilling after a restart)
- Answer `n` or just press Enter to skip and only monitor new changes

## Testing

Before running the sync with real kiln data, test your Google Sheets connection:

```bash
python kiln-google-sync.py \
    --credentials /path/to/service-account-key.json \
    --spreadsheet-id YOUR_SPREADSHEET_ID \
    --sheet-name test-sheet1 \
    --test-google-sheets
```

This will:
1. Connect to your Google Sheets API using the credentials
2. Verify the spreadsheet and sheet exist
3. Append a test row to verify write permissions
4. Report success or any errors

### Command Line Options

- `--csvfile`: Path to the CSV file to monitor (default: `/tmp/kilnstats.csv`)
- `--credentials`: Path to your Google service account JSON key file (required)
- `--spreadsheet-id`: Your Google Sheets spreadsheet ID (required)
- `--sheet-name`: Name of the sheet to append data to (IMPORTANT: check your Google Sheet tabs!)
- `--poll-interval`: How often to check for new data in seconds (default: 1.0)
- `--upload-every-nth`: Only upload every nth CSV data row (default: 1 = upload all rows)
- `--test-google-sheets`: Test the Google Sheets connection by appending a test row and exit (doesn't require --csvfile)

## CSV Data Format

The script appends rows with the following columns (depending on kiln-logger.py options):

**Standard columns:**
- `stamp`: Unix timestamp
- `runtime`: Runtime in seconds
- `temperature`: Actual temperature
- `target`: Target temperature
- `state`: Current state
- `heat`: Heat setting
- `totaltime`: Total scheduled time
- `profile`: Profile name

**PID columns (if --pidstats enabled):**
- `pid_time`, `pid_timeDelta`, `pid_setpoint`, `pid_ispoint`, `pid_err`, `pid_errDelta`
- `pid_p`, `pid_i`, `pid_d`, `pid_kp`, `pid_ki`, `pid_kd`, `pid_pid`, `pid_out`

## Troubleshooting

- **Permission denied**: Make sure you've shared the spreadsheet with the service account email and granted "Editor" access (not just "Viewer")
- **API errors**: Verify the Google Sheets API is enabled in your Google Cloud project
- **CSV file not found**: Ensure the CSV file path matches what kiln-logger.py is writing to
- **No data appearing**: Check that the sheet name matches exactly (case-sensitive)

## Security Notes

- Keep your service account JSON key file secure and don't commit it to version control
- The service account only needs access to the specific spreadsheet
- Consider using environment variables or a config file for credentials in production