import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


def ensure_columns(cur):
    existing = {row[1] for row in cur.execute("PRAGMA table_info(source_registry)")}
    wanted = {
        "priority_score": "REAL NOT NULL DEFAULT 0",
        "last_run_seen_count": "INTEGER NOT NULL DEFAULT 0",
        "last_run_matching_count": "INTEGER NOT NULL DEFAULT 0",
        "notes": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in wanted.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE source_registry ADD COLUMN {col} {ddl}")


def load_latest_run(cur):
    row = cur.execute(
        "SELECT id, details_json FROM ingestion_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None, {}
    run_id, details_json = row
    try:
        details = json.loads(details_json or "{}")
    except Exception:
        details = {}
    return run_id, details


def compute_priority(row):
    (
        source_key,
        source_type,
        source_trust,
        status,
        seen_count,
        matching_job_count,
        first_seen_at,
        last_seen_at,
        last_success_at,
    ) = row

    score = 0.0

    # Base trust
    if source_trust == "ATS Confirmed":
        score += 50
    elif source_trust == "Career Site Confirmed":
        score += 35
    elif source_trust == "Web Discovered":
        score += 20

    # Source type
    if source_type == "ATS":
        score += 20
    elif source_type == "Company Career Site":
        score += 10

    # Historical utility
    score += min(seen_count, 50) * 0.5
    score += min(matching_job_count, 50) * 1.5

    # Conversion quality
    if seen_count > 0:
        ratio = matching_job_count / max(seen_count, 1)
        score += ratio * 30
    else:
        ratio = 0.0

    # Status
    if status == "active":
        score += 10
    elif status != "active":
        score -= 10

    notes = []
    if ratio >= 0.75:
        notes.append("high yield")
    elif ratio <= 0.15 and seen_count >= 5:
        notes.append("low yield")

    if seen_count >= 25:
        notes.append("high volume")
    elif seen_count <= 2:
        notes.append("low history")

    return round(score, 2), ", ".join(notes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/job_agent.db")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    ensure_columns(cur)

    rows = cur.execute(
        """
        SELECT source_key, source_type, source_trust, status,
               COALESCE(seen_count, 0), COALESCE(matching_job_count, 0),
               first_seen_at, last_seen_at, last_success_at
        FROM source_registry
        """
    ).fetchall()

    updated = 0
    for row in rows:
        source_key = row[0]
        priority_score, notes = compute_priority(row)
        cur.execute(
            """
            UPDATE source_registry
            SET priority_score = ?,
                notes = ?,
                last_run_seen_count = COALESCE(last_run_seen_count, 0),
                last_run_matching_count = COALESCE(last_run_matching_count, 0)
            WHERE source_key = ?
            """,
            (priority_score, notes, source_key),
        )
        updated += 1

    conn.commit()

    print(f"Updated {updated} source_registry rows.")

    print("\nTop 15 sources by priority_score:")
    top_rows = cur.execute(
        """
        SELECT source_name, hostname, source_type, source_trust,
               seen_count, matching_job_count, priority_score, notes
        FROM source_registry
        ORDER BY priority_score DESC, matching_job_count DESC, seen_count DESC
        LIMIT 15
        """
    ).fetchall()
    for r in top_rows:
        print(r)

    print("\nBottom 15 sources by priority_score:")
    low_rows = cur.execute(
        """
        SELECT source_name, hostname, source_type, source_trust,
               seen_count, matching_job_count, priority_score, notes
        FROM source_registry
        ORDER BY priority_score ASC, matching_job_count ASC, seen_count ASC
        LIMIT 15
        """
    ).fetchall()
    for r in low_rows:
        print(r)

    run_id, details = load_latest_run(cur)
    print("\nLatest run:", run_id, details)

    conn.close()


if __name__ == "__main__":
    main()
