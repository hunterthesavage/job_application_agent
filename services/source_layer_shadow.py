from __future__ import annotations

from collections import Counter
from typing import Any

from services.db import db_connection


def run_shadow_endpoint_selection(settings: dict[str, str] | None = None) -> dict[str, Any]:
    del settings  # Phase 1 shadow mode is endpoint-inventory only.

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ats_vendor,
                review_status,
                careers_url_status,
                is_primary,
                active
            FROM hiring_endpoints
            WHERE active = 1
            """
        ).fetchall()

    ats_counter: Counter[str] = Counter()
    approved_count = 0
    candidate_count = 0
    primary_count = 0

    for row in rows:
        ats_vendor = str(row["ats_vendor"] or "").strip().lower() or "unknown"
        ats_counter[ats_vendor] += 1

        if str(row["review_status"] or "").strip().lower() == "approved":
            approved_count += 1
        if str(row["careers_url_status"] or "").strip().lower() == "candidate":
            candidate_count += 1
        if int(row["is_primary"] or 0) == 1:
            primary_count += 1

    top_ats = [f"{vendor} {count}" for vendor, count in ats_counter.most_common(5)]

    lines = [
        "Next-gen source layer shadow summary:",
        f"- Active imported endpoints: {len(rows)}",
        f"- Approved endpoints: {approved_count}",
        f"- Candidate endpoints: {candidate_count}",
        f"- Primary endpoints: {primary_count}",
    ]
    if top_ats:
        lines.append(f"- Top ATS families: {', '.join(top_ats)}")
    else:
        lines.append("- Top ATS families: none yet")

    return {
        "active_endpoint_count": len(rows),
        "approved_endpoint_count": approved_count,
        "candidate_endpoint_count": candidate_count,
        "primary_endpoint_count": primary_count,
        "ats_counts": dict(ats_counter),
        "output": "\n".join(lines),
    }
