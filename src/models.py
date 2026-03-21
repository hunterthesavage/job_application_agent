from dataclasses import dataclass
from datetime import datetime


@dataclass
class JobRecord:
    date_found: str
    date_last_validated: str
    company: str
    title: str
    role_family: str
    normalized_title: str
    location: str
    remote_type: str
    dallas_dfw_match: str
    company_careers_url: str
    job_posting_url: str
    ats_type: str
    requisition_id: str
    source: str
    compensation_raw: str
    compensation_status: str
    validation_status: str
    validation_confidence: str
    fit_score: int
    fit_tier: str
    ai_priority: str
    match_rationale: str
    risk_flags: str
    application_angle: str
    cover_letter_starter: str
    status: str
    duplicate_key: str
    active_status: str

    def to_row(self) -> list:
        return [
            self.date_found,
            self.date_last_validated,
            self.company,
            self.title,
            self.role_family,
            self.normalized_title,
            self.location,
            self.remote_type,
            self.dallas_dfw_match,
            self.company_careers_url,
            self.job_posting_url,
            self.ats_type,
            self.requisition_id,
            self.source,
            self.compensation_raw,
            self.compensation_status,
            self.validation_status,
            self.validation_confidence,
            self.fit_score,
            self.fit_tier,
            self.ai_priority,
            self.match_rationale,
            self.risk_flags,
            self.application_angle,
            self.cover_letter_starter,
            self.status,
            self.duplicate_key,
            self.active_status,
        ]


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")