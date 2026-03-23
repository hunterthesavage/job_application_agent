
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def print_section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def print_counter(title: str, rows) -> None:
    print_section(title)
    for key, count in rows:
        print(f"{key}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Board-level source registry report")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--limit", type=int, default=25, help="Rows per section")
    args = parser.parse_args()

    conn = connect(args.db)
    limit = args.limit

    print_section("Registry counts")
    total = conn.execute("SELECT COUNT(*) AS c FROM source_registry").fetchone()["c"]
    print(f"total_sources: {total}")

    for field in ("source_trust", "source_type", "ats_type", "hostname"):
        rows = conn.execute(
            f"""
            SELECT COALESCE(NULLIF({field}, ''), '<<blank>>') AS key, COUNT(*) AS c
            FROM source_registry
            GROUP BY 1
            ORDER BY c DESC, key
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        print_counter(f"{field} mix", [(row["key"], row["c"]) for row in rows])

    score_col = "priority_score" if has_column(conn, "source_registry", "priority_score") else None
    note_col = "priority_note" if has_column(conn, "source_registry", "priority_note") else None

    order_by = "COALESCE(priority_score, 0) DESC, matching_job_count DESC, seen_count DESC, source_key"
    score_select = "COALESCE(priority_score, 0) AS priority_score," if score_col else "0 AS priority_score,"
    note_select = "COALESCE(priority_note, '') AS priority_note," if note_col else "'' AS priority_note,"

    print_section("Top sources by source_key")
    rows = conn.execute(
        f"""
        SELECT
            source_key,
            source_root,
            hostname,
            ats_type,
            source_type,
            source_trust,
            seen_count,
            matching_job_count,
            {score_select}
            {note_select}
            last_seen_at
        FROM source_registry
        ORDER BY {order_by}
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in rows:
        print(
            f"{row['source_key']} | score={row['priority_score']} | "
            f"match={row['matching_job_count']} | seen={row['seen_count']} | "
            f"ats={row['ats_type']} | trust={row['source_trust']} | root={row['source_root']} | "
            f"note={row['priority_note']}"
        )

    print_section("Top roots")
    rows = conn.execute(
        f"""
        SELECT
            source_root,
            hostname,
            ats_type,
            COUNT(*) AS source_rows,
            SUM(seen_count) AS total_seen,
            SUM(matching_job_count) AS total_matching,
            AVG(COALESCE(priority_score, 0)) AS avg_priority
        FROM source_registry
        GROUP BY source_root, hostname, ats_type
        ORDER BY total_matching DESC, total_seen DESC, avg_priority DESC, source_root
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in rows:
        print(
            f"{row['source_root']} | ats={row['ats_type']} | host={row['hostname']} | "
            f"rows={row['source_rows']} | matching={row['total_matching']} | "
            f"seen={row['total_seen']} | avg_score={round(row['avg_priority'] or 0, 2)}"
        )

    print_section("Low-yield candidates")
    rows = conn.execute(
        f"""
        SELECT
            source_key,
            source_root,
            ats_type,
            seen_count,
            matching_job_count,
            COALESCE(priority_score, 0) AS priority_score,
            COALESCE(priority_note, '') AS priority_note
        FROM source_registry
        WHERE seen_count >= 3
          AND matching_job_count <= 1
        ORDER BY COALESCE(priority_score, 0) ASC, seen_count DESC, source_key
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    if not rows:
        print("No low-yield sources found with current thresholds.")
    else:
        for row in rows:
            print(
                f"{row['source_key']} | score={row['priority_score']} | "
                f"match={row['matching_job_count']} | seen={row['seen_count']} | note={row['priority_note']}"
            )

    conn.close()


if __name__ == "__main__":
    main()
