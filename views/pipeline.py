from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st

from config import JOB_URLS_FILE
from services.ingestion import get_recent_ingestion_runs
from services.pipeline_runtime import (
    build_search_preview,
    discover_and_ingest,
    discover_job_links,
    ingest_pasted_urls,
    ingest_urls_from_file,
)
from services.status import get_system_status
from services.ui_busy import app_is_busy, clear_action, get_action, move_action_to_execute, queue_action, stop_busy


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
    status = get_system_status()
    jobs_total = str(status.get("jobs_total", "0")).strip()
    last_import_at = str(status.get("last_import_at", "—")).strip()
    return jobs_total == "0" and last_import_at == "—"


def _render_first_run_pipeline_guidance() -> None:
    if not _is_first_run_pipeline_state():
        return

    st.info(
        """
No jobs have been added yet.

A good first step is:
1. Add your search preferences in Settings
2. Review the search summary below
3. Click **Find and Add Jobs**
4. Or paste a few job URLs manually to seed your list
        """
    )


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

    changed_count = inserted_count + updated_count

    if changed_count > 0:
        parts = []
        if inserted_count > 0:
            parts.append(f"{inserted_count} added")
        if updated_count > 0:
            parts.append(f"{updated_count} updated")
        return "success", f"✓ Job run complete: {', '.join(parts)}"

    if seen_urls == 0:
        return "warning", "No job URLs were discovered. Try the fallback search links below or broaden your criteria."

    if accepted_jobs == 0 and skipped_count > 0:
        return "warning", f"{seen_urls} URLs were found, but none matched your current Settings filters."

    if accepted_jobs > 0 and changed_count == 0:
        if error_count > 0:
            return "warning", f"{seen_urls} URLs were reviewed, but no jobs were added. {error_count} processing errors occurred."
        return "warning", f"{seen_urls} URLs were reviewed, but no new jobs were added."

    if error_count > 0:
        return "warning", f"Run completed with {error_count} processing errors and no added jobs."

    return "warning", "Run completed, but no jobs were added."


def _build_ingest_flash(result: dict, source_label: str) -> tuple[str, str]:
    summary = result.get("summary", {}) or {}
    inserted_count = int(summary.get("inserted_count", 0) or 0)
    updated_count = int(summary.get("updated_count", 0) or 0)
    seen_urls = int(result.get("seen_urls", 0) or 0)
    accepted_jobs = int(result.get("accepted_jobs", 0) or 0)
    skipped_count = int(result.get("skipped_count", 0) or 0)
    error_count = int(result.get("error_count", 0) or 0)

    changed_count = inserted_count + updated_count

    if changed_count > 0:
        parts = []
        if inserted_count > 0:
            parts.append(f"{inserted_count} added")
        if updated_count > 0:
            parts.append(f"{updated_count} updated")
        return "success", f"✓ {source_label} complete: {', '.join(parts)}"

    if seen_urls == 0:
        return "warning", f"No job URLs were available for {source_label.lower()}."

    if accepted_jobs == 0 and skipped_count > 0:
        return "warning", f"{seen_urls} URLs were reviewed for {source_label.lower()}, but none matched your current Settings filters."

    if error_count > 0:
        return "warning", f"{source_label} completed with {error_count} processing errors and no added jobs."

    return "warning", f"{source_label} completed, but no new jobs were added."


def _build_discover_only_flash(result: dict) -> tuple[str, str]:
    url_count = int(result.get("url_count", 0) or 0)

    if url_count > 0:
        return "success", f"✓ Job link discovery complete: {url_count} URLs found"

    return "warning", "No job URLs were discovered."


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
                result = discover_and_ingest()
                st.session_state["pipeline_last_result"] = result
                level, message = _build_discover_and_ingest_flash(result)
                _set_flash(level, message)
                st.cache_data.clear()

            elif action_type == "ingest_pasted":
                result = ingest_pasted_urls(payload.get("manual_urls", ""))
                st.session_state["pipeline_last_result"] = result
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
                    result = ingest_urls_from_file(JOB_URLS_FILE)
                    st.session_state["pipeline_last_result"] = result
                    level, message = _build_ingest_flash(result, "Saved job link import")
                    _set_flash(level, message)
                    st.cache_data.clear()

            elif action_type == "discover_only":
                result = discover_job_links()
                st.session_state["pipeline_last_result"] = result
                level, message = _build_discover_only_flash(result)
                _set_flash(level, message)

    except Exception as exc:
        _set_flash("error", f"Pipeline action failed: {exc}")
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

    st.markdown("### What I'm searching for")
    st.caption("This is the search setup the app will use before validating and importing jobs.")

    if not plan:
        st.info("No search settings are saved yet. Go to Settings and add at least a target title.")
        return

    for item in plan:
        st.markdown(f"- {item}")

    st.caption("Search sources: Greenhouse, Lever, and broader web job search when available.")

    with st.expander("Show technical search details"):
        if queries:
            st.markdown("**Generated discovery queries**")
            for query in queries:
                st.code(query, language=None)
        else:
            st.caption("No generated discovery queries available.")


def _render_provider_summary() -> None:
    last_result = st.session_state.get("pipeline_last_result")
    if not last_result:
        return

    discovery = last_result.get("discovery", last_result) or {}
    providers = discovery.get("providers", {}) or {}

    greenhouse_count = int(providers.get("greenhouse", 0) or 0)
    lever_count = int(providers.get("lever", 0) or 0)
    search_count = int(providers.get("search", 0) or 0)
    total_count = int(discovery.get("url_count", 0) or 0)

    if not providers and total_count == 0:
        return

    st.markdown("### Discovery results")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Greenhouse", greenhouse_count)
    c2.metric("Lever", lever_count)
    c3.metric("Web Search", search_count)
    c4.metric("Total URLs", total_count)


def _manual_search_link(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


def _render_manual_fallback_links() -> None:
    last_result = st.session_state.get("pipeline_last_result")
    if not last_result:
        return

    discovery = last_result.get("discovery", last_result) or {}
    total_count = int(discovery.get("url_count", 0) or 0)

    if total_count > 0:
        return

    preview = build_search_preview()
    queries = preview.get("queries", []) or []

    if not queries:
        return

    st.markdown("### Manual fallback searches")
    st.caption("Live discovery found no URLs this time. These links run broader web searches you can open manually.")

    for query in queries[:8]:
        st.markdown(f"- [{query}]({_manual_search_link(query)})")


def _render_last_run_details() -> None:
    last_result = st.session_state.get("pipeline_last_result")
    if not last_result:
        return

    with st.expander("Show technical run details"):
        _render_result(last_result)


def render_run_history() -> None:
    st.markdown("### Recent Job Runs")
    runs = get_recent_ingestion_runs(limit=12)

    if not runs:
        st.info("No job runs yet.")
        return

    for run in runs:
        st.markdown(
            f"""
            <div class="job-card">
                <div class="job-title">{run['run_type']} | {run['source_name']}</div>
                <div class="meta-row">
                    <span class="meta-pill fit">Status: {run['status']}</span>
                    <span class="meta-pill location">Seen: {run['total_seen']}</span>
                    <span class="meta-pill comp">Inserted: {run['inserted_count']}</span>
                    <span class="meta-pill comp">Updated: {run['updated_count']}</span>
                    <span class="meta-pill comp">Skipped Removed: {run['skipped_removed_count']}</span>
                    <span class="meta-pill comp">Errors: {run['error_count']}</span>
                </div>
                <div class="hero-subtle">Started: {run['started_at']} | Completed: {run['completed_at'] or '—'} | Detail: {run['source_detail']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_pipeline() -> None:
    _process_pending_action_before_render()

    st.subheader("Pipeline")
    _render_first_run_pipeline_guidance()
    _render_flash()
    _render_search_summary()
    _render_provider_summary()
    _render_manual_fallback_links()

    st.markdown("### Find and Add Jobs")
    st.caption("Searches for job links, validates them, and adds matching roles to your New Roles list.")

    if st.button("Find and Add Jobs", use_container_width=True, type="primary", disabled=app_is_busy()):
        queue_action("pipeline", "discover_and_ingest", {}, "Finding and adding jobs")
        st.rerun()

    st.markdown("---")
    st.markdown("### Add Pasted Job Links")
    st.caption("Paste one or more job links and add them directly into the app.")

    manual_urls = st.text_area(
        "Paste one job URL per line",
        height=160,
        key="pipeline_manual_urls",
        disabled=app_is_busy(),
    )

    if st.button("Add Pasted Job Links", use_container_width=True, type="secondary", disabled=app_is_busy()):
        if not manual_urls.strip():
            st.warning("Paste at least one URL first.")
        else:
            queue_action("pipeline", "ingest_pasted", {"manual_urls": manual_urls}, "Adding pasted job links")
            st.rerun()

    with st.expander("Advanced"):
        st.markdown("### Saved Job Links")
        st.caption(f"Uses the saved URL file at: {JOB_URLS_FILE}")

        if _job_urls_file_exists():
            st.success("Saved job link file found.")
        else:
            st.info("No saved job link file exists yet. Use Find Job Links Only or Find and Add Jobs first.")

        adv1, adv2 = st.columns(2)

        with adv1:
            if st.button("Add Saved Job Links", use_container_width=True, type="secondary", disabled=app_is_busy()):
                if not _job_urls_file_exists():
                    _set_flash("warning", "No saved job links file exists yet. Run discovery first or paste job links.")
                    st.rerun()
                queue_action("pipeline", "ingest_saved", {}, "Adding saved job links")
                st.rerun()

        with adv2:
            if st.button("Find Job Links Only", use_container_width=True, type="secondary", disabled=app_is_busy()):
                queue_action("pipeline", "discover_only", {}, "Finding job links")
                st.rerun()

    _render_last_run_details()

    st.markdown("---")
    render_run_history()

    _advance_pending_action_after_render()
