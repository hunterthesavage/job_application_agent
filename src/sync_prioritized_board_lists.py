from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable


def fetch_ranked_sources(conn: sqlite3.Connection, ats_type: str) -> list[dict]:
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
            source_key,
            source_root,
            hostname,
            ats_type,
            source_type,
            source_trust,
            seen_count,
            matching_job_count,
            COALESCE(priority_score, 0) AS priority_score,
            COALESCE(priority_notes, '') AS priority_notes,
            COALESCE(status, 'active') AS status
        FROM source_registry
        WHERE ats_type = ?
          AND COALESCE(source_root, '') <> ''
          AND COALESCE(status, 'active') = 'active'
        ORDER BY
            COALESCE(priority_score, 0) DESC,
            matching_job_count DESC,
            seen_count DESC,
            source_root ASC
        """,
        (ats_type,),
    ).fetchall()

    cols = [
        "source_key",
        "source_root",
        "hostname",
        "ats_type",
        "source_type",
        "source_trust",
        "seen_count",
        "matching_job_count",
        "priority_score",
        "priority_notes",
        "status",
    ]
    return [dict(zip(cols, row)) for row in rows]


def unique_roots(rows: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    output: list[dict] = []
    for row in rows:
        root = (row.get("source_root") or "").strip()
        if not root or root in seen:
            continue
        seen.add(root)
        output.append(row)
    return output


def is_strong_source(row: dict, min_priority: float, min_matches: int) -> bool:
    return float(row.get("priority_score", 0) or 0) >= min_priority or int(row.get("matching_job_count", 0) or 0) >= min_matches


def split_sources(rows: list[dict], min_priority: float, min_matches: int) -> tuple[list[dict], list[dict]]:
    strong: list[dict] = []
    weak: list[dict] = []
    for row in rows:
        if is_strong_source(row, min_priority=min_priority, min_matches=min_matches):
            strong.append(row)
        else:
            weak.append(row)
    return strong, weak


def apply_caps(rows: list[dict], strong_cap: int, weak_cap: int, min_priority: float, min_matches: int) -> tuple[list[dict], list[dict], list[dict]]:
    deduped = unique_roots(rows)
    strong, weak = split_sources(deduped, min_priority=min_priority, min_matches=min_matches)
    kept = strong[:strong_cap] + weak[:weak_cap]
    dropped = strong[strong_cap:] + weak[weak_cap:]
    return kept, strong, dropped


def write_board_file(path: Path, rows: list[dict]) -> None:
    lines = [row["source_root"].strip() for row in rows if row.get("source_root")]
    content = "\n".join(lines).strip() + ("\n" if lines else "")
    path.write_text(content)


def print_preview(label: str, kept: list[dict], strong: list[dict], dropped: list[dict]) -> None:
    print(f"\n=== {label} ===")
    print(f"Strong sources found: {len(strong)}")
    print(f"Kept sources: {len(kept)}")
    print(f"Dropped sources: {len(dropped)}")

    print("\nTop kept sources:")
    for row in kept[:15]:
        print(
            f"- {row['source_root']} | score={row['priority_score']} | "
            f"matches={row['matching_job_count']} | seen={row['seen_count']} | notes={row['priority_notes']}"
        )

    if dropped:
        print("\nTop dropped sources:")
        for row in dropped[:10]:
            print(
                f"- {row['source_root']} | score={row['priority_score']} | "
                f"matches={row['matching_job_count']} | seen={row['seen_count']} | notes={row['priority_notes']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync prioritized ATS board lists with source-aware caps.")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--repo-root", required=True, help="Repo root containing greenhouse_boards.txt and lever_boards.txt")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    parser.add_argument("--greenhouse-strong-cap", type=int, default=40)
    parser.add_argument("--greenhouse-weak-cap", type=int, default=20)
    parser.add_argument("--lever-strong-cap", type=int, default=25)
    parser.add_argument("--lever-weak-cap", type=int, default=15)
    parser.add_argument("--min-priority", type=float, default=60.0)
    parser.add_argument("--min-matches", type=int, default=3)
    args = parser.parse_args()

    db_path = Path(args.db)
    repo_root = Path(args.repo_root)

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    if not repo_root.exists():
        raise SystemExit(f"Repo root not found: {repo_root}")

    conn = sqlite3.connect(str(db_path))
    try:
        greenhouse_rows = fetch_ranked_sources(conn, "Greenhouse")
        lever_rows = fetch_ranked_sources(conn, "Lever")
    finally:
        conn.close()

    gh_kept, gh_strong, gh_dropped = apply_caps(
        greenhouse_rows,
        strong_cap=args.greenhouse_strong_cap,
        weak_cap=args.greenhouse_weak_cap,
        min_priority=args.min_priority,
        min_matches=args.min_matches,
    )
    lv_kept, lv_strong, lv_dropped = apply_caps(
        lever_rows,
        strong_cap=args.lever_strong_cap,
        weak_cap=args.lever_weak_cap,
        min_priority=args.min_priority,
        min_matches=args.min_matches,
    )

    print_preview("Greenhouse", gh_kept, gh_strong, gh_dropped)
    print_preview("Lever", lv_kept, lv_strong, lv_dropped)

    if args.dry_run:
        print("\nDry run only. No files were written.")
        return 0

    gh_path = repo_root / "greenhouse_boards.txt"
    lv_path = repo_root / "lever_boards.txt"
    write_board_file(gh_path, gh_kept)
    write_board_file(lv_path, lv_kept)

    print("\nWrote prioritized board files:")
    print(f"- {gh_path} ({len(gh_kept)} sources)")
    print(f"- {lv_path} ({len(lv_kept)} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
