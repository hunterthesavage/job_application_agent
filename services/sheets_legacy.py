import gspread
import pandas as pd

from config import SPREADSHEET_ID


def load_sheet(tab_name: str) -> pd.DataFrame:
    if not SPREADSHEET_ID:
        raise RuntimeError(
            "Legacy Google Sheets support is not configured. Set SPREADSHEET_ID in config.py or provide it through your local setup."
        )

    gc = gspread.service_account(filename="service_account.json")
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(tab_name)
    rows = ws.get_all_records()
    return pd.DataFrame(rows)
