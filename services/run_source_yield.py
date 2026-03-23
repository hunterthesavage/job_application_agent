from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _get_value(job: Any, key: str) -> str:
    if isinstance(job, dict):
        return safe_text(job.get(key, ""))
    return safe_text(getattr(job, key, ""))


def _source_root_from_job(job: Any) -> str:
    detail = _get_value(job, "source_detail")
    if detail and detail != "in_memory_discovery_result":
        return detail

    url = _get_value(job, "job_posting_url")
    if not url:
        return "unknown"

    parsed = urlparse(url)
    host = safe_text(parsed.netloc).lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if "job-boards.greenhouse.io" in host:
        if path_parts:
            return f"{host}/{path_parts[0]}"
        return host

    if "jobs.lever.co" in host:
        if path_parts:
            return f"{host}/{path_parts[0]}"
        return host

    if "jobs.ashbyhq.com" in host:
        if path_parts:
            return f"{host}/{path_parts[0]}"
        return host

    if "jobs.smartrecruiters.com" in host:
        if path_parts:
            return f"{host}/{path_parts[0]}"
        return host

    if "myworkdayjobs.com" in host:
        return host

    return host or "unknown"


def _source_key(job: Any) -> str:
    ats_type = _get_value(job, "ats_type") or "Unknown"
    source_root = _source_root_from_job(job)
    return f"{ats_type}::{source_root}"


def increment_source_yield(counter: dict[str, dict[str, Any]], job: Any) -> None:
    key = _source_key(job)
    row = counter.setdefault(
        key,
        {
            "source_key": key,
            "source_root": _source_root_from_job(job),
            "ats_type": _get_value(job, "ats_type") or "Unknown",
            "source_trust": _get_value(job, "source_trust") or "Unknown",
            "source_type": _get_value(job, "source_type") or "Unknown",
            "job_count": 0,
        },
    )
    row["job_count"] += 1


def summarize_source_yield(counter: dict[str, dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    rows = list(counter.values())
    rows.sort(
        key=lambda row: (
            int(row.get("job_count", 0)),
            safe_text(row.get("ats_type", "")),
            safe_text(row.get("source_root", "")),
        ),
        reverse=True,
    )
    return rows[:limit]

def detect_source_dominance(counter: dict[str, dict[str, Any]], total_seen: int) -> dict[str, Any]:
    if not counter or total_seen <= 0:
        return {
            "flag": False,
            "share": 0.0,
            "source_key": "",
            "source_root": "",
            "ats_type": "",
            "job_count": 0,
            "reason": "",
        }

    rows = list(counter.values())
    rows.sort(key=lambda row: int(row.get("job_count", 0)), reverse=True)
    top = rows[0]
    top_count = int(top.get("job_count", 0))
    share = top_count / total_seen if total_seen else 0.0

    # Safe first-pass rule:
    # flag if one source contributes at least 35% of the run and at least 10 jobs.
    flag = top_count >= 10 and share >= 0.35

    reason = ""
    if flag:
        reason = (
            f"{safe_text(top.get('ats_type', 'Unknown'))} | "
            f"{safe_text(top.get('source_root', 'unknown'))} contributed "
            f"{top_count} of {total_seen} jobs ({share:.1%})"
        )

    return {
        "flag": flag,
        "share": round(share, 4),
        "source_key": safe_text(top.get("source_key", "")),
        "source_root": safe_text(top.get("source_root", "")),
        "ats_type": safe_text(top.get("ats_type", "")),
        "job_count": top_count,
        "reason": reason,
    }
