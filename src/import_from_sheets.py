import json

from services.sqlite_importer import import_all_from_sheets


def main() -> None:
    results = import_all_from_sheets()
    print("Import complete.")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
