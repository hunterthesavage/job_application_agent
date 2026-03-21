from services.backup import backup_database


def main() -> None:
    backup_path = backup_database()
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
