from __future__ import annotations

import html
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import streamlit as st

from config import JOB_URLS_FILE, LATEST_PIPELINE_LOG_PATH
from services.ingestion import get_recent_ingestion_runs, get_source_registry_summary
from services.job_levels import (
    JOB_LEVEL_OPTIONS,
    parse_preferred_job_levels,
    serialize_preferred_job_levels,
)
from services.openai_key import has_openai_api_key
from services.openai_title_suggestions import (
    suggest_run_input_refinements_with_openai,
    suggest_title_groups_with_openai,
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
from services.settings import load_settings, save_settings
from services.title_groups import (
    MAX_MAIN_TITLES,
    MAX_SUBTITLE_VARIANTS,
    build_effective_title_list,
    build_effective_titles_text,
    build_search_titles_text,
    create_empty_title_group,
    load_title_groups_from_settings,
    merge_ai_variants_into_groups,
    normalize_title_groups,
    serialize_title_groups,
)
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
    "Find Roles",
    "Search Results",
]

SEARCH_STRATEGY_OPTIONS = {
    "Broader Search": "broad_recall",
    "Standard": "balanced",
}


def _append_comma_separated(existing: str, additions: list[str]) -> str:
    current = [part.strip() for part in str(existing or "").split(",") if part.strip()]
    seen = {part.casefold() for part in current}

    for addition in additions:
        clean = str(addition or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        current.append(clean)
        seen.add(key)

    return ", ".join(current)


def _clear_pipeline_title_suggestions() -> None:
    st.session_state["pipeline_title_suggestions_notes"] = ""
    st.session_state["pipeline_run_input_summary"] = {}

def _normalize_location_lines(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    if "\n" in text:
        parts = text.splitlines()
    elif ";" in text:
        parts = text.split(";")
    else:
        parts = [text]

    results: list[str] = []
    seen: set[str] = set()
    for part in parts:
        clean = " ".join(str(part or "").strip().split())
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(clean)
    return results


def _append_unique_lines(existing: list[str], additions: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()

    for raw in [*existing, *additions]:
        clean = " ".join(str(raw or "").strip().split())
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(clean)

    return results


def _title_group_variant_label(variant: dict[str, Any]) -> str:
    title = str(variant.get("title", "") or "").strip()
    if not title:
        return ""
    source = str(variant.get("source", "") or "").strip().lower()
    if source == "ai":
        return f"{title}  [AI]"
    return title


def _summarize_title_groups(groups: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_title_groups(groups)
    effective_titles = build_effective_title_list(normalized)
    generated_variant_count = sum(len(group.get("variants", []) or []) for group in normalized)
    selected_variant_count = sum(
        1
        for group in normalized
        for variant in (group.get("variants", []) or [])
        if bool(variant.get("selected", True))
    )
    return {
        "title_groups": normalized,
        "titles": effective_titles,
        "main_title_count": len(normalized),
        "generated_variant_count": generated_variant_count,
        "selected_variant_count": selected_variant_count,
    }


def _coerce_title_group_editor_state(title_groups: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    coerced: list[dict[str, Any]] = []

    for raw_group in title_groups or []:
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or create_empty_title_group()["id"]).strip()
        main_title = " ".join(str(raw_group.get("main_title", "") or "").split())
        variants: list[dict[str, Any]] = []
        for raw_variant in raw_group.get("variants", []) or []:
            if not isinstance(raw_variant, dict):
                continue
            title = " ".join(str(raw_variant.get("title", "") or "").split())
            if not title:
                continue
            variants.append(
                {
                    "title": title,
                    "selected": bool(raw_variant.get("selected", True)),
                    "source": str(raw_variant.get("source", "") or "ai"),
                }
            )
        coerced.append(
            {
                "id": group_id,
                "main_title": main_title,
                "variants": variants,
            }
        )
        if len(coerced) >= MAX_MAIN_TITLES:
            break

    if not coerced:
        coerced = [create_empty_title_group()]

    return coerced


def _collect_pipeline_title_groups_from_widgets(title_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []

    for group in _coerce_title_group_editor_state(title_groups):
        group_id = str(group.get("id", "") or create_empty_title_group()["id"]).strip()
        main_title = " ".join(str(st.session_state.get(f"pipeline_main_title_{group_id}", group.get("main_title", "")) or "").split())
        variants: list[dict[str, Any]] = []
        for variant_index, variant in enumerate(group.get("variants", []) or []):
            if not isinstance(variant, dict):
                continue
            title = " ".join(str(variant.get("title", "") or "").split())
            if not title:
                continue
            selected = bool(
                st.session_state.get(
                    f"pipeline_variant_selected_{group_id}_{variant_index}",
                    bool(variant.get("selected", True)),
                )
            )
            variants.append(
                {
                    "title": title,
                    "selected": selected,
                    "source": str(variant.get("source", "") or "ai"),
                }
            )
        collected.append(
            {
                "id": group_id,
                "main_title": main_title,
                "variants": variants,
            }
        )

    return _coerce_title_group_editor_state(collected)


def _render_pipeline_title_group_editor(title_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_groups = _coerce_title_group_editor_state(title_groups)

    remove_group_id = ""
    updated_groups: list[dict[str, Any]] = []

    for index, group in enumerate(normalized_groups, start=1):
        group_id = str(group.get("id", "") or create_empty_title_group()["id"])
        cols = st.columns([0.82, 0.18], gap="small")
        with cols[0]:
            widget_key = f"pipeline_main_title_{group_id}"
            if widget_key not in st.session_state:
                st.session_state[widget_key] = str(group.get("main_title", "") or "")
            main_title = st.text_input(
                f"Main Title {index}",
                key=widget_key,
                placeholder="Enter a job title to search",
            )
        with cols[1]:
            st.markdown("<div style='height: 1.8rem;'></div>", unsafe_allow_html=True)
            if st.button(
                "Remove",
                key=f"pipeline_remove_title_{group_id}",
                use_container_width=True,
                disabled=len(normalized_groups) <= 1,
            ):
                remove_group_id = group_id

        updated_variants: list[dict[str, Any]] = []
        existing_variants = group.get("variants", []) or []
        if main_title and existing_variants:
            st.caption("Subtitle variants")
        for variant_index, variant in enumerate(existing_variants):
            variant_title = str(variant.get("title", "") or "").strip()
            if not variant_title:
                continue
            selection_key = f"pipeline_variant_selected_{group_id}_{variant_index}"
            if selection_key not in st.session_state:
                st.session_state[selection_key] = bool(variant.get("selected", True))
            selected = st.checkbox(
                _title_group_variant_label(variant),
                key=selection_key,
            )
            updated_variants.append(
                {
                    "title": variant_title,
                    "selected": selected,
                    "source": str(variant.get("source", "") or "ai"),
                }
            )

        updated_groups.append(
            {
                "id": group_id,
                "main_title": main_title,
                "variants": updated_variants,
            }
        )

    if remove_group_id:
        remaining_groups = [group for group in updated_groups if str(group.get("id", "")) != remove_group_id]
        st.session_state["pipeline_title_groups_value"] = _coerce_title_group_editor_state(remaining_groups)
        st.rerun()

    add_disabled = len(updated_groups) >= MAX_MAIN_TITLES
    if st.button(
        "Add Another Title",
        use_container_width=False,
        disabled=add_disabled,
        key="pipeline_add_title_group",
    ):
        st.session_state["pipeline_title_groups_value"] = _coerce_title_group_editor_state(updated_groups + [create_empty_title_group()])
        st.rerun()

    if add_disabled:
        st.caption(f"You can search up to {MAX_MAIN_TITLES} main titles.")
    else:
        st.caption(
            f"Add up to {MAX_MAIN_TITLES} main titles. On save, AI will generate up to {MAX_SUBTITLE_VARIANTS} close subtitle variants per title."
        )

    return _coerce_title_group_editor_state(updated_groups)


def _generate_pipeline_title_groups(
    *,
    title_groups: list[dict[str, Any]],
    preferred_locations: str,
    include_keywords: str,
    include_remote: bool,
) -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    st.session_state["pipeline_title_suggestion_message"] = ""
    _clear_pipeline_title_suggestions()

    normalized_groups = normalize_title_groups(title_groups)
    if not normalized_groups:
        return [], preferred_locations, "", "", _summarize_title_groups([])

    settings = load_settings()
    result = suggest_title_groups_with_openai(
        main_titles=[group.get("main_title", "") for group in normalized_groups],
        profile_summary=str(settings.get("profile_summary", "") or ""),
        resume_text=str(settings.get("resume_text", "") or ""),
        include_keywords=str(include_keywords or "").strip(),
        max_variants_per_title=MAX_SUBTITLE_VARIANTS,
    )

    if result.get("ok"):
        ai_variants_by_main_title = {
            str(group.get("main_title", "") or "").strip(): [
                str(title or "").strip()
                for title in (group.get("variants", []) or [])
                if str(title or "").strip()
            ]
            for group in (result.get("title_groups", []) or [])
            if str(group.get("main_title", "") or "").strip()
        }
        merged_groups = merge_ai_variants_into_groups(normalized_groups, ai_variants_by_main_title)
        summary = _summarize_title_groups(merged_groups)
        title_notes = ""
        if summary["generated_variant_count"]:
            title_notes = "Subtitle variants focus on close abbreviation and level changes while preserving the original role and seniority."
        st.session_state["pipeline_title_suggestions_notes"] = title_notes
        st.session_state["pipeline_run_input_summary"] = summary
        if summary["generated_variant_count"]:
            message = (
                "Run inputs saved. AI generated close subtitle variants for each main title and kept your previous selections where possible."
            )
        else:
            message = "Run inputs saved. AI did not find any close subtitle variants to add."
        location_result = suggest_run_input_refinements_with_openai(
            current_titles=build_effective_titles_text(merged_groups),
            preferred_locations=preferred_locations,
            profile_summary=str(settings.get("profile_summary", "") or ""),
            resume_text=str(settings.get("resume_text", "") or ""),
            include_keywords=str(include_keywords or "").strip(),
            include_remote=include_remote,
            max_titles=1,
            max_locations=6,
        )
        refined_locations = preferred_locations
        location_notes = ""
        if location_result.get("ok"):
            suggested_location_values = _normalize_location_lines(
                "\n".join(str(location or "") for location in (location_result.get("locations", []) or []))
            )
            if suggested_location_values:
                refined_locations = "\n".join(suggested_location_values)
                summary["locations"] = suggested_location_values
                location_notes = "Location lines were normalized into clean search targets."
            if suggested_location_values:
                if summary["generated_variant_count"]:
                    message = "Run inputs saved. AI generated close subtitle variants and normalized your location lines."
                else:
                    message = "Run inputs saved. AI normalized your location lines."
        combined_notes = " ".join(part for part in [title_notes, location_notes] if part).strip()
        return merged_groups, refined_locations, message, combined_notes, summary

    error_text = str(result.get("error", "") or "").strip()
    if error_text:
        message = f"Run inputs saved. Could not generate subtitle variants with AI. {error_text}"
    else:
        message = "Run inputs saved. Could not generate subtitle variants with AI."
    summary = _summarize_title_groups(normalized_groups)
    return normalized_groups, preferred_locations, message, "", summary


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

            .pipeline-ai-updates-box {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
                background: linear-gradient(180deg, rgba(17,24,39,0.94) 0%, rgba(11,16,26,0.98) 100%);
                padding: 0.95rem 1rem;
                max-height: 21rem;
                overflow-y: auto;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
            }

            .pipeline-ai-updates-title {
                font-size: 1rem;
                font-weight: 780;
                color: rgba(255,255,255,0.96);
                margin-bottom: 0.45rem;
            }

            .pipeline-ai-updates-copy {
                font-size: 0.9rem;
                line-height: 1.45;
                color: rgba(255,255,255,0.74);
                margin-bottom: 0.55rem;
            }

            .pipeline-ai-updates-label {
                font-size: 0.8rem;
                font-weight: 760;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: rgba(191,219,254,0.86);
                margin-top: 0.75rem;
                margin-bottom: 0.35rem;
            }

            .pipeline-ai-updates-list {
                margin: 0;
                padding-left: 1.15rem;
                color: rgba(255,255,255,0.88);
            }

            .pipeline-ai-updates-list li {
                margin-bottom: 0.26rem;
                line-height: 1.35;
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


def _render_pipeline_ai_chip() -> None:
    st.markdown(
        '<div class="ai-button-chip-wrap"><span class="ai-button-chip" title="Uses OpenAI">AI</span></div>',
        unsafe_allow_html=True,
    )


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


def _set_run_input_notice(level: str, message: str) -> None:
    st.session_state["pipeline_run_input_notice_level"] = level
    st.session_state["pipeline_run_input_notice_message"] = message


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


def _save_run_inputs_action(payload: dict[str, Any]) -> tuple[str, str]:
    saved_title_groups = normalize_title_groups(payload.get("title_groups", []) or [])
    saved_locations = str(payload.get("preferred_locations", "") or "")
    saved_include_keywords = str(payload.get("include_keywords", "") or "")
    saved_job_levels = payload.get("preferred_job_levels", []) or []
    saved_exclude_keywords = str(payload.get("exclude_keywords", "") or "")
    saved_search_strategy = str(payload.get("search_strategy", "Broader Search") or "Broader Search")
    saved_include_remote = bool(payload.get("include_remote", True))

    final_title_groups = saved_title_groups
    final_locations = saved_locations
    final_message = "Run inputs saved."
    final_notes = ""
    final_summary: dict[str, Any] = _summarize_title_groups(saved_title_groups)
    final_summary["locations"] = _normalize_location_lines(saved_locations)

    if saved_title_groups and has_openai_api_key():
        (
            final_title_groups,
            final_locations,
            final_message,
            final_notes,
            final_summary,
        ) = _generate_pipeline_title_groups(
            title_groups=saved_title_groups,
            preferred_locations=saved_locations,
            include_keywords=saved_include_keywords,
            include_remote=saved_include_remote,
        )
    elif saved_title_groups:
        final_message = "Run inputs saved. Add an OpenAI API key to generate close subtitle variants automatically."

    final_target_titles = build_search_titles_text(final_title_groups)

    save_settings(
        {
            "target_title_groups": serialize_title_groups(final_title_groups),
            "target_titles": final_target_titles,
            "preferred_locations": final_locations,
            "preferred_job_levels": serialize_preferred_job_levels(saved_job_levels),
            "include_keywords": saved_include_keywords,
            "exclude_keywords": saved_exclude_keywords,
            "include_remote": "true" if saved_include_remote else "false",
            "remote_only": "false",
            "search_strategy": SEARCH_STRATEGY_OPTIONS.get(saved_search_strategy, "broad_recall"),
        }
    )
    st.session_state["pipeline_pending_title_groups_value"] = final_title_groups
    st.session_state["pipeline_pending_preferred_locations_value"] = final_locations
    st.session_state["pipeline_title_suggestion_message"] = final_message
    st.session_state["pipeline_title_suggestions_notes"] = final_notes
    st.session_state["pipeline_run_input_summary"] = final_summary

    title_count = len(final_summary.get("titles", []) or [])
    main_title_count = int(final_summary.get("main_title_count", 0) or 0)
    variant_count = int(final_summary.get("generated_variant_count", 0) or 0)
    location_count = len(final_summary.get("locations", []) or [])
    changed_parts: list[str] = []
    if main_title_count:
        changed_parts.append(f"{main_title_count} main titles")
    if variant_count:
        changed_parts.append(f"{variant_count} subtitle variants")
    elif title_count:
        changed_parts.append(f"{title_count} effective titles")
    if location_count:
        changed_parts.append(f"{location_count} location lines saved")

    if changed_parts:
        flash_message = f"✓ Save Run Inputs complete: {', '.join(changed_parts)}"
    else:
        flash_message = "✓ Save Run Inputs complete"

    return "success", flash_message


def _navigate_pipeline_section(section: str) -> None:
    st.session_state["pipeline_subnav_selection"] = section
    st.rerun()


def _navigate_top_section(section: str) -> None:
    st.session_state["top_nav_selection"] = section
    st.rerun()


def _render_subpage_intro(kicker: str, title: str, copy: str) -> None:
    markup = (
        '<div class="pipeline-page-intro">'
        '<div class="pipeline-page-intro-copy">'
        f'<div class="pipeline-page-kicker">{html.escape(kicker)}</div>'
        f'<div class="pipeline-page-title">{html.escape(title)}</div>'
        f'<div class="pipeline-page-copy">{html.escape(copy)}</div>'
        '</div>'
        '</div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


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
    markup = (
        f'<div class="pipeline-section-card{compact_class}">'
        f'<div class="pipeline-section-kicker">{html.escape(kicker)}</div>'
        '<div class="pipeline-section-heading">'
        f'{step_markup}'
        f'<div class="pipeline-section-title">{html.escape(title)}</div>'
        '</div>'
        f'<div class="pipeline-section-copy">{html.escape(copy)}</div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


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


def _render_copy_result_button(output_text: str, *, key: str) -> None:
    text = str(output_text or "")
    if not text:
        return

    status_key = f"pipeline_copy_result_status_{key}"
    button_col, status_col = st.columns([0.18, 0.82])
    with button_col:
        if st.button("Copy", key=f"pipeline_copy_result_button_{key}", use_container_width=True):
            try:
                subprocess.run(
                    ["pbcopy"],
                    input=text,
                    text=True,
                    check=True,
                )
                st.session_state[status_key] = ("success", "Copied")
            except Exception:
                st.session_state[status_key] = ("error", "Copy failed")

    status = st.session_state.get(status_key)
    if not status:
        return

    level, message = status
    with status_col:
        if level == "success":
            st.caption(message)
        else:
            st.caption(message)


def _job_urls_file_exists() -> bool:
    return Path(JOB_URLS_FILE).exists()


def _is_first_run_pipeline_state() -> bool:
    last_result = st.session_state.get("pipeline_last_result")
    latest_run = _get_latest_run()
    return not bool(last_result) and latest_run is None


def _build_discover_and_ingest_flash(result: dict) -> tuple[str, str]:
    discovery = result.get("discovery", {}) or {}
    ingest = result.get("ingest", {}) or {}
    maintenance = result.get("maintenance", {}) if isinstance(result.get("maintenance", {}), dict) else {}

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
    maintenance_changed_count = int(maintenance.get("changed_count", 0) or 0)
    maintenance_refreshed_count = int(maintenance.get("refreshed_count", 0) or 0)

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
        if maintenance_changed_count > 0:
            parts.append(f"{maintenance_changed_count} existing refreshed")
        return "success", f"✓ Find Roles complete: {', '.join(parts)}"

    if maintenance_changed_count > 0 or maintenance_refreshed_count > 0:
        if maintenance_changed_count > 0:
            return "success", f"✓ Find Roles complete: {maintenance_changed_count} existing jobs improved"
        return "success", f"✓ Find Roles complete: {maintenance_refreshed_count} existing jobs refreshed"

    if seen_urls == 0:
        return "warning", "No job URLs were discovered and no existing jobs needed maintenance. Try the fallback search links below or broaden your criteria."

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


def _run_jobs_has_reviewable_results(result: dict) -> bool:
    summary = result.get("ingest", {}).get("summary", {}) if isinstance(result.get("ingest", {}), dict) else {}
    inserted_count = int(summary.get("inserted_count", 0) or 0)
    updated_count = int(summary.get("updated_count", 0) or 0)
    net_new_count = int(summary.get("net_new_count", inserted_count) or 0)
    rediscovered_count = int(summary.get("rediscovered_count", 0) or 0)
    changed_count = inserted_count + updated_count

    return any(value > 0 for value in [changed_count, net_new_count, rediscovered_count])


def _maybe_route_after_run_jobs(result: dict) -> None:
    wizard_redirect = bool(st.session_state.pop("_wizard_first_discovery_redirect", False))
    st.session_state.pop("_wizard_first_discovery_loading", None)

    if _run_jobs_has_reviewable_results(result):
        st.session_state["top_nav_selection"] = "New Roles"
        return

    if wizard_redirect:
        st.session_state["top_nav_selection"] = "Pipeline"
        st.session_state["pipeline_subnav_selection"] = "Search Results"
        st.session_state["_post_wizard_run_message"] = {
            "kind": "warning",
            "text": "Your first search did not add jobs yet. Review Search Results for diagnostics.",
        }


def _process_pending_action_before_render() -> None:
    action = get_action("pipeline")
    if not action or action.get("phase") != "execute":
        return

    try:
        action_type = action.get("type")
        payload = action.get("payload", {})
        label = action.get("label", "Working")

        if action_type == "discover_and_ingest":
            result = discover_and_ingest(
                use_ai_title_expansion=bool(payload.get("use_ai_title_expansion", True)),
                use_ai_scoring=bool(payload.get("use_ai_scoring", True)),
            )
            st.session_state["pipeline_last_result"] = result
            _maybe_route_after_run_jobs(result)
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

        elif action_type == "save_run_inputs":
            level, message = _save_run_inputs_action(payload)
            _set_flash(level, message)
            _set_run_input_notice(
                level,
                str(st.session_state.get("pipeline_title_suggestion_message", "") or "Run inputs saved."),
            )

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


def process_pipeline_action_cycle() -> None:
    _process_pending_action_before_render()
    _advance_pending_action_after_render()


def _render_search_summary(*, show_heading: bool = True) -> None:
    preview = build_search_preview()
    plan = preview.get("plan", [])
    queries = preview.get("queries", [])

    if show_heading:
        st.markdown("### Search Summary")

    if plan:
        for line in plan:
            st.write(f"- {line}")

    if queries:
        with st.expander("Preview generated search queries", expanded=False):
            for query in queries:
                st.code(query, language="text")


def _render_google_search_links(*, show_heading: bool = True) -> None:
    preview = build_search_preview()
    queries = preview.get("queries", [])[:8]

    if not queries:
        return

    if show_heading:
        st.markdown("### Fallback Search Links")
        st.caption("If discovery is light, use these direct Google searches to inspect the market manually.")

    for query in queries:
        encoded = quote_plus(query)
        st.markdown(f"- [Search Google for: {query}](https://www.google.com/search?q={encoded})")


def _render_source_registry_visibility(*, show_heading: bool = True) -> None:
    if show_heading:
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


def _render_recent_runs(*, show_heading: bool = True) -> None:
    if show_heading:
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


def _render_research_health_card() -> None:
    readiness = get_readiness_summary()

    _render_section_shell(
        "App health",
        "Check whether setup or local state is contributing to the problem",
        "Use this when AI features seem off or setup drift might be affecting the run.",
        compact=True,
    )

    note = str(readiness.get("note", "") or "").strip()
    if note:
        st.markdown(f'<div class="pipeline-compact-note">{html.escape(note)}</div>', unsafe_allow_html=True)

    with st.expander("Open app health", expanded=False):
        capability_tiles = readiness.get("capabilities", []) or []
        if capability_tiles:
            rendered = []
            for tile in capability_tiles:
                ready = bool(tile.get("ready", False))
                status_class = "ready" if ready else "warning"
                label = html.escape(str(tile.get("label", "") or ""))
                value = html.escape(str(tile.get("value", "") or ""))
                detail = html.escape(str(tile.get("detail", "") or ""))
                rendered.append(
                    '<div class="pipeline-readiness-tile">'
                    f'<div class="pipeline-readiness-label">{label}</div>'
                    f'<div class="pipeline-readiness-value {status_class}">{value}</div>'
                    f'<div class="pipeline-readiness-detail">{detail}</div>'
                    '</div>'
                )
            st.markdown(
                f'<div class="pipeline-readiness-grid capabilities">{"".join(rendered)}</div>',
                unsafe_allow_html=True,
            )
        st.caption("For backups, full health checks, and reset tools, open Settings -> System Status.")

    _close_section_shell()


def _render_research_recent_history_card() -> None:
    runs = get_recent_ingestion_runs(limit=8)
    latest = runs[0] if runs else None
    latest_status = _humanize_pipeline_status(str((latest or {}).get("status", "") or "Unknown")) if latest else "No runs yet"
    latest_errors = int((latest or {}).get("error_count", 0) or 0) if latest else 0

    _render_section_shell(
        "Recent run history",
        "Check whether this issue is a one-off or a pattern",
        "Use this when you want to compare recent runs before changing discovery or scoring inputs.",
        compact=True,
    )

    if latest:
        st.markdown(
            f'<div class="pipeline-compact-note">Latest run: {html.escape(latest_status)} with {latest_errors} errors. {len(runs)} recent runs available for comparison.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="pipeline-compact-note">No ingestion history yet. Run a small search first, then come back here to compare outcomes over time.</div>',
            unsafe_allow_html=True,
        )

    with st.expander("Open recent run history", expanded=False):
        _render_recent_runs(show_heading=False)

    _close_section_shell()


def _render_research_source_quality_card() -> None:
    try:
        summary = get_source_registry_summary()
    except Exception as exc:
        summary = None
        error_message = str(exc)
    else:
        error_message = ""

    _render_section_shell(
        "Source quality",
        "Check whether noisy or weak sources are distorting results",
        "Use this when results seem too dependent on one ATS or when the source mix feels lower quality than expected.",
        compact=True,
    )

    if summary is None:
        st.markdown(
            f'<div class="pipeline-compact-note">Source quality could not be loaded yet: {html.escape(error_message)}</div>',
            unsafe_allow_html=True,
        )
    else:
        totals = summary.get("totals", {}) or {}
        total_sources = int(totals.get("total_sources", 0) or 0)
        ats_confirmed = int(totals.get("ats_confirmed_sources", 0) or 0)
        st.markdown(
            f'<div class="pipeline-compact-note">{total_sources} known sources tracked, with {ats_confirmed} ATS-confirmed roots currently in the registry.</div>',
            unsafe_allow_html=True,
        )

    with st.expander("Open source quality details", expanded=False):
        _render_source_registry_visibility(show_heading=False)

    _close_section_shell()


def _render_research_search_strategy_card() -> None:
    preview = build_search_preview()
    plan = preview.get("plan", []) or []
    queries = preview.get("queries", []) or []

    _render_section_shell(
        "Search strategy",
        "Check what discovery is actually searching for",
        "Use this when the search feels too narrow, too broad, or just off-target.",
        compact=True,
    )

    st.markdown(
        f'<div class="pipeline-compact-note">{len(plan)} planning notes and {len(queries)} generated queries are ready to inspect.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Open search strategy details", expanded=False):
        _render_search_summary(show_heading=False)
        st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
        _render_google_search_links(show_heading=False)

    _close_section_shell()


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


def _format_duration_seconds(seconds_value: object) -> str:
    try:
        total_seconds = float(str(seconds_value).strip())
    except Exception:
        return "Unknown"
    if total_seconds < 0:
        total_seconds = 0.0
    return f"{total_seconds:.2f}s"


def _get_preferred_run_duration(run: dict | None) -> str:
    if not run or not isinstance(run, dict):
        return "Unknown"

    details = run.get("details", {})
    if isinstance(details, dict):
        pipeline_total_seconds = details.get("pipeline_total_seconds")
        if pipeline_total_seconds not in (None, ""):
            formatted = _format_duration_seconds(pipeline_total_seconds)
            if formatted != "Unknown":
                return formatted

    return _format_run_duration(
        str(run.get("started_at", "") or ""),
        str(run.get("completed_at", "") or ""),
    )


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
            <div class="pipeline-ops-title">Know whether the pipeline is healthy before you run anything else.</div>
            <div class="pipeline-ops-copy">
                Use this as the fast operational check: current state, the last completed run, and whether anything needs attention before the next search.
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
        "This is the short setup view. It tells you what AI-assisted capabilities are ready without making you read the full configuration state.",
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
    if next_step:
        st.info(next_step)

    _close_section_shell()


def _render_run_inputs() -> None:
    settings = load_settings()
    current_title_groups = load_title_groups_from_settings(settings)
    current_preferred_locations = str(settings.get("preferred_locations", "") or "")
    current_preferred_job_levels = parse_preferred_job_levels(settings.get("preferred_job_levels", ""))
    current_include_keywords = str(settings.get("include_keywords", "") or "")
    current_exclude_keywords = str(settings.get("exclude_keywords", "") or "")
    current_include_remote = _str_to_bool(settings.get("include_remote", "true"), default=True)
    current_search_strategy = str(settings.get("search_strategy", "broad_recall") or "broad_recall")

    pending_title_groups = st.session_state.pop("pipeline_pending_title_groups_value", None)
    if pending_title_groups is not None:
        st.session_state["pipeline_title_groups_value"] = normalize_title_groups(pending_title_groups)

    pending_preferred_locations = st.session_state.pop("pipeline_pending_preferred_locations_value", None)
    if pending_preferred_locations is not None:
        st.session_state["pipeline_preferred_locations_value"] = str(pending_preferred_locations)

    if "pipeline_title_groups_value" not in st.session_state:
        st.session_state["pipeline_title_groups_value"] = normalize_title_groups(current_title_groups) or [create_empty_title_group()]
    if "pipeline_preferred_locations_value" not in st.session_state:
        st.session_state["pipeline_preferred_locations_value"] = current_preferred_locations
    if "pipeline_preferred_job_levels_value" not in st.session_state:
        st.session_state["pipeline_preferred_job_levels_value"] = current_preferred_job_levels
    if "pipeline_include_keywords_value" not in st.session_state:
        st.session_state["pipeline_include_keywords_value"] = current_include_keywords
    if "pipeline_exclude_keywords_value" not in st.session_state:
        st.session_state["pipeline_exclude_keywords_value"] = current_exclude_keywords
    if "pipeline_include_remote_value" not in st.session_state:
        st.session_state["pipeline_include_remote_value"] = current_include_remote
    if "pipeline_search_strategy_value" not in st.session_state:
        current_strategy_label = next(
            (label for label, value in SEARCH_STRATEGY_OPTIONS.items() if value == current_search_strategy),
            "Broader Search",
        )
        st.session_state["pipeline_search_strategy_value"] = current_strategy_label
    if "pipeline_title_suggestions_notes" not in st.session_state:
        st.session_state["pipeline_title_suggestions_notes"] = ""
    if "pipeline_title_suggestion_message" not in st.session_state:
        st.session_state["pipeline_title_suggestion_message"] = ""
    if "pipeline_run_input_summary" not in st.session_state:
        st.session_state["pipeline_run_input_summary"] = {}

    suggestion_message = str(st.session_state.get("pipeline_title_suggestion_message", "") or "").strip()
    notes = str(st.session_state.get("pipeline_title_suggestions_notes", "") or "").strip()
    run_input_summary = st.session_state.get("pipeline_run_input_summary", {}) or {}
    run_input_notice_message = str(st.session_state.pop("pipeline_run_input_notice_message", "") or "").strip()
    run_input_notice_level = str(st.session_state.pop("pipeline_run_input_notice_level", "success") or "success").strip().lower()
    suggested_titles = run_input_summary.get("titles", []) or []
    suggested_title_groups = run_input_summary.get("title_groups", []) or []
    suggested_locations = run_input_summary.get("locations", []) or []

    _render_section_shell(
        "Search setup",
        "Adjust what the search looks for",
        "Update these inputs only when you want to change the search shape.",
        compact=True,
    )

    section_left, section_right = st.columns([1.45, 0.95], gap="large")

    with section_left:
        st.markdown("**Target Titles**")
        st.caption("Enter up to 10 main titles. AI will generate close subtitle variants for each title on save, and you can deselect any variant you do not want to use.")
        rendered_title_groups = _render_pipeline_title_group_editor(
            st.session_state.get("pipeline_title_groups_value", current_title_groups)
        )
        editable_title_groups = _collect_pipeline_title_groups_from_widgets(rendered_title_groups)
        st.session_state["pipeline_title_groups_value"] = editable_title_groups

        location_col, remote_col = st.columns([1.35, 0.65], gap="medium")
        with location_col:
            st.text_area(
                "Preferred Locations",
                key="pipeline_preferred_locations_value",
                height=100,
                help="One location per line. Examples:\nDallas, TX\nMiami, FL\nLondon, UK\nUse full structured entries instead of comma-separated fragments.",
            )
        with remote_col:
            st.markdown("<div style='height: 1.8rem;'></div>", unsafe_allow_html=True)
            st.toggle(
                "Include Remote",
                key="pipeline_include_remote_value",
                help="When on, remote roles can be included alongside your preferred locations.",
            )

        levels_col, strategy_col = st.columns([1.1, 0.9], gap="medium")
        with levels_col:
            st.multiselect(
                "Preferred Job Levels",
                options=JOB_LEVEL_OPTIONS,
                key="pipeline_preferred_job_levels_value",
                help="AI scoring will penalize jobs whose title level falls below the levels you select here.",
            )
        with strategy_col:
            st.selectbox(
                "Search Strategy",
                options=list(SEARCH_STRATEGY_OPTIONS.keys()),
                key="pipeline_search_strategy_value",
                help="Broader Search is the recommended default for V1. Standard keeps the search tighter when you want a narrower pass.",
            )

        include_col, exclude_col = st.columns(2, gap="medium")
        with include_col:
            st.text_area(
                "Include Keywords",
                key="pipeline_include_keywords_value",
                height=96,
                help="Comma-separated values",
            )
        with exclude_col:
            st.text_area(
                "Exclude Keywords",
                key="pipeline_exclude_keywords_value",
                height=96,
                help="Comma-separated values",
            )

    current_groups_serialized = serialize_title_groups(current_title_groups)
    editable_groups_serialized = serialize_title_groups(editable_title_groups)
    has_run_input_changes = any(
        [
            editable_groups_serialized != current_groups_serialized,
            str(st.session_state.get("pipeline_preferred_locations_value", current_preferred_locations)) != current_preferred_locations,
            serialize_preferred_job_levels(st.session_state.get("pipeline_preferred_job_levels_value", current_preferred_job_levels))
            != str(settings.get("preferred_job_levels", "")),
            str(st.session_state.get("pipeline_include_keywords_value", current_include_keywords)) != current_include_keywords,
            str(st.session_state.get("pipeline_exclude_keywords_value", current_exclude_keywords)) != current_exclude_keywords,
            ("true" if bool(st.session_state.get("pipeline_include_remote_value", current_include_remote)) else "false")
            != str(settings.get("include_remote", "true")),
            SEARCH_STRATEGY_OPTIONS.get(
                str(st.session_state.get("pipeline_search_strategy_value", "Broader Search")),
                "broad_recall",
            ) != current_search_strategy,
        ]
    )

    with section_right:
        _render_pipeline_ai_chip()
        save_run_inputs = st.button(
            "Save Run Inputs",
            type="primary",
            use_container_width=True,
            disabled=app_is_busy() or (not has_run_input_changes),
        )

        st.caption("Save changes here before you search. AI can clean up titles and locations and add likely variants directly into the fields.")

        if run_input_notice_message:
            if run_input_notice_level == "error":
                st.error(run_input_notice_message)
            elif run_input_notice_level == "warning":
                st.warning(run_input_notice_message)
            else:
                st.success(run_input_notice_message)

        if suggested_titles or suggestion_message or suggested_title_groups or suggested_locations:
            st.markdown('<div class="pipeline-ai-updates-box">', unsafe_allow_html=True)
            st.markdown('<div class="pipeline-ai-updates-title">AI Input Updates</div>', unsafe_allow_html=True)
            if suggestion_message:
                st.markdown(
                    f'<div class="pipeline-ai-updates-copy">{html.escape(suggestion_message)}</div>',
                    unsafe_allow_html=True,
                )
            if notes:
                st.markdown(
                    f'<div class="pipeline-ai-updates-copy">{html.escape(notes)}</div>',
                    unsafe_allow_html=True,
                )
            if suggested_title_groups:
                st.markdown('<div class="pipeline-ai-updates-label">Subtitle variants by main title</div>', unsafe_allow_html=True)
                for group in suggested_title_groups:
                    main_title = str(group.get("main_title", "") or "").strip()
                    if not main_title:
                        continue
                    variant_titles = [
                        str(variant.get("title", "") or "").strip()
                        for variant in (group.get("variants", []) or [])
                        if str(variant.get("title", "") or "").strip()
                    ]
                    detail = ", ".join(variant_titles) if variant_titles else "No subtitle variants added"
                    st.markdown(
                        f'<div class="pipeline-ai-updates-copy"><strong>{html.escape(main_title)}</strong>: {html.escape(detail)}</div>',
                        unsafe_allow_html=True,
                    )
            elif suggested_titles:
                title_items = "".join(f"<li>{html.escape(str(title))}</li>" for title in suggested_titles)
                st.markdown(
                    '<div class="pipeline-ai-updates-label">Effective search titles</div>'
                    f'<ul class="pipeline-ai-updates-list">{title_items}</ul>',
                    unsafe_allow_html=True,
                )
            if suggested_locations:
                location_items = "".join(f"<li>{html.escape(str(location))}</li>" for location in suggested_locations)
                st.markdown(
                    '<div class="pipeline-ai-updates-label">Current saved location lines</div>'
                    f'<ul class="pipeline-ai-updates-list">{location_items}</ul>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)
        elif suggestion_message:
            st.caption(suggestion_message)

    if save_run_inputs:
        queue_action(
            "pipeline",
            "save_run_inputs",
            payload={
                "title_groups": editable_title_groups,
                "preferred_locations": str(
                    st.session_state.get("pipeline_preferred_locations_value", current_preferred_locations) or ""
                ),
                "preferred_job_levels": st.session_state.get(
                    "pipeline_preferred_job_levels_value",
                    current_preferred_job_levels,
                ),
                "include_keywords": str(
                    st.session_state.get("pipeline_include_keywords_value", current_include_keywords) or ""
                ),
                "exclude_keywords": str(
                    st.session_state.get("pipeline_exclude_keywords_value", current_exclude_keywords) or ""
                ),
                "include_remote": bool(
                    st.session_state.get("pipeline_include_remote_value", current_include_remote)
                ),
                "search_strategy": str(
                    st.session_state.get("pipeline_search_strategy_value", "Broader Search") or "Broader Search"
                ),
            },
            label="Save Run Inputs",
        )
        st.rerun()


    _close_section_shell()


def _render_action_deck() -> None:
    busy = app_is_busy()
    _render_section_shell(
        "Main action",
        "Run one search and send matches to New Roles",
        "This is the core workflow. Use it to discover, score, and queue the strongest roles for review.",
        compact=True,
    )
    _render_pipeline_ai_chip()
    if st.button("Find Roles", type="primary", use_container_width=True, disabled=busy, key="pipeline_primary_run"):
        st.session_state["pipeline_run_started_at"] = datetime.now().isoformat()
        queue_action(
            "pipeline",
            "discover_and_ingest",
            payload={
                "use_ai_title_expansion": False,
                "use_ai_scoring": True,
            },
            label="Find Roles",
        )
        st.rerun()

    st.markdown(
        '<div class="pipeline-secondary-actions-note">Best for normal day-to-day searching. Searches use your saved main titles plus selected subtitle variants without adding extra run-time title expansion.</div>',
        unsafe_allow_html=True,
    )
    _close_section_shell()


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


def _get_last_result_next_step_message(last_result: dict) -> str:
    output_text = str(last_result.get("output", "") or "")
    status = str(last_result.get("status", "") or "").strip().lower()

    if status == "completed":
        if "Rescore summary:" in output_text:
            return "Review New Roles and spot-check AI Fit Detail on the jobs that changed the most."
        if "Validation + ingestion complete." in output_text:
            return "Go to New Roles to review the strongest matches, then generate a cover letter or mark one as applied."
    return ""


def _render_last_result_card() -> None:
    last_result = st.session_state.get("pipeline_last_result")
    if not last_result:
        return

    _render_section_shell(
        "Full output",
        "Open the raw result only when you need detail",
        "This keeps the page focused on decisions first and raw run text second.",
        compact=True,
    )
    with st.expander("Open last result", expanded=False):
        _render_copy_result_button(str(last_result.get("output", "") or ""), key="last_result")
        _render_result(last_result)
    _close_section_shell()


def _render_more_results_expander() -> None:
    runs = get_recent_ingestion_runs(limit=1)
    if not runs:
        return

    run = runs[0]
    details = run.get("details", {}) if isinstance(run.get("details", {}), dict) else {}

    run_id = run.get("id", "")
    started_at = str(run.get("started_at", "") or "")
    completed_at = str(run.get("completed_at", "") or "")
    status = str(run.get("status", "") or "Unknown")
    ingest_duration = _get_preferred_run_duration(run)

    total_seen = run.get("total_seen", 0)
    inserted_count = run.get("inserted_count", 0)
    updated_count = run.get("updated_count", 0)
    error_count = run.get("error_count", 0)

    net_new_count = details.get("net_new_count", inserted_count) if isinstance(details, dict) else inserted_count
    rediscovered_count = details.get("rediscovered_count", 0) if isinstance(details, dict) else 0
    duplicate_in_run_count = details.get("duplicate_in_run_count", 0) if isinstance(details, dict) else 0

    source_yield_top = details.get("source_yield_top", []) if isinstance(details, dict) else []
    source_dominance = details.get("source_dominance", {}) if isinstance(details, dict) else {}

    with st.expander("More Results", expanded=False):
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


def _render_results_summary_card() -> None:
    latest_run = _get_latest_run()
    last_result = st.session_state.get("pipeline_last_result") or {}

    if not latest_run and not last_result:
        _render_section_shell(
            "Search Results",
            "No results yet",
            "Run a search first, then this page will summarize what happened.",
            compact=True,
        )
        if st.button("Go to Find Roles", key="pipeline_results_empty_to_run_jobs", type="primary", use_container_width=True):
            _navigate_pipeline_section("Find Roles")
        _close_section_shell()
        return

    next_step_message = _get_last_result_next_step_message(last_result)
    details = latest_run.get("details", {}) if latest_run and isinstance(latest_run.get("details", {}), dict) else {}

    run_status = _humanize_pipeline_status(str((latest_run or {}).get("status", "") or "Completed"))
    duration = _get_preferred_run_duration(latest_run)
    net_new = int((details or {}).get("net_new_count", (latest_run or {}).get("inserted_count", 0) or 0) or 0)
    errors = int((latest_run or {}).get("error_count", 0) or 0)
    total_seen = int((latest_run or {}).get("total_seen", 0) or 0)
    current_search_strategy = str(load_settings().get("search_strategy", "broad_recall") or "broad_recall").strip().lower()

    _render_section_shell(
        "Latest run",
        "Start here",
        "This is the quick read on the most recent search.",
        compact=True,
    )

    top1, top2, top3, top4 = st.columns(4)
    top1.metric("Status", run_status)
    top2.metric("Net New", net_new)
    top3.metric("Errors", errors)
    top4.metric("Seen", total_seen)

    st.caption(f"Latest completed run duration: {duration}")

    if next_step_message:
        st.info(f"Next step: {next_step_message}")

    should_nudge_broader_search = (
        current_search_strategy != "broad_recall"
        and errors == 0
        and (net_new == 0 or total_seen <= 5)
    )
    if should_nudge_broader_search:
        st.info(
            "Results looked light. Try Broader Search in Find Roles if this role is sparse, senior, or harder to source."
        )
        if st.button(
            "Go to Find Roles",
            key="pipeline_results_try_broader_search",
            use_container_width=True,
        ):
            _navigate_pipeline_section("Find Roles")

    _render_more_results_expander()

    _close_section_shell()


def _render_pipeline_run_jobs_tab() -> None:
    _render_subpage_intro(
        "Find Roles",
        "Search for new roles",
        "Set the search once, save it when needed, and run the main search from here.",
    )
    _render_run_inputs()
    _render_action_deck()


def _render_pipeline_results_tab() -> None:
    _render_subpage_intro(
        "Search Results",
        "See what the last search found",
        "Start with the summary, then open diagnostics only if something looks off.",
    )
    _render_results_summary_card()
    _render_run_diagnostics_card()
    _render_last_result_card()


def render_pipeline() -> None:
    _process_pending_action_before_render()
    _inject_pipeline_css()

    st.subheader("Pipeline")
    _render_flash()
    initialize_nav_state("pipeline_subnav_selection", "Find Roles")

    selected_section = render_button_nav(
        options=PIPELINE_NAV_OPTIONS,
        state_key="pipeline_subnav_selection",
        key_prefix="pipeline_subnav",
        selected_button_type="tertiary",
    )
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

    if selected_section == "Find Roles":
        _render_pipeline_run_jobs_tab()
    else:
        _render_pipeline_results_tab()

    _advance_pending_action_after_render()
