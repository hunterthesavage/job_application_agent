from services.db import initialize_database


def main() -> None:
    db_path = initialize_database()
    print(f"SQLite database initialized at: {db_path}")


if __name__ == "__main__":
    main()
