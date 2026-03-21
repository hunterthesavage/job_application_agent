import os

import gspread
from google.oauth2.service_account import Credentials

from config import NEW_ROLES_SHEET, REMOVED_SHEET, SPREADSHEET_ID
from src.models import JobRecord


SHEET_ID = SPREADSHEET_ID
WORKSHEET_NAME = NEW_ROLES_SHEET
REMOVED_WORKSHEET_NAME = REMOVED_SHEET
SERVICE_ACCOUNT_FILE = "service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

REMOVED_HEADERS = [
    "Removed Date",
    "Duplicate Key",
    "Company",
    "Title",
    "Location",
    "Job Posting URL",
    "Removal Reason",
    "Source Sheet",
]


def _validate_legacy_sheets_config() -> None:
    if not SHEET_ID:
        raise RuntimeError(
            "Legacy Google Sheets support is not configured. Set SPREADSHEET_ID in config.py or provide it through your local setup."
        )

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Missing {SERVICE_ACCOUNT_FILE}. Legacy Google Sheets features require a local service account file."
        )


def get_client():
    _validate_legacy_sheets_config()

    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )
    return gspread.authorize(credentials)


def get_spreadsheet():
    client = get_client()
    return client.open_by_key(SHEET_ID)


def get_or_create_worksheet(name: str, headers: list[str] | None = None):
    spreadsheet = get_spreadsheet()

    try:
        worksheet = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=max(20, len(headers or [])))
        if headers:
            worksheet.append_row(headers, value_input_option="USER_ENTERED")

    if headers:
        existing_headers = worksheet.row_values(1)
        if existing_headers != headers:
            if not existing_headers:
                worksheet.append_row(headers, value_input_option="USER_ENTERED")
            else:
                worksheet.update("A1", [headers])

    return worksheet


def get_worksheet():
    return get_or_create_worksheet(WORKSHEET_NAME)


def get_removed_worksheet():
    return get_or_create_worksheet(REMOVED_WORKSHEET_NAME, REMOVED_HEADERS)


def append_job_record(job: JobRecord) -> None:
    worksheet = get_worksheet()
    worksheet.append_row(job.to_row(), value_input_option="USER_ENTERED")


def append_removed_job_record(record: dict[str, str]) -> None:
    worksheet = get_removed_worksheet()
    row = [str(record.get(header, "")).strip() for header in REMOVED_HEADERS]
    worksheet.append_row(row, value_input_option="USER_ENTERED")


def _collect_duplicate_keys_from_worksheet(worksheet) -> set[str]:
    records = worksheet.get_all_records()
    keys = set()

    for record in records:
        value = str(record.get("Duplicate Key", "")).strip()
        if value:
            keys.add(value)

    return keys


def get_existing_duplicate_keys() -> set[str]:
    keys = set()

    active_worksheet = get_worksheet()
    keys.update(_collect_duplicate_keys_from_worksheet(active_worksheet))

    removed_worksheet = get_removed_worksheet()
    keys.update(_collect_duplicate_keys_from_worksheet(removed_worksheet))

    return keys
