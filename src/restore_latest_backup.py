from services.backup import restore_latest_backup


def main() -> None:
    restored_from = restore_latest_backup()
    print(f"Database restored from: {restored_from}")


if __name__ == "__main__":
    main()
