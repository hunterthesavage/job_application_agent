import os
from datetime import datetime

import gspread

from config import NEW_ROLES_SHEET, SPREADSHEET_ID


SHEET_NAME = NEW_ROLES_SHEET
OUTPUT_FILE = "daily_digest.txt"
SERVICE_ACCOUNT_FILE = "service_account.json"


def get_today_rows():
    if not SPREADSHEET_ID:
        raise RuntimeError(
            "Legacy Google Sheets digest is not configured. Set SPREADSHEET_ID in config.py or provide it through your local setup."
        )

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Missing {SERVICE_ACCOUNT_FILE}. Legacy Google Sheets features require a local service account file."
        )

    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)

    rows = worksheet.get_all_records()

    today = datetime.now().astimezone().strftime("%Y-%m-%d")

    today_rows = []
    for row in rows:
        date_found = str(row.get("Date Found", "")).split(" ")[0]
        if date_found == today:
            today_rows.append(row)

    return today_rows


def format_digest(rows):
    if not rows:
        return "No new jobs found today.\n"

    lines = []
    lines.append(f"Job Agent Daily Digest ({len(rows)} new roles)\n")

    for r in rows:
        lines.append(
            f"{r.get('Company')} | {r.get('Title')}\n"
            f"Location: {r.get('Location')} | Fit: {r.get('Fit Score')}\n"
            f"{r.get('Job Posting URL')}\n"
        )

    return "\n".join(lines)


def save_to_file(content):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    rows = get_today_rows()
    content = format_digest(rows)

    print("\n===== DAILY DIGEST =====\n")
    print(content)

    save_to_file(content)

    print(f"\nSaved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
