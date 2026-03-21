import os
from datetime import datetime

import gspread


SPREADSHEET_ID = "1h0LEK4-t6-j7rmdxjWeO8XY_Kx9L5HfQpOdkJtf_p_E"
SHEET_NAME = "New Validated Roles"
OUTPUT_FILE = "daily_digest.txt"


def get_today_rows():
    gc = gspread.service_account(filename="service_account.json")
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