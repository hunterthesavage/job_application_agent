import gspread
import pandas as pd

from config import SPREADSHEET_ID


def load_sheet(tab_name: str) -> pd.DataFrame:
    gc = gspread.service_account(filename="service_account.json")
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(tab_name)
    rows = ws.get_all_records()
    return pd.DataFrame(rows)
