from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


@dataclass
class CandidateStageRecord:
    url: str
    source_name: str = ""
    source_type: str = ""
    source_trust: str = ""
    query_text: str = ""
    discovery_status: str = "discovered"
    parse_status: str = "pending"
    qualification_status: str = "pending"
    coarse_skip_reason: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    ats_type: str = ""
    compensation_raw: str = ""
    parse_confidence: str = ""
    qualification_score: int = 0
    qualification_confidence: str = ""
    qualification_rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_stage_record(
    url: str,
    source_name: str = "",
    source_type: str = "",
    source_trust: str = "",
    query_text: str = "",
) -> CandidateStageRecord:
    return CandidateStageRecord(
        url=safe_text(url),
        source_name=safe_text(source_name),
        source_type=safe_text(source_type),
        source_trust=safe_text(source_trust),
        query_text=safe_text(query_text),
    )
