from src import validate_job_url as validator
from bs4 import BeautifulSoup


def should_pass_title_gate(title: str, settings: dict[str, str]) -> bool:
    """
    Mirrors the intended title-gating behavior:
    - if target_titles exist, use settings title gate
    - otherwise use the legacy strict title gate
    """
    raw_target_titles = str(settings.get("target_titles", "") or "")
    target_titles = [part.strip() for part in raw_target_titles.split(",") if part.strip()]

    if target_titles:
        return validator.passes_settings_title_gate(title, settings)

    return validator.passes_strict_title_gate(title)


def test_exec_role_still_passes_legacy_strict_gate() -> None:
    assert validator.passes_strict_title_gate("VP Technology") is True


def test_generic_manager_role_fails_legacy_strict_gate() -> None:
    assert validator.passes_strict_title_gate("Project Manager") is False


def test_generic_manager_role_passes_when_target_title_is_present() -> None:
    settings = {"target_titles": "project manager"}
    assert should_pass_title_gate("Project Manager", settings) is True


def test_settings_title_gate_is_case_insensitive() -> None:
    settings = {"target_titles": "PROJECT MANAGER"}
    assert validator.passes_settings_title_gate("Senior Project Manager", settings) is True


def test_remote_only_location_gate_accepts_remote() -> None:
    settings = {"remote_only": "true"}
    assert validator.passes_settings_location_gate("Remote", settings) is True


def test_remote_only_location_gate_rejects_non_remote() -> None:
    settings = {"remote_only": "true"}
    assert validator.passes_settings_location_gate("Austin, TX", settings) is False


def test_preferred_location_gate_accepts_dallas() -> None:
    settings = {"preferred_locations": "dallas"}
    assert validator.passes_settings_location_gate("Dallas, TX", settings) is True


def test_preferred_location_gate_rejects_other_city() -> None:
    settings = {"preferred_locations": "dallas"}
    assert validator.passes_settings_location_gate("Austin, TX", settings) is False


def test_infer_location_recognizes_remote_us() -> None:
    text = "This role is remote within the United States."
    assert validator.infer_location(text) == "Remote, United States"


def test_infer_location_recognizes_dallas() -> None:
    text = "Primary Location: Dallas, TX"
    assert validator.infer_location(text) == "Dallas, TX"


def test_infer_company_from_workday_tenant_uses_tenant_name() -> None:
    url = "https://harriscomputer.wd3.myworkdayjobs.com/en-US/1/job/SVP-Technology---Engineering_R0040737"
    assert validator.infer_company_from_domain(url) == "Harris Computer"


def test_extract_company_from_json_ld_prefers_hiring_organization_name() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "JobPosting",
                "title": "SVP Technology & Engineering",
                "hiringOrganization": {
                  "@type": "Organization",
                  "name": "Xapo Bank"
                }
              }
            </script>
          </head>
        </html>
        """,
        "lxml",
    )

    assert validator.extract_company_from_json_ld(soup) == "Xapo Bank"


def test_choose_best_company_name_cleans_title_like_company_candidate() -> None:
    chosen = validator.choose_best_company_name(
        extracted_company="Work from Anywhere) at Xapo Bank",
        fallback_company="Xapo61",
        url="https://job-boards.greenhouse.io/xapo61/jobs/7596633003",
    )
    assert chosen == "Xapo Bank"


def test_choose_best_company_name_prefers_workday_tenant_brand_over_legal_entity_name() -> None:
    chosen = validator.choose_best_company_name(
        extracted_company="New Ultimate Billing, LLC",
        fallback_company="Harris Computer",
        url="https://harriscomputer.wd3.myworkdayjobs.com/en-US/1/job/SVP-Technology---Engineering_R0040737",
    )
    assert chosen == "Harris Computer"
