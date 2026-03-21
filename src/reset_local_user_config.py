from services.db import db_connection
from services.openai_key import delete_saved_openai_api_key


def main() -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM app_settings")

    delete_saved_openai_api_key()
    print("Local settings cleared and saved OpenAI API key deleted.")


if __name__ == "__main__":
    main()
