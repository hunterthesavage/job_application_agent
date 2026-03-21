import streamlit as st

from config import JOB_URLS_FILE
from services.ingestion import get_recent_ingestion_runs
from services.pipeline_runtime import (
    discover_and_ingest,
    discover_job_links,
    ingest_pasted_urls,
    ingest_urls_from_file,
)
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
                _set_flash("success", "✓ Jobs found and added")
                st.cache_data.clear()

            elif action_type == "ingest_pasted":
                result = ingest_pasted_urls(payload.get("manual_urls", ""))
                st.session_state["pipeline_last_result"] = result
                _set_flash("success", "✓ Pasted job links added")
                st.cache_data.clear()

            elif action_type == "ingest_saved":
                result = ingest_urls_from_file(JOB_URLS_FILE)
                st.session_state["pipeline_last_result"] = result
                _set_flash("success", "✓ Saved job links added")
                st.cache_data.clear()

            elif action_type == "discover_only":
                result = discover_job_links()
                st.session_state["pipeline_last_result"] = result
                _set_flash("success", "✓ Job links found and saved")

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

    _render_flash()

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
        height=180,
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

        adv1, adv2 = st.columns(2)

        with adv1:
            if st.button("Add Saved Job Links", use_container_width=True, type="secondary", disabled=app_is_busy()):
                queue_action("pipeline", "ingest_saved", {}, "Adding saved job links")
                st.rerun()

        with adv2:
            if st.button("Find Job Links Only", use_container_width=True, type="secondary", disabled=app_is_busy()):
                queue_action("pipeline", "discover_only", {}, "Finding job links")
                st.rerun()

    last_result = st.session_state.get("pipeline_last_result")
    if last_result:
        st.markdown("---")
        _render_result(last_result)

    st.markdown("---")
    render_run_history()

    _advance_pending_action_after_render()
