import json

from config import APPLIED_SHEET, NEW_ROLES_SHEET
from services.sheets_legacy import load_sheet


def clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def main() -> None:
    new_df = load_sheet(NEW_ROLES_SHEET)
    applied_df = load_sheet(APPLIED_SHEET)

    new_map = {}
    applied_map = {}

    for _, row in new_df.iterrows():
        key = clean(row["Duplicate Key"]) if "Duplicate Key" in row.index else ""
        if key:
            new_map[key] = {
                "sheet": NEW_ROLES_SHEET,
                "company": clean(row["Company"]) if "Company" in row.index else "",
                "title": clean(row["Title"]) if "Title" in row.index else "",
            }

    for _, row in applied_df.iterrows():
        key = clean(row["Duplicate Key"]) if "Duplicate Key" in row.index else ""
        if key:
            applied_map[key] = {
                "sheet": APPLIED_SHEET,
                "company": clean(row["Company"]) if "Company" in row.index else "",
                "title": clean(row["Title"]) if "Title" in row.index else "",
            }

    overlap_keys = sorted(set(new_map.keys()) & set(applied_map.keys()))

    report = {
        "new_roles_keys": len(new_map),
        "applied_keys": len(applied_map),
        "overlap_count": len(overlap_keys),
        "overlaps": [],
    }

    for key in overlap_keys:
        report["overlaps"].append(
            {
                "duplicate_key": key,
                "new_roles": new_map[key],
                "applied": applied_map[key],
            }
        )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
