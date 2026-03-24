import html
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st

from config import JOB_URLS_FILE, LATEST_PIPELINE_LOG_PATH
from services.ingestion import get_recent_ingestion_runs, get_source_registry_summary
from services.job_levels import (
    JOB_LEVEL_OPTIONS,
    parse_preferred_job_levels,
    serialize_preferred_job_levels,
)
from services.readiness import get_readiness_summary
from services.pipeline_runtime import (
    build_search_preview,
    discover_and_ingest,
    discover_job_links,
    ingest_pasted_urls,
    ingest_urls_from_file,
    rescore_existing_jobs,
)
from services.job_store import count_jobs_for_rescoring
from services.settings import load_settings, save_settings
from services.ui_busy import (
    app_is_busy,
    clear_action,
    get_action,
    move_action_to_execute,
    queue_action,
    stop_busy,
)
from ui.navigation import initialize_nav_state, render_button_nav


RESCORE_LIMIT_OPTIONS = [
    ("25", 25),
    ("50", 50),
    ("100", 100),
    ("All", 0),
]

RESCORE_STALE_OPTIONS = [
    ("All ages", 0),
    ("Older than 7 days", 7),
    ("Older than 14 days", 14),
    ("Older than 30 days", 30),
]

PIPELINE_NAV_OPTIONS = [
    "Overview",
    "Run Jobs",
    "Results",
    "Research",
]


def _render_ai_button_chip() -> None:
    st.markdown(
        '<div class="ai-button-chip-wrap"><span class="ai-button-chip" title="Uses OpenAI">AI</span></div>',
        unsafe_allow_html=True,
    )


def _inject_pipeline_css() -> None:
    st.markdown(
        """
        <style>
            .pipeline-page-intro {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 1rem;
                margin-bottom: 1rem;
            }

            .pipeline-page-intro-copy {
                max-width: 780px;
            }

            .pipeline-page-kicker {
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.10em;
                text-transform: uppercase;
                color: rgba(147,197,253,0.90);
                margin-bottom: 0.28rem;
            }

            .pipeline-page-title {
                font-size: 1.58rem;
                font-weight: 840;
                line-height: 1.02;
                color: rgba(255,255,255,0.98);
                letter-spacing: -0.03em;
                margin-bottom: 0.3rem;
            }

            .pipeline-page-copy {
                font-size: 0.95rem;
                line-height: 1.48;
                color: rgba(255,255,255,0.72);
                max-width: 780px;
            }

            .pipeline-section-card {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                background:
                    radial-gradient(circle at top right, rgba(59,130,246,0.10), transparent 26%),
                    linear-gradient(180deg, rgba(16,22,36,0.97) 0%, rgba(10,14,24,0.99) 100%);
                box-shadow: 0 18px 48px rgba(0,0,0,0.24);
                padding: 1.18rem 1.18rem 1.02rem 1.18rem;
                margin-bottom: 1rem;
            }

            .pipeline-section-card.compact {
                padding-bottom: 0.85rem;
            }

            .pipeline-section-kicker {
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.10em;
                text-transform: uppercase;
                color: rgba(191,219,254,0.88);
                margin-bottom: 0.28rem;
            }

            .pipeline-section-title {
                font-size: 1.15rem;
                font-weight: 820;
                color: rgba(255,255,255,0.98);
                letter-spacing: -0.02em;
                margin-bottom: 0.18rem;
            }

            .pipeline-section-heading {
                display: flex;
                align-items: center;
                gap: 0.7rem;
                margin-bottom: 0.18rem;
            }

            .pipeline-step-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 1.95rem;
                height: 1.95rem;
                border-radius: 999px;
                background: linear-gradient(180deg, rgba(96,165,250,0.24) 0%, rgba(59,130,246,0.16) 100%);
                border: 1px solid rgba(96,165,250,0.42);
                color: rgba(219,234,254,0.98);
                font-size: 0.92rem;
                font-weight: 840;
                box-shadow: 0 8px 18px rgba(37,99,235,0.16);
                flex-shrink: 0;
            }

            .pipeline-section-copy {
                font-size: 0.92rem;
                line-height: 1.45;
                color: rgba(255,255,255,0.72);
                margin-bottom: 0.9rem;
                max-width: 860px;
            }

            .pipeline-cta-strip {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.8rem;
                margin-bottom: 1rem;
            }

            .pipeline-cta-tile {
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.07);
                background: linear-gradient(180deg, rgba(17,24,39,0.90) 0%, rgba(11,16,26,0.97) 100%);
                padding: 0.9rem 0.95rem;
                box-shadow: 0 10px 24px rgba(0,0,0,0.16);
            }

            .pipeline-cta-label {
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.62);
                margin-bottom: 0.32rem;
            }

            .pipeline-cta-title {
                font-size: 1.02rem;
                font-weight: 780;
                color: rgba(255,255,255,0.98);
                margin-bottom: 0.22rem;
            }

            .pipeline-cta-copy {
                font-size: 0.88rem;
                line-height: 1.4;
                color: rgba(255,255,255,0.70);
            }

            .pipeline-compact-note {
                font-size: 0.87rem;
                line-height: 1.45;
                color: rgba(255,255,255,0.68);
                margin-bottom: 0.7rem;
            }

            .pipeline-card {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 22px;
                background: linear-gradient(180deg, rgba(16,22,36,0.96) 0%, rgba(10,14,24,0.98) 100%);
                box-shadow: 0 18px 48px rgba(0,0,0,0.24);
                padding: 1.15rem 1.15rem 1rem 1.15rem;
                margin-bottom: 1rem;
            }

            .pipeline-ops-card {
                position: relative;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                background:
                    radial-gradient(circle at top right, rgba(59,130,246,0.16), transparent 28%),
                    linear-gradient(180deg, rgba(15,22,38,0.98) 0%, rgba(9,13,22,0.99) 100%);
                box-shadow: 0 20px 54px rgba(0,0,0,0.26);
                padding: 1.25rem 1.25rem 1.05rem 1.25rem;
                margin-bottom: 1rem;
            }

            .pipeline-ops-kicker {
                font-size: 0.82rem;
                font-weight: 800;
                letter-spacing: 0.10em;
                text-transform: uppercase;
                color: rgba(147,197,253,0.94);
                margin-bottom: 0.42rem;
            }

            .pipeline-ops-title {
                font-size: 1.72rem;
                font-weight: 840;
                line-height: 1.02;
                color: rgba(255,255,255,0.98);
                letter-spacing: -0.03em;
                margin-bottom: 0.35rem;
            }

            .pipeline-ops-copy {
                font-size: 0.98rem;
                line-height: 1.5;
                color: rgba(255,255,255,0.76);
                margin-bottom: 1rem;
                max-width: 920px;
            }

            .pipeline-status-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.8rem;
                margin-bottom: 0.8rem;
            }

            .pipeline-status-tile {
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.07);
                background: linear-gradient(180deg, rgba(17,24,39,0.94) 0%, rgba(11,16,26,0.98) 100%);
                padding: 0.9rem 0.95rem 0.85rem 0.95rem;
                box-shadow: 0 10px 24px rgba(0,0,0,0.18);
            }

            .pipeline-readiness-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.8rem;
                margin-bottom: 0.9rem;
            }

            .pipeline-readiness-grid.capabilities {
                grid-template-columns: repeat(3, minmax(0, 1fr));
                margin-top: 0.2rem;
            }

            .pipeline-readiness-tile {
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.07);
                background: linear-gradient(180deg, rgba(17,24,39,0.94) 0%, rgba(11,16,26,0.98) 100%);
                padding: 0.9rem 0.95rem 0.88rem 0.95rem;
                box-shadow: 0 10px 24px rgba(0,0,0,0.18);
            }

            .pipeline-readiness-label {
                font-size: 0.80rem;
                font-weight: 700;
                color: rgba(255,255,255,0.68);
                margin-bottom: 0.35rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .pipeline-readiness-value {
                font-size: 1.02rem;
                font-weight: 780;
                color: rgba(255,255,255,0.98);
                line-height: 1.1;
                margin-bottom: 0.22rem;
            }

            .pipeline-readiness-value.ready {
                color: rgba(134, 239, 172, 0.98);
            }

            .pipeline-readiness-value.warning {
                color: rgba(253, 224, 71, 0.96);
            }

            .pipeline-readiness-detail {
                font-size: 0.84rem;
                line-height: 1.35;
                color: rgba(255,255,255,0.68);
            }

            .pipeline-status-label {
                font-size: 0.80rem;
                font-weight: 700;
                color: rgba(255,255,255,0.68);
                margin-bottom: 0.35rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .pipeline-status-value {
                font-size: 1.30rem;
                font-weight: 820;
                color: rgba(255,255,255,0.98);
                line-height: 1.05;
                letter-spacing: -0.02em;
            }

            .pipeline-card-title {
                font-size: 1.08rem;
                font-weight: 800;
                color: rgba(255,255,255,0.97);
                margin-bottom: 0.15rem;
                letter-spacing: -0.02em;
            }

            .pipeline-card-copy {
                font-size: 0.93rem;
                color: rgba(255,255,255,0.72);
                margin-bottom: 0.85rem;
            }

            .pipeline-secondary-actions-note {
                font-size: 0.86rem;
                color: rgba(255,255,255,0.68);
                margin-top: 0.1rem;
                margin-bottom: 0.75rem;
            }

            .pipeline-diagnostic-line {
                padding: 0.55rem 0.75rem;
                border-radius: 14px;
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                margin-bottom: 0.55rem;
                color: rgba(255,255,255,0.90);
                font-size: 0.92rem;
            }

            .pipeline-takeaway {
                padding: 0.8rem 0.95rem;
                border-radius: 16px;
                background: rgba(59,130,246,0.10);
                border: 1px solid rgba(59,130,246,0.20);
                color: rgba(219,234,254,0.96);
                font-size: 0.93rem;
                margin-bottom: 0.75rem;
            }

            @media (max-width: 1100px) {
                .pipeline-page-intro {
                    flex-direction: column;
                }

                .pipeline-cta-strip {
                    grid-template-columns: 1fr;
                }

                .pipeline-status-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .pipeline-readiness-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .pipeline-readiness-grid.capabilities {
                    grid-template-columns: 1fr;
                }
            }

            @media (max-width: 680px) {
                .pipeline-status-grid {
                    grid-template-columns: 1fr;
                }

                .pipeline-readiness-grid {
                    grid-template-columns: 1fr;
                }

                .pipeline-ops-title {
                    font-size: 1.38rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _str_to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def _humanize_pipeline_status(value: str) -> str:
    mapping = {
        "idle": "Idle",
        "discover_and_ingest": "Discover and Ingest Jobs",
        "discover_only": "Find Job Links Only",
        "ingest_saved": "Add Saved Job Links",
        "ingest_pasted": "Add Pasted Job Links",
        "completed": "Completed",
        "running": "Running",
        "error": "Needs Attention",
    }
    normalized = str(value or "").strip().lower()
    if normalized in mapping:
        return mapping[normalized]
    return str(value or "Idle").replace("_", " ").strip().title() or "Idle"


def _set_flash(level: str, message: str) -> None:
    st.session_state["pipeline_flash_level"] = level
    st.session_state["pipeline_flash_message"] = message


def _render_flash() -> None:
    message = st.session_state.pop("pipeline_flash_message", "")
    level = st.session_state.pop("pipeline_flash_level", "success")

    if not message:
        return

    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.success(message)


def _navigate_pipeline_section(section: str) -> None:
    st.session_state["pipeline_subnav_selection"] = section
    st.rerun()


def _render_subpage_intro(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="pipeline-page-intro">
            <div class="pipeline-page-intro-copy">
                <div class="pipeline-page-kicker">{html.escape(kicker)}</div>
                <div class="pipeline-page-title">{html.escape(title)}</div>
                <div class="pipeline-page-copy">{html.escape(copy)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_shell(
    kicker: str,
    title: str,
    copy: str,
    *,
    compact: bool = False,
    step: str = "",
) -> None:
    compact_class = " compact" if compact else ""
    step_markup = ""
    if step:
        step_markup = f'<span class="pipeline-step-badge">{html.escape(step)}</span>'
    st.markdown(
        f"""
        <div class="pipeline-section-card{compact_class}">
            <div class="pipeline-section-kicker">{html.escape(kicker)}</div>
            <div class="pipeline-section-heading">
                {step_markup}
                <div class="pipeline-section-title">{html.escape(title)}</div>
            </div>
            <div class="pipeline-section-copy">{html.escape(copy)}</div>
        """,
        unsafe_allow_html=True,
    )


def _close_section_shell() -> None:
    st.markdown("</div>", unsafe_allow_html=True)



def _persist_pipeline_output(result: dict) -> None:
    try:
        LATEST_PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        output = str((result or {}).get("output", "") or "")
        LATEST_PIPELINE_LOG_PATH.write_text(output, encoding="utf-8")
    except Exception:
        pass


def _render_result(result: dict) -> None:
    if result.get("status") == "completed":
        if result.get("output"):
            st.text(result["output"])
    else:
        st.error("Action failed.")
        if result.get("output"):
            st.text(result["output"])


def _job_urls_file_exists() -> bool:
    return Path(JOB_URLS_FILE).exists()


def _is_first_run_pipeline_state() -> bool:
    last_result = st.session_state.get("pipeline_last_result")
    latest_run = _get_latest_run()
    return not bool(last_result) and latest_run is None


def _build_discover_and_ingest_flash(result: dict) -> tuple[str, str]:
    discovery = result.get("discovery", {}) or {}
    ingest = result.get("ingest", {}) or {}

    seen_urls = int(ingest.get("seen_urls", discovery.get("url_count", 0)) or 0)
    accepted_jobs = int(ingest.get("accepted_jobs", 0) or 0)
    skipped_count = int(ingest.get("skipped_count", 0) or 0)
    error_count = int(ingest.get("error_count", 0) or 0)

    summary = ingest.get("summary", {}) or {}
    inserted_count = int(summary.get("inserted_count", 0) or 0)
    updated_count = int(summary.get("updated_count", 0) or 0)
    net_new_count = int(summary.get("net_new_count", inserted_count) or 0)
    rediscovered_count = int(summary.get("rediscovered_count", 0) or 0)
    duplicate_in_run_count = int(summary.get("duplicate_in_run_count", 0) or 0)

    changed_count = inserted_count + updated_count

    if changed_count > 0:
        parts = []
        if net_new_count > 0:
            parts.append(f"{net_new_count} net new")
        if rediscovered_count > 0:
            parts.append(f"{rediscovered_count} rediscovered")
        if duplicate_in_run_count > 0:
            parts.append(f"{duplicate_in_run_count} duplicate in run")
        if not parts:
            if inserted_count > 0:
                parts.append(f"{inserted_count} added")
            if updated_count > 0:
                parts.append(f"{updated_count} updated")
        return "success", f"✓ Job run complete: {', '.join(parts)}"

    if seen_urls == 0:
        return "warning", "No job URLs were discovered. Try the fallback search links below or broaden your criteria."

    if accepted_jobs == 0 and skipped_count > 0:
        return "warning", f"{seen_urls} URLs were found, but none matched your current run inputs."

    if accepted_jobs > 0 and changed_count == 0:
        if duplicate_in_run_count > 0:
            return "warning", f"{seen_urls} URLs were reviewed, but only duplicate-in-run matches were found."
        if error_count > 0:
            return "warning", f"{seen_urls} URLs were reviewed, but no jobs were added. {error_count} processing errors occurred."
        return "warning", f"{seen_urls} URLs were reviewed, but no net-new or rediscovered jobs were added."

    if error_count > 0:
        return "warning", f"Run completed with {error_count} processing errors and no added jobs."

    return "warning", "Run completed, but no jobs were added."


def _build_ingest_flash(result: dict, source_label: str) -> tuple[str, str]:
    summary = result.get("summary", {}) or {}
    inserted_count = int(summary.get("inserted_count", 0) or 0)
    updated_count = int(summary.get("updated_count", 0) or 0)
    net_new_count = int(summary.get("net_new_count", inserted_count) or 0)
    rediscovered_count = int(summary.get("rediscovered_count", 0) or 0)
    duplicate_in_run_count = int(summary.get("duplicate_in_run_count", 0) or 0)
    seen_urls = int(result.get("seen_urls", 0) or 0)
    accepted_jobs = int(result.get("accepted_jobs", 0) or 0)
    skipped_count = int(result.get("skipped_count", 0) or 0)
    error_count = int(result.get("error_count", 0) or 0)

    changed_count = inserted_count + updated_count

    if changed_count > 0:
        parts = []
        if net_new_count > 0:
            parts.append(f"{net_new_count} net new")
        if rediscovered_count > 0:
            parts.append(f"{rediscovered_count} rediscovered")
        if duplicate_in_run_count > 0:
            parts.append(f"{duplicate_in_run_count} duplicate in run")
        if not parts:
            if inserted_count > 0:
                parts.append(f"{inserted_count} added")
            if updated_count > 0:
                parts.append(f"{updated_count} updated")
        return "success", f"✓ {source_label} complete: {', '.join(parts)}"

    if seen_urls == 0:
        return "warning", f"No job URLs were available for {source_label.lower()}."

    if accepted_jobs == 0 and skipped_count > 0:
        return "warning", f"{seen_urls} URLs were reviewed for {source_label.lower()}, but none matched your current run inputs."

    if duplicate_in_run_count > 0:
        return "warning", f"{source_label} completed, but only duplicate-in-run matches were found."

    if error_count > 0:
        return "warning", f"{source_label} completed with {error_count} processing errors and no added jobs."

    return "warning", f"{source_label} completed, but no net-new or rediscovered jobs were added."


def _build_discover_only_flash(result: dict) -> tuple[str, str]:
    url_count = int(result.get("url_count", 0) or 0)
    if url_count > 0:
        return "success", f"✓ Job link discovery complete: {url_count} URLs found"
    return "warning", "No job URLs were discovered."


def _build_rescore_flash(result: dict) -> tuple[str, str]:
    rescored_count = int(result.get("rescored_count", 0) or 0)
    changed_count = int(result.get("changed_count", 0) or 0)
    error_count = int(result.get("error_count", 0) or 0)
    total_considered = int(result.get("total_considered", 0) or 0)

    if rescored_count > 0:
        return "success", (
            f"Rescored {rescored_count} existing jobs. "
            f"{changed_count} changed under the new scoring rules."
        )

    if total_considered == 0 and error_count == 0:
        return "warning", "No existing jobs were available to rescore."

    if error_count > 0:
        return "warning", f"Rescore completed with {error_count} errors and no updated scores."

    return "warning", "Rescore completed, but no jobs were updated."


def _process_pending_action_before_render() -> None:
    action = get_action("pipeline")
    if not action or action.get("phase") != "execute":
        return

    try:
        action_type = action.get("type")
        payload = action.get("payload", {})
        label = action.get("label", "Working")

        with st.spinner(f"{label}..."):
            if action_type == "discover_and_ingest":
                result = discover_and_ingest(
                    use_ai_title_expansion=bool(payload.get("use_ai_title_expansion", True)),
                    use_ai_scoring=bool(payload.get("use_ai_scoring", True)),
                )
                st.session_state["pipeline_last_result"] = result
                _persist_pipeline_output(result)
                level, message = _build_discover_and_ingest_flash(result)
                _set_flash(level, message)
                st.cache_data.clear()

            elif action_type == "ingest_pasted":
                result = ingest_pasted_urls(
                    payload.get("manual_urls", ""),
                    use_ai_scoring=bool(payload.get("use_ai_scoring", True)),
                )
                st.session_state["pipeline_last_result"] = result
                _persist_pipeline_output(result)
                level, message = _build_ingest_flash(result, "Pasted job link import")
                _set_flash(level, message)
                st.cache_data.clear()

            elif action_type == "ingest_saved":
                if not _job_urls_file_exists():
                    st.session_state["pipeline_last_result"] = {
                        "status": "skipped",
                        "output": f"No saved job link file found yet at: {JOB_URLS_FILE}",
                    }
                    _set_flash("warning", "No saved job links file exists yet. Run discovery first or paste job links.")
                else:
                    result = ingest_urls_from_file(
                        JOB_URLS_FILE,
                        use_ai_scoring=bool(payload.get("use_ai_scoring", True)),
                    )
                    st.session_state["pipeline_last_result"] = result
                    _persist_pipeline_output(result)
                    level, message = _build_ingest_flash(result, "Saved job link import")
                    _set_flash(level, message)
                    st.cache_data.clear()

            elif action_type == "discover_only":
                result = discover_job_links(
                    use_ai_title_expansion=bool(payload.get("use_ai_title_expansion", True)),
                )
                st.session_state["pipeline_last_result"] = result
                _persist_pipeline_output(result)
                level, message = _build_discover_only_flash(result)
                _set_flash(level, message)

            elif action_type == "rescore_existing_jobs":
                result = rescore_existing_jobs(
                    limit=int(payload.get("limit", 0) or 0),
                    stale_days=int(payload.get("stale_days", 0) or 0),
                )
                st.session_state["pipeline_last_result"] = result
                _persist_pipeline_output(result)
                level, message = _build_rescore_flash(result)
                _set_flash(level, message)
                st.cache_data.clear()

    except Exception as exc:
        _set_flash("error", f"That action could not finish: {exc}")
    finally:
        clear_action("pipeline")
        stop_busy()
        st.rerun()


def _advance_pending_action_after_render() -> None:
    action = get_action("pipeline")
    if action and action.get("phase") == "prepare":
        move_action_to_execute("pipeline")
        st.rerun()


def _render_search_summary() -> None:
    preview = build_search_preview()
    plan = preview.get("plan", [])
    queries = preview.get("queries", [])

    st.markdown("### Search Summary")

    if plan:
        for line in plan:
            st.write(f"- {line}")

    if queries:
        with st.expander("Preview generated search queries", expanded=False):
            for query in queries:
                st.code(query, language="text")


def _render_google_search_links() -> None:
    preview = build_search_preview()
    queries = preview.get("queries", [])[:8]

    if not queries:
        return

    st.markdown("### Fallback Search Links")
    st.caption("If discovery is light, use these direct Google searches to inspect the market manually.")

    for query in queries:
        encoded = quote_plus(query)
        st.markdown(f"- [Search Google for: {query}](https://www.google.com/search?q={encoded})")


def _render_source_registry_visibility() -> None:
    st.markdown("### Source Registry")
    st.caption("This shows how many source roots the app currently knows and how trustworthy they are.")

    try:
        summary = get_source_registry_summary()
    except Exception as exc:
        st.warning(f"Could not load source registry yet: {exc}")
        return

    totals = summary.get("totals", {}) or {}
    recent_sources = summary.get("recent_sources", []) or []

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Known Sources", int(totals.get("total_sources", 0) or 0))
    c2.metric("ATS Confirmed", int(totals.get("ats_confirmed_sources", 0) or 0))
    c3.metric("Career Site", int(totals.get("career_site_sources", 0) or 0))
    c4.metric("Web Discovered", int(totals.get("web_discovered_sources", 0) or 0))

    if recent_sources:
        with st.expander("Recent active sources", expanded=False):
            for item in recent_sources:
                source_name = str(item.get("source_name", "") or item.get("hostname", "Unknown source"))
                hostname = str(item.get("hostname", "") or "")
                source_trust = str(item.get("source_trust", "Unknown") or "Unknown")
                source_type = str(item.get("source_type", "Unknown") or "Unknown")
                matching_count = int(item.get("matching_job_count", 0) or 0)
                last_success = str(item.get("last_success_at", "") or "")
                label = source_name if not hostname else f"{source_name} ({hostname})"
                st.write(f"- {label} | {source_trust} | {source_type} | matched jobs: {matching_count} | last seen: {last_success}")
    else:
        st.info("No source registry entries yet. Run a job import first.")


def _render_recent_runs() -> None:
    st.markdown("### Recent Job Runs")
    runs = get_recent_ingestion_runs(limit=8)

    if not runs:
        st.info("No ingestion history yet.")
        return

    for run in runs:
        summary = run.get("details", {}) or {}
        trust_counts = summary.get("source_trust_counts", {}) or {}
        trust_text = ", ".join([f"{k}: {v}" for k, v in trust_counts.items()])

        inserted_count = int(run.get("inserted_count", 0) or 0)
        net_new_count = int(summary.get("net_new_count", inserted_count) or 0)
        rediscovered_count = int(summary.get("rediscovered_count", 0) or 0)
        duplicate_in_run_count = int(summary.get("duplicate_in_run_count", 0) or 0)
        error_count = int(run.get("error_count", 0) or 0)

        run_parts = []
        if net_new_count > 0:
            run_parts.append(f"net new {net_new_count}")
        if rediscovered_count > 0:
            run_parts.append(f"rediscovered {rediscovered_count}")
        if duplicate_in_run_count > 0:
            run_parts.append(f"duplicate in run {duplicate_in_run_count}")
        if not run_parts:
            run_parts.append(f"net new {net_new_count}")
            run_parts.append(f"rediscovered {rediscovered_count}")

        headline = (
            f"Run #{run['id']} | {run['source_name']} | "
            f"{' | '.join(run_parts)} | "
            f"errors {error_count}"
        )
        st.write(headline)
        if trust_text:
            st.caption(f"Trust mix: {trust_text}")


def _format_elapsed(start_iso: str) -> str:
    if not start_iso:
        return "00:00:00"
    try:
        started = datetime.fromisoformat(start_iso)
    except Exception:
        return "00:00:00"
    delta = datetime.now() - started
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _parse_sqlite_datetime(value: str):
    text = str(value or "").strip()
    if not text:
        return None

    candidates = [
        text,
        text.replace("Z", "+00:00"),
        text.replace(" ", "T"),
        text.replace(" ", "T").replace("Z", "+00:00"),
    ]

    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass

    return None


def _format_run_duration(started_at: str, completed_at: str) -> str:
    if not started_at or not completed_at:
        return "Unknown"

    start = _parse_sqlite_datetime(started_at)
    end = _parse_sqlite_datetime(completed_at)

    if not start or not end:
        return "Unknown"

    total_seconds = max(0, int((end - start).total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _get_latest_run() -> dict | None:
    runs = get_recent_ingestion_runs(limit=1)
    if not runs:
        return None
    return runs[0]


def _extract_line_items(output: str, header: str) -> list[str]:
    lines = output.splitlines()
    collected: list[str] = []
    active = False

    for raw in lines:
        line = str(raw).rstrip()
        if not active:
            if line.strip() == header:
                active = True
            continue

        if not line.strip():
            break

        if not line.lstrip().startswith("- "):
            break

        collected.append(line.strip()[2:])

    return collected


def _build_diagnostics_from_last_result() -> dict[str, Any]:
    last_result = st.session_state.get("pipeline_last_result") or {}
    output = str(last_result.get("output", "") or "")

    discovery_lines = _extract_line_items(output, "Discovery URL drop summary:")
    skip_lines = _extract_line_items(output, "Skip summary:")

    takeaway = ""
    lower_output = output.lower()

    if any("location_mismatch" in line for line in skip_lines):
        takeaway = "Most post-parse rejects came from location mismatch. That suggests the run was limited more by location strictness than by title relevance."
    elif any("title_mismatch" in line for line in skip_lines):
        takeaway = "Most post-parse rejects came from title mismatch. That suggests the search is discovering jobs, but they are drifting off your intended role family."
    elif any("weak_url_title_match" in line for line in skip_lines):
        takeaway = "A meaningful share of candidates are being dropped by the URL title prefilter. That suggests the current prefilter may be too brittle for some ATS URL patterns."
    elif "blocked_domain" in lower_output:
        takeaway = "Discovery is still pulling in wrapper and ad-style links from search. The main discovery issue in this run appears to be noisy source quality before parsing."
    elif discovery_lines or skip_lines:
        takeaway = "The run completed, but the biggest limiter is still hidden in the skip and drop mix rather than in ingest errors."

    return {
        "discovery_lines": discovery_lines[:5],
        "skip_lines": skip_lines[:5],
        "takeaway": takeaway,
    }


def _render_pipeline_operations_card() -> None:
    latest_run = _get_latest_run()
    busy = app_is_busy()

    current_status = "Running" if busy else "Ready"
    current_action = ""
    elapsed = "—"

    if busy:
        current_action = _humanize_pipeline_status(st.session_state.get("_app_busy_label", "Working"))
        elapsed = _format_elapsed(st.session_state.get("pipeline_run_started_at", ""))
    elif latest_run:
        current_action = _humanize_pipeline_status(latest_run.get("status", "Idle"))
        elapsed = _format_run_duration(
            str(latest_run.get("started_at", "") or ""),
            str(latest_run.get("completed_at", "") or ""),
        )
    else:
        current_action = "Waiting for first run"

    seen = 0
    net_new = 0
    errors = 0

    if latest_run:
        details = latest_run.get("details", {}) or {}
        seen = int(latest_run.get("total_seen", 0) or 0)
        net_new = int(details.get("net_new_count", latest_run.get("inserted_count", 0) or 0) or 0)
        errors = int(latest_run.get("error_count", 0) or 0)

    st.markdown(
        """
        <div class="pipeline-ops-card">
            <div class="pipeline-ops-kicker">Pipeline operations</div>
            <div class="pipeline-ops-title">Keep discovery moving without losing track of quality.</div>
            <div class="pipeline-ops-copy">
                This is the quickest read on whether the pipeline is ready, currently busy, or needs a reset before your next run.
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="pipeline-status-grid">
            <div class="pipeline-status-tile">
                <div class="pipeline-status-label">Current state</div>
                <div class="pipeline-status-value">{current_status}</div>
            </div>
            <div class="pipeline-status-tile">
                <div class="pipeline-status-label">Run focus</div>
                <div class="pipeline-status-value">{current_action}</div>
            </div>
            <div class="pipeline-status-tile">
                <div class="pipeline-status-label">Last duration</div>
                <div class="pipeline-status-value">{elapsed}</div>
            </div>
            <div class="pipeline-status-tile">
                <div class="pipeline-status-label">Last run health</div>
                <div class="pipeline-status-value">{net_new} net new / {errors} errors</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if busy:
        st.info(f"Working: {current_action} | Elapsed: {elapsed}")
        if elapsed >= "00:05:00":
            st.warning("This run is taking longer than usual. If the UI appears stuck after a while, you can use Reset Run State below.")
        if st.button("Reset Run State", key="reset_pipeline_run_state_ops"):
            st.session_state["pipeline_run_started_at"] = ""
            stop_busy()
            clear_action("pipeline")
            st.rerun()
    else:
        st.caption(f"Latest processed URLs: {seen}")

    st.markdown("</div>", unsafe_allow_html=True)


def _render_first_run_pipeline_guidance() -> None:
    if not _is_first_run_pipeline_state():
        return

    _render_section_shell(
        "First run",
        "Start with one simple run",
        "You do not need to configure every option before using the app. A small first run is the fastest way to confirm that search, scoring, and cleanup all feel right.",
        compact=True,
    )
    st.markdown(
        '<div class="pipeline-cta-strip">'
        '<div class="pipeline-cta-tile">'
        '<div class="pipeline-cta-label">Recommended</div>'
        '<div class="pipeline-cta-title">Run Find and Add Jobs</div>'
        '<div class="pipeline-cta-copy">Use your current run inputs and let the app discover, score, and add a small batch of jobs.</div>'
        '</div>'
        '<div class="pipeline-cta-tile">'
        '<div class="pipeline-cta-label">Alternative</div>'
        '<div class="pipeline-cta-title">Paste a few known job links</div>'
        '<div class="pipeline-cta-copy">Use manual import when you want to test the pipeline against specific postings first.</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Go to Run Jobs", key="pipeline_first_run_go_to_run_jobs", use_container_width=True):
            _navigate_pipeline_section("Run Jobs")
    with c2:
        if st.button("Go to Research", key="pipeline_first_run_go_to_research", use_container_width=True):
            _navigate_pipeline_section("Research")
    _close_section_shell()


def _render_readiness_card() -> None:
    readiness = get_readiness_summary()
    capability_tiles = readiness.get("capabilities", []) or []
    setup_snapshot = str(readiness.get("setup_snapshot", "") or "").strip()
    note = str(readiness.get("note", "") or "").strip()
    next_step = str(readiness.get("next_step", "") or "").strip()

    def _render_tile(tile: dict[str, object]) -> str:
        ready = bool(tile.get("ready", False))
        status_class = "ready" if ready else "warning"
        label = html.escape(str(tile.get("label", "") or ""))
        value = html.escape(str(tile.get("value", "") or ""))
        detail = html.escape(str(tile.get("detail", "") or ""))
        return (
            '<div class="pipeline-readiness-tile">'
            f'<div class="pipeline-readiness-label">{label}</div>'
            f'<div class="pipeline-readiness-value {status_class}">{value}</div>'
            f'<div class="pipeline-readiness-detail">{detail}</div>'
            '</div>'
        )

    _render_section_shell(
        "Readiness",
        "What is ready right now",
        "This is the minimum setup view. It answers whether discovery AI, scoring AI, and cover letters are available without making you interpret a longer setup checklist.",
        compact=True,
    )

    if capability_tiles:
        rendered_capabilities = [_render_tile(tile) for tile in capability_tiles]
        st.markdown(
            f'<div class="pipeline-readiness-grid capabilities">{"".join(rendered_capabilities)}</div>',
            unsafe_allow_html=True,
        )

    if note:
        st.markdown(f'<div class="pipeline-compact-note">{html.escape(note)}</div>', unsafe_allow_html=True)
    if setup_snapshot:
        st.caption(setup_snapshot)
    if next_step:
        st.info(next_step)

    _close_section_shell()


def _render_run_inputs() -> None:
    settings = load_settings()

    _render_section_shell(
        "Run inputs",
        "Tune what discovery looks for",
        "Use this only when you want to change the shape of the search. If the current settings already look right, you can skip this and run jobs immediately.",
        compact=True,
        step="1",
    )

    with st.form("pipeline_run_inputs_form"):
        c1, c2 = st.columns(2)

        with c1:
            target_titles = st.text_area(
                "Target Titles",
                value=settings.get("target_titles", ""),
                height=100,
                help="Comma-separated values",
            )

            preferred_locations = st.text_area(
                "Preferred Locations",
                value=settings.get("preferred_locations", ""),
                height=100,
                help="One location per line. Examples:\nDallas, TX\nMiami, FL\nLondon, UK\nUse full structured entries instead of comma-separated fragments.",
            )

            preferred_job_levels = st.multiselect(
                "Preferred Job Levels",
                options=JOB_LEVEL_OPTIONS,
                default=parse_preferred_job_levels(settings.get("preferred_job_levels", "")),
                help="AI scoring will penalize jobs whose title level falls below the levels you select here.",
            )

            include_keywords = st.text_area(
                "Include Keywords",
                value=settings.get("include_keywords", ""),
                height=100,
                help="Comma-separated values",
            )

        with c2:
            exclude_keywords = st.text_area(
                "Exclude Keywords",
                value=settings.get("exclude_keywords", ""),
                height=100,
                help="Comma-separated values",
            )

            remote_only = st.toggle(
                "Remote Only",
                value=_str_to_bool(settings.get("remote_only", "true"), default=True),
                help="Include only roles that appear remote-friendly.",
            )

            st.caption("Minimum Compensation is not shown here yet because it is not currently a primary live run control in this workflow.")

        save_run_inputs = st.form_submit_button("Save Run Inputs", type="primary", use_container_width=False)

        if save_run_inputs:
            save_settings(
                {
                    "target_titles": target_titles,
                    "preferred_locations": preferred_locations,
                    "preferred_job_levels": serialize_preferred_job_levels(preferred_job_levels),
                    "include_keywords": include_keywords,
                    "exclude_keywords": exclude_keywords,
                    "remote_only": "true" if remote_only else "false",
                }
            )
            st.success("Run inputs saved.")
            st.rerun()

    _close_section_shell()


def _render_action_deck() -> None:
    busy = app_is_busy()
    use_ai_title_expansion = bool(st.session_state.get("pipeline_use_ai_title_expansion", True))
    use_ai_scoring = bool(st.session_state.get("pipeline_use_ai_scoring", True))
    _render_section_shell(
        "Recommended path",
        "Find and add jobs in one pass",
        "This is the normal workflow. The app discovers links, validates them, scores accepted jobs, and adds the strongest matches to New Roles.",
        compact=True,
        step="2",
    )
    st.toggle(
        "Use AI title expansion in this run",
        key="pipeline_use_ai_title_expansion",
        disabled=busy,
        help="When on, discovery may use OpenAI to suggest closely related title variants for search coverage.",
    )
    st.toggle(
        "Use AI scoring and scrub in this run",
        key="pipeline_use_ai_scoring",
        disabled=busy,
        help="When on, accepted jobs may run through AI scoring and the AI scrub pass before they are saved.",
    )

    _render_ai_button_chip()
    if st.button("Find and Add Jobs", type="primary", use_container_width=True, disabled=busy, key="pipeline_primary_run"):
        st.session_state["pipeline_run_started_at"] = datetime.now().isoformat()
        queue_action(
            "pipeline",
            "discover_and_ingest",
            payload={
                "use_ai_title_expansion": use_ai_title_expansion,
                "use_ai_scoring": use_ai_scoring,
            },
            label="Find and Add Jobs",
        )
        st.rerun()

    st.markdown(
        '<div class="pipeline-secondary-actions-note">Default path for most runs. Best for normal day-to-day discovery.</div>',
        unsafe_allow_html=True,
    )

    _render_ai_button_chip()
    if st.button("Find Job Links Only", use_container_width=True, disabled=busy, key="pipeline_discover_only"):
        st.session_state["pipeline_run_started_at"] = datetime.now().isoformat()
        queue_action(
            "pipeline",
            "discover_only",
            payload={"use_ai_title_expansion": use_ai_title_expansion},
            label="Find Job Links Only",
        )
        st.rerun()

    _close_section_shell()


def _render_action_deck_manual_only() -> None:
    busy = app_is_busy()
    manual_urls = st.session_state.get("pipeline_manual_urls", "")
    use_ai_scoring = bool(st.session_state.get("pipeline_use_ai_scoring", True))

    top_left, top_right = st.columns([1.15, 1])

    with top_left:
        st.text_area(
            "Paste job links",
            key="pipeline_manual_urls",
            height=170,
            placeholder="Paste one job URL per line",
        )

        _render_ai_button_chip()
        if st.button("Add Pasted Job Links", use_container_width=True, disabled=busy, key="pipeline_ingest_pasted"):
            st.session_state["pipeline_run_started_at"] = datetime.now().isoformat()
            queue_action(
                "pipeline",
                "ingest_pasted",
                payload={
                    "manual_urls": manual_urls,
                    "use_ai_scoring": use_ai_scoring,
                },
                label="Add Pasted Job Links",
            )
            st.rerun()

    with top_right:
        st.markdown(
            '<div class="pipeline-card-copy">Use these when you already have links or when older jobs need their Fit Score and AI Recommendation refreshed under the latest scoring rules.</div>',
            unsafe_allow_html=True,
        )

        _render_ai_button_chip()
        if st.button("Add Saved Job Links", use_container_width=True, disabled=busy, key="pipeline_ingest_saved"):
            st.session_state["pipeline_run_started_at"] = datetime.now().isoformat()
            queue_action(
                "pipeline",
                "ingest_saved",
                payload={"use_ai_scoring": use_ai_scoring},
                label="Add Saved Job Links",
            )
            st.rerun()

        rescore_left, rescore_right = st.columns(2)
        with rescore_left:
            selected_rescore_label = st.selectbox(
                "Rescore Range",
                options=[label for label, _ in RESCORE_LIMIT_OPTIONS],
                index=1,
                disabled=busy,
                key="pipeline_rescore_limit",
                help="Use a smaller batch for faster maintenance runs. Choose All only when you want to refresh the full backlog.",
            )
        selected_rescore_limit = dict(RESCORE_LIMIT_OPTIONS).get(selected_rescore_label, 50)

        with rescore_right:
            selected_stale_label = st.selectbox(
                "Rescore Age",
                options=[label for label, _ in RESCORE_STALE_OPTIONS],
                index=1,
                disabled=busy,
                key="pipeline_rescore_stale_age",
                help="Use this to avoid spending AI calls on jobs that were refreshed recently.",
            )
        selected_stale_days = dict(RESCORE_STALE_OPTIONS).get(selected_stale_label, 7)

        matching_jobs = count_jobs_for_rescoring(stale_days=selected_stale_days or None)
        selected_jobs = matching_jobs if selected_rescore_limit == 0 else min(matching_jobs, selected_rescore_limit)
        st.caption(
            f"Current rescore policy matches {matching_jobs} jobs. "
            f"This run will process {selected_jobs}."
        )

        _render_ai_button_chip()
        if st.button("Rescore Existing Jobs", use_container_width=True, disabled=busy, key="pipeline_rescore_existing"):
            st.session_state["pipeline_run_started_at"] = datetime.now().isoformat()
            queue_action(
                "pipeline",
                "rescore_existing_jobs",
                payload={"limit": selected_rescore_limit, "stale_days": selected_stale_days},
                label=f"Rescore Existing Jobs ({selected_rescore_label}, {selected_stale_label})",
            )
            st.rerun()


def _render_run_diagnostics_card() -> None:
    last_result = st.session_state.get("pipeline_last_result")
    if not last_result:
        return

    diagnostics = _build_diagnostics_from_last_result()
    discovery_lines = diagnostics.get("discovery_lines", [])
    skip_lines = diagnostics.get("skip_lines", [])
    takeaway = diagnostics.get("takeaway", "")

    if not discovery_lines and not skip_lines and not takeaway:
        return

    _render_section_shell(
        "Diagnostics",
        "Why the latest run underperformed",
        "Use this when a run finishes but produces fewer useful jobs than you expected. It surfaces the biggest blockers without making you read the full raw log first.",
        compact=True,
    )

    if takeaway:
        st.markdown(f'<div class="pipeline-takeaway">{takeaway}</div>', unsafe_allow_html=True)

    if discovery_lines:
        st.markdown("**Top discovery drop reasons**")
        for line in discovery_lines:
            st.markdown(f'<div class="pipeline-diagnostic-line">{line}</div>', unsafe_allow_html=True)

    if skip_lines:
        st.markdown("**Top post-parse skip reasons**")
        for line in skip_lines:
            st.markdown(f'<div class="pipeline-diagnostic-line">{line}</div>', unsafe_allow_html=True)

    _close_section_shell()


def _render_last_result_card() -> None:
    last_result = st.session_state.get("pipeline_last_result")
    if not last_result:
        return

    output_text = str(last_result.get("output", "") or "")
    next_step_message = ""
    status = str(last_result.get("status", "") or "").strip().lower()

    if status == "completed":
        if "Rescore summary:" in output_text:
            next_step_message = (
                "Next step: review New Roles and spot-check AI Fit Detail on a few jobs that changed the most."
            )
        elif "Validation + ingestion complete." in output_text:
            next_step_message = (
                "Next step: go to New Roles to review the new matches, then generate a cover letter or mark the strongest ones as applied."
            )
        elif "Job link discovery complete" in output_text:
            next_step_message = (
                "Next step: import the saved links, or open Search Summary and Fallback Search Links if discovery felt too light."
            )

    _render_section_shell(
        "Last result",
        "Review the most recent pipeline output",
        "This is the detailed run log for the last action you triggered. Use it when you want the exact summary, skips, and parser details.",
        compact=True,
    )
    if next_step_message:
        st.info(next_step_message)
    with st.expander("Open last result", expanded=False):
        _render_result(last_result)
    _close_section_shell()


def _render_last_run_monitor() -> None:
    runs = get_recent_ingestion_runs(limit=1)
    if not runs:
        return

    run = runs[0]
    details = run.get("details", {}) if isinstance(run.get("details", {}), dict) else {}

    run_id = run.get("id", "")
    started_at = str(run.get("started_at", "") or "")
    completed_at = str(run.get("completed_at", "") or "")
    status = str(run.get("status", "") or "Unknown")
    ingest_duration = _format_run_duration(started_at, completed_at)

    total_seen = run.get("total_seen", 0)
    inserted_count = run.get("inserted_count", 0)
    updated_count = run.get("updated_count", 0)
    error_count = run.get("error_count", 0)

    net_new_count = details.get("net_new_count", inserted_count) if isinstance(details, dict) else inserted_count
    rediscovered_count = details.get("rediscovered_count", 0) if isinstance(details, dict) else 0
    duplicate_in_run_count = details.get("duplicate_in_run_count", 0) if isinstance(details, dict) else 0

    source_yield_top = details.get("source_yield_top", []) if isinstance(details, dict) else []
    source_dominance = details.get("source_dominance", {}) if isinstance(details, dict) else {}

    _render_section_shell(
        "Monitor",
        "Key metrics from the latest completed run",
        "Use this for the fast metric read: total seen, net new, rediscovered roles, errors, and whether one source dominated the run.",
        compact=True,
    )

    top1, top2, top3 = st.columns(3)
    top1.metric("Run ID", run_id if run_id != "" else "Unknown")
    top2.metric("Status", _humanize_pipeline_status(status))
    top3.metric("Duration", ingest_duration)

    mid1, mid2, mid3, mid4 = st.columns(4)
    mid1.metric("Total Seen", total_seen)
    mid2.metric("Inserted", inserted_count)
    mid3.metric("Updated", updated_count)
    mid4.metric("Errors", error_count)

    low1, low2, low3 = st.columns(3)
    low1.metric("Net New", net_new_count)
    low2.metric("Rediscovered", rediscovered_count)
    low3.metric("Duplicate In Run", duplicate_in_run_count)

    st.caption(f"Ingest started: {started_at or 'Unknown'} | Ingest completed: {completed_at or 'Unknown'}")

    if source_dominance.get("flag"):
        st.warning(f"Dominance warning: {source_dominance.get('reason', '')}")
    elif source_yield_top:
        first = source_yield_top[0]
        top_source_root = str(first.get("source_root", "") or "")
        top_source_jobs = int(first.get("job_count", 0) or 0)
        if top_source_root:
            st.caption(f"Top source this run: {top_source_root} ({top_source_jobs} jobs)")

    if source_yield_top:
        with st.expander("Top sources this run", expanded=False):
            for row in source_yield_top[:5]:
                ats_type = str(row.get("ats_type", "Unknown") or "Unknown")
                source_root = str(row.get("source_root", "unknown") or "unknown")
                job_count = int(row.get("job_count", 0) or 0)
                st.write(f"- {ats_type} | {source_root} | {job_count} jobs")

    _close_section_shell()


def _render_pipeline_overview_tab() -> None:
    _render_subpage_intro(
        "Overview",
        "Start here for the shortest path to a healthy run",
        "This page is the calm summary view. Check readiness, confirm the pipeline is in a good state, and then jump into Run Jobs or Results depending on what you need next.",
    )
    st.markdown(
        '<div class="pipeline-cta-strip">'
        '<div class="pipeline-cta-tile">'
        '<div class="pipeline-cta-label">Primary next step</div>'
        '<div class="pipeline-cta-title">Run Jobs</div>'
        '<div class="pipeline-cta-copy">Use this when you are ready to discover new roles, import links, or refresh existing jobs.</div>'
        '</div>'
        '<div class="pipeline-cta-tile">'
        '<div class="pipeline-cta-label">If you already ran something</div>'
        '<div class="pipeline-cta-title">Results</div>'
        '<div class="pipeline-cta-copy">Use this when you want to understand what happened in the latest run and what to do next.</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Go to Run Jobs", key="pipeline_overview_to_run_jobs", type="primary", use_container_width=True):
            _navigate_pipeline_section("Run Jobs")
    with c2:
        if st.button("Go to Results", key="pipeline_overview_to_results", use_container_width=True):
            _navigate_pipeline_section("Results")

    left, right = st.columns([1.15, 1])
    with left:
        _render_pipeline_operations_card()
    with right:
        _render_readiness_card()
    _render_first_run_pipeline_guidance()


def _render_pipeline_run_jobs_tab() -> None:
    _render_subpage_intro(
        "Run jobs",
        "Choose one action and keep the setup nearby",
        "This page is for doing work, not reading logs. Set the run inputs first, use the recommended path for normal discovery, and use manual import or maintenance only when needed.",
    )
    primary_left, primary_right = st.columns([1.15, 1])
    with primary_left:
        _render_run_inputs()
    with primary_right:
        _render_action_deck()

    _render_section_shell(
        "Manual import",
        "Seed specific jobs or bring saved links into the app",
        "Use this section when you want to test exact postings, import links you already discovered, or run maintenance on existing jobs. This is secondary to the main discovery flow, but it should stay visible.",
        compact=True,
        step="3",
    )
    _render_action_deck_manual_only()
    _close_section_shell()


def _render_pipeline_results_tab() -> None:
    _render_subpage_intro(
        "Results",
        "Review outcomes before changing the workflow",
        "Start with the next-step guidance, then look at diagnostics only if the run underperformed or the results felt off.",
    )
    _render_last_result_card()
    left, right = st.columns([1.05, 0.95])
    with left:
        _render_run_diagnostics_card()
    with right:
        _render_last_run_monitor()


def _render_pipeline_research_tab() -> None:
    _render_subpage_intro(
        "Research",
        "Use this page only when you need deeper context",
        "These tools help you inspect generated queries, source quality, recent history, and manual fallback options. They are helpful, but not required for normal day-to-day use.",
    )

    top_left, top_right = st.columns(2)
    with top_left:
        _render_section_shell(
            "Search planning",
            "Preview what discovery is going to search",
            "Use this when you want to sanity-check the generated query set before or after a run.",
            compact=True,
        )
        _render_search_summary()
        _close_section_shell()

    with top_right:
        _render_section_shell(
            "Fallback",
            "Use direct searches when discovery feels light",
            "This is the manual backup plan when you want to inspect Google results yourself.",
            compact=True,
        )
        _render_google_search_links()
        _close_section_shell()

    bottom_left, bottom_right = st.columns(2)
    with bottom_left:
        _render_section_shell(
            "Sources",
            "See what domains and ATS roots the app already trusts",
            "Use this when you want more confidence in where jobs are coming from.",
            compact=True,
        )
        _render_source_registry_visibility()
        _close_section_shell()

    with bottom_right:
        _render_section_shell(
            "History",
            "Look back at recent ingestion runs",
            "Use this when you want to compare run quality over time or confirm the source mix from recent imports.",
            compact=True,
        )
        _render_recent_runs()
        _close_section_shell()


def render_pipeline() -> None:
    _process_pending_action_before_render()
    _inject_pipeline_css()

    st.subheader("Pipeline")
    _render_flash()
    initialize_nav_state("pipeline_subnav_selection", "Overview")
    st.caption("Use the subpages below to move between readiness, active runs, recent results, and deeper research tools.")

    selected_section = render_button_nav(
        options=PIPELINE_NAV_OPTIONS,
        state_key="pipeline_subnav_selection",
        key_prefix="pipeline_subnav",
        selected_button_type="tertiary",
    )
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

    if selected_section == "Overview":
        _render_pipeline_overview_tab()
    elif selected_section == "Run Jobs":
        _render_pipeline_run_jobs_tab()
    elif selected_section == "Results":
        _render_pipeline_results_tab()
    else:
        _render_pipeline_research_tab()

    _advance_pending_action_after_render()
