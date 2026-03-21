import json
import sqlite3

from config import DATABASE_PATH


def fetch_one(conn: sqlite3.Connection, query: str, params=()):
    cur = conn.execute(query, params)
    row = cur.fetchone()
    return row[0] if row else None


def fetch_all(conn: sqlite3.Connection, query: str, params=()):
    cur = conn.execute(query, params)
    return cur.fetchall()


def main() -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    summary = {
        "database_path": str(DATABASE_PATH),
        "jobs_total": fetch_one(conn, "SELECT COUNT(*) FROM jobs"),
        "jobs_new": fetch_one(
            conn,
            "SELECT COUNT(*) FROM jobs WHERE workflow_status = 'New'"
        ),
        "jobs_applied": fetch_one(
            conn,
            "SELECT COUNT(*) FROM jobs WHERE workflow_status = 'Applied'"
        ),
        "removed_jobs_total": fetch_one(conn, "SELECT COUNT(*) FROM removed_jobs"),
        "settings_total": fetch_one(conn, "SELECT COUNT(*) FROM app_settings"),
        "jobs_with_duplicate_key": fetch_one(
            conn,
            "SELECT COUNT(*) FROM jobs WHERE TRIM(COALESCE(duplicate_key, '')) <> ''"
        ),
        "removed_with_duplicate_key": fetch_one(
            conn,
            "SELECT COUNT(*) FROM removed_jobs WHERE TRIM(COALESCE(duplicate_key, '')) <> ''"
        ),
        "jobs_missing_company_or_title": fetch_one(
            conn,
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE TRIM(COALESCE(company, '')) = ''
               OR TRIM(COALESCE(title, '')) = ''
            """
        ),
    }

    recent_jobs = fetch_all(
        conn,
        """
        SELECT workflow_status, company, title, applied_date, fit_score
        FROM jobs
        ORDER BY
            CASE WHEN workflow_status = 'Applied' THEN 0 ELSE 1 END,
            COALESCE(applied_date, '') DESC,
            company ASC,
            title ASC
        LIMIT 10
        """
    )

    print("SQLite verification summary:")
    print(json.dumps(summary, indent=2))

    print("\nSample jobs:")
    for row in recent_jobs:
        print(
            f"- [{row['workflow_status']}] "
            f"{row['company']} | {row['title']} | "
            f"applied_date={row['applied_date']} | fit_score={row['fit_score']}"
        )

    conn.close()


if __name__ == "__main__":
    main()
