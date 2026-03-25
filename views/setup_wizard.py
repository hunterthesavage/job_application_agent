from __future__ import annotations

import streamlit as st

from services.job_levels import (
    JOB_LEVEL_OPTIONS,
    parse_preferred_job_levels,
    serialize_preferred_job_levels,
)
from services.openai_key import (
    delete_saved_openai_api_key,
    get_effective_openai_api_key,
    get_openai_api_key_details,
    load_saved_openai_api_key,
    save_openai_api_key,
)
from services.profile_context_templates import generate_profile_context_from_resume
from services.settings import load_settings, save_settings
from services.openai_title_suggestions import suggest_titles_with_openai
from services.ui_busy import queue_action


SETUP_WIZARD_STEPS = [
    "Welcome",
    "OpenAI API",
    "Profile Context",
    "Search Criteria",
    "AI Review",
]


def _current_step_index() -> int:
    try:
        idx = int(st.session_state.get("setup_wizard_step_index", 0))
    except Exception:
        idx = 0
    return max(0, min(idx, len(SETUP_WIZARD_STEPS) - 1))


def _set_step_index(index: int) -> None:
    st.session_state["setup_wizard_step_index"] = max(0, min(index, len(SETUP_WIZARD_STEPS) - 1))


def _go_next() -> None:
    _set_step_index(_current_step_index() + 1)


def _go_back() -> None:
    _set_step_index(_current_step_index() - 1)


def _start_first_discovery() -> None:
    save_settings(
        {
            "setup_wizard_completed": "true",
            "setup_wizard_dismissed": "true",
        }
    )
    st.session_state["_wizard_first_discovery_redirect"] = True
    st.session_state["top_nav_selection"] = "Pipeline"
    st.session_state["pipeline_subnav_selection"] = "Overview"
    st.session_state["_post_wizard_run_message"] = {
        "kind": "info",
        "text": "Starting your first discovery run now.",
    }
    queue_action("pipeline", "discover_and_ingest", label="Find and Add Jobs")


def _skip_to_app() -> None:
    save_settings(
        {
            "setup_wizard_dismissed": "true",
        }
    )
    st.session_state["top_nav_selection"] = "Settings"


def _initialize_wizard_state(settings: dict[str, str]) -> None:
    if "setup_wizard_step_index" not in st.session_state:
        st.session_state["setup_wizard_step_index"] = 0

    if "wizard_target_titles" not in st.session_state:
        st.session_state["wizard_target_titles"] = settings.get("target_titles", "")
    if "wizard_preferred_locations" not in st.session_state:
        st.session_state["wizard_preferred_locations"] = settings.get("preferred_locations", "")
    if "wizard_preferred_job_levels" not in st.session_state:
        st.session_state["wizard_preferred_job_levels"] = parse_preferred_job_levels(
            settings.get("preferred_job_levels", "")
        )
    if "wizard_include_keywords" not in st.session_state:
        st.session_state["wizard_include_keywords"] = settings.get("include_keywords", "")
    if "wizard_exclude_keywords" not in st.session_state:
        st.session_state["wizard_exclude_keywords"] = settings.get("exclude_keywords", "")
    if "wizard_remote_only" not in st.session_state:
        st.session_state["wizard_remote_only"] = str(settings.get("remote_only", "false")).strip().lower() == "true"
    if "wizard_minimum_compensation" not in st.session_state:
        st.session_state["wizard_minimum_compensation"] = settings.get("minimum_compensation", "")

    if "wizard_resume_text" not in st.session_state:
        st.session_state["wizard_resume_text"] = settings.get("resume_text", "")
    if "wizard_profile_summary" not in st.session_state:
        st.session_state["wizard_profile_summary"] = settings.get("profile_summary", "")
    if "wizard_strengths_to_highlight" not in st.session_state:
        st.session_state["wizard_strengths_to_highlight"] = settings.get("strengths_to_highlight", "")
    if "wizard_cover_letter_voice" not in st.session_state:
        st.session_state["wizard_cover_letter_voice"] = settings.get("cover_letter_voice", "")

    if "wizard_openai_api_key_value" not in st.session_state:
        st.session_state["wizard_openai_api_key_value"] = load_saved_openai_api_key()

    if "wizard_title_suggestions" not in st.session_state:
        st.session_state["wizard_title_suggestions"] = []
    if "wizard_title_suggestions_notes" not in st.session_state:
        st.session_state["wizard_title_suggestions_notes"] = ""
    if "wizard_ai_review_generated" not in st.session_state:
        st.session_state["wizard_ai_review_generated"] = False
    if "wizard_ai_review_message" not in st.session_state:
        st.session_state["wizard_ai_review_message"] = ""
    if "wizard_ai_review_choice_made" not in st.session_state:
        st.session_state["wizard_ai_review_choice_made"] = False


def _render_progress(step_index: int) -> None:
    step_number = step_index + 1
    st.caption(f"Setup progress · Step {step_number} of {len(SETUP_WIZARD_STEPS)}")
    st.progress(step_number / len(SETUP_WIZARD_STEPS))


def _render_shell_open() -> None:
    st.markdown(
        """
        <div style="
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(16,22,36,0.96) 0%, rgba(10,14,24,0.98) 100%);
            box-shadow: 0 18px 48px rgba(0,0,0,0.24);
            padding: 1.4rem 1.4rem 1.2rem 1.4rem;
            margin-top: 0.4rem;
            margin-bottom: 1.2rem;
        ">
        """,
        unsafe_allow_html=True,
    )


def _render_shell_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def _render_welcome_step() -> None:
    st.markdown("## Set up your Job Application Agent")
    st.write(
        "We’ll get the essentials ready so the app can find jobs that match your search and optionally generate AI-assisted cover letters."
    )

    st.markdown("### What we’ll set up")
    st.markdown(
        """
1. **OpenAI API** so AI suggestions and cover letters are ready if you want them  
2. **Profile Context** to improve AI-generated content, optional  
3. **Search Criteria** so the app knows what roles to look for  
4. **AI Review** so you can broaden titles before your first run  
5. **Find and Add Jobs** so you can start with real results
        """
    )

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

    if st.button("Start Setup", type="primary", use_container_width=True, key="wizard_start_setup"):
        _go_next()
        st.rerun()

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
    skip_col_1, skip_col_2 = st.columns([1, 5])
    with skip_col_1:
        if st.button("Skip", type="secondary", use_container_width=True, key="wizard_skip_to_app_welcome"):
            _skip_to_app()
            st.rerun()
    with skip_col_2:
        st.caption("Skip for now and go straight into the app.")


def _append_comma_separated(base_value: str, additions: list[str]) -> str:
    current = [part.strip() for part in str(base_value or "").split(",") if part.strip()]
    seen = {item.casefold() for item in current}
    for item in additions:
        clean = str(item or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        current.append(clean)
        seen.add(key)
    return ", ".join(current)


def _clear_wizard_title_suggestions() -> None:
    st.session_state["wizard_title_suggestions"] = []
    st.session_state["wizard_title_suggestions_notes"] = ""
    for key in list(st.session_state.keys()):
        if key.startswith("wizard_title_checkbox_"):
            del st.session_state[key]


def _generate_wizard_title_suggestions() -> None:
    details = get_openai_api_key_details()
    titles_clean = str(st.session_state.get("wizard_target_titles", "") or "").strip()
    include_clean = str(st.session_state.get("wizard_include_keywords", "") or "").strip()

    st.session_state["wizard_ai_review_generated"] = True
    st.session_state["wizard_ai_review_choice_made"] = False
    st.session_state["wizard_ai_review_message"] = ""
    _clear_wizard_title_suggestions()

    if not titles_clean:
        st.session_state["wizard_ai_review_message"] = "Add at least one target title to get AI title suggestions."
        return

    if not bool(details.get("active_key_present")):
        st.session_state["wizard_ai_review_message"] = "No OpenAI key is configured, so there are no AI title suggestions yet. You can continue with your current titles."
        return

    result = suggest_titles_with_openai(
        current_titles=titles_clean,
        profile_summary=str(st.session_state.get("wizard_profile_summary", "") or ""),
        resume_text=str(st.session_state.get("wizard_resume_text", "") or ""),
        include_keywords=include_clean,
    )

    if result.get("ok"):
        titles = result.get("titles", []) or []
        st.session_state["wizard_title_suggestions"] = titles
        st.session_state["wizard_title_suggestions_notes"] = str(result.get("notes", "") or "")
        if titles:
            st.session_state["wizard_ai_review_message"] = "Review the suggested title updates below before your first run."
        else:
            st.session_state["wizard_ai_review_message"] = "No additional title suggestions were returned. You can continue with your current titles."
        return

    error_text = str(result.get("error", "") or "").strip()
    if error_text:
        st.session_state["wizard_ai_review_message"] = f"Could not generate title suggestions. You can continue with your current titles. {error_text}"
    else:
        st.session_state["wizard_ai_review_message"] = "Could not generate title suggestions. You can continue with your current titles."


def _render_search_step() -> None:
    st.markdown("## Search Criteria")
    st.write("This step drives the search. Add the titles, locations, and keywords you want the app to use.")

    if "wizard_target_titles_widget" not in st.session_state:
        st.session_state["wizard_target_titles_widget"] = st.session_state.get("wizard_target_titles", "")
    if "wizard_preferred_locations_widget" not in st.session_state:
        st.session_state["wizard_preferred_locations_widget"] = st.session_state.get("wizard_preferred_locations", "")
    if "wizard_preferred_job_levels_widget" not in st.session_state:
        st.session_state["wizard_preferred_job_levels_widget"] = list(
            st.session_state.get("wizard_preferred_job_levels", [])
        )
    if "wizard_include_keywords_widget" not in st.session_state:
        st.session_state["wizard_include_keywords_widget"] = st.session_state.get("wizard_include_keywords", "")
    if "wizard_exclude_keywords_widget" not in st.session_state:
        st.session_state["wizard_exclude_keywords_widget"] = st.session_state.get("wizard_exclude_keywords", "")
    if "wizard_remote_only_widget" not in st.session_state:
        st.session_state["wizard_remote_only_widget"] = bool(st.session_state.get("wizard_remote_only", False))
    if "wizard_minimum_compensation_widget" not in st.session_state:
        st.session_state["wizard_minimum_compensation_widget"] = st.session_state.get("wizard_minimum_compensation", "")

    with st.form("setup_wizard_search_form"):
        c1, c2 = st.columns(2)

        with c1:
            target_titles = st.text_area(
                "Target Titles",
                key="wizard_target_titles_widget",
                height=120,
                help="Comma-separated values. Example: VP Technology, CIO, Head of Platform",
            )

            preferred_locations = st.text_area(
                "Preferred Locations",
                key="wizard_preferred_locations_widget",
                height=120,
                help="One location per line. Examples:\nDallas, TX\nMiami, FL\nLondon, UK\nYou can leave this blank only if Remote Only is turned on.",
            )

            preferred_job_levels = st.multiselect(
                "Preferred Job Levels",
                options=JOB_LEVEL_OPTIONS,
                default=st.session_state.get("wizard_preferred_job_levels_widget", []),
                help="AI scoring will penalize jobs whose title level falls below the levels you select here.",
            )

            include_keywords = st.text_area(
                "Include Keywords",
                key="wizard_include_keywords_widget",
                height=100,
                help="Optional. Comma-separated values.",
            )

        with c2:
            exclude_keywords = st.text_area(
                "Exclude Keywords",
                key="wizard_exclude_keywords_widget",
                height=100,
                help="Optional. Comma-separated values.",
            )

            remote_only = st.toggle("Remote Only", key="wizard_remote_only_widget")

            minimum_compensation = st.text_input(
                "Minimum Compensation",
                key="wizard_minimum_compensation_widget",
                help="Optional. Leave blank if you do not want to filter on compensation.",
            )

        back_col, next_col = st.columns([1, 1.35])
        with back_col:
            back_clicked = st.form_submit_button("Back", use_container_width=True)
        with next_col:
            next_clicked = st.form_submit_button("Suggest Relevant Updates", type="primary", use_container_width=True)

        if back_clicked:
            _go_back()
            st.rerun()

        if next_clicked:
            titles_clean = str(target_titles or "").strip()
            locations_clean = str(preferred_locations or "").strip()
            preferred_job_levels_clean = serialize_preferred_job_levels(preferred_job_levels)
            include_clean = str(include_keywords or "").strip()
            exclude_clean = str(exclude_keywords or "").strip()
            minimum_clean = str(minimum_compensation or "").strip()

            if not titles_clean:
                st.error("Add at least one target title before continuing.")
                return
            if not locations_clean and not remote_only:
                st.error("Add at least one preferred location or turn on Remote Only.")
                return

            save_settings(
                {
                    "target_titles": titles_clean,
                    "preferred_locations": locations_clean,
                    "preferred_job_levels": preferred_job_levels_clean,
                    "include_keywords": include_clean,
                    "exclude_keywords": exclude_clean,
                    "remote_only": "true" if remote_only else "false",
                    "minimum_compensation": minimum_clean,
                }
            )

            st.session_state["wizard_target_titles"] = titles_clean
            st.session_state["wizard_preferred_locations"] = locations_clean
            st.session_state["wizard_preferred_job_levels"] = list(preferred_job_levels)
            st.session_state["wizard_preferred_job_levels_widget"] = list(preferred_job_levels)
            st.session_state["wizard_include_keywords"] = include_clean
            st.session_state["wizard_exclude_keywords"] = exclude_clean
            st.session_state["wizard_remote_only"] = remote_only
            st.session_state["wizard_minimum_compensation"] = minimum_clean
            st.session_state["wizard_ai_review_generated"] = False
            st.session_state["wizard_ai_review_choice_made"] = False
            st.session_state["wizard_ai_review_message"] = ""
            _clear_wizard_title_suggestions()

            _go_next()
            st.rerun()


def _render_profile_step() -> None:
    st.markdown("## Profile Context")
    st.write(
        "This is the main context used for AI scoring and cover letters. Discovery still works without it, but accepted jobs will skip AI scoring unless a fallback profile file exists."
    )

    resume_present = bool(str(st.session_state.get("wizard_resume_text", "") or "").strip())
    api_key_present = bool(get_effective_openai_api_key())
    can_generate = resume_present and api_key_present

    helper_left, helper_right = st.columns([1.1, 2.2])
    with helper_left:
        if st.button(
            "Generate from Resume",
            key="wizard_generate_profile_from_resume",
            disabled=not can_generate,
            help=(
                "Generate the profile fields from the current Resume Text."
                if can_generate
                else "Paste Resume Text and add an OpenAI API key first."
            ),
        ):
            with st.spinner("Generating profile context from resume..."):
                result = generate_profile_context_from_resume(
                    st.session_state.get("wizard_resume_text", "")
                )
            if result.get("ok"):
                st.session_state["wizard_profile_summary"] = str(result.get("profile_summary", "") or "")
                st.session_state["wizard_strengths_to_highlight"] = str(result.get("strengths_to_highlight", "") or "")
                st.session_state["wizard_cover_letter_voice"] = str(result.get("cover_letter_voice", "") or "")
                st.success("Generated profile fields from your resume text.")
                st.rerun()
            st.error(str(result.get("error", "") or "Could not generate profile context from resume."))
    with helper_right:
        st.caption("Paste resume text first, then generate the summary, strengths, and cover letter voice from that resume. This does not overwrite Resume Text.")

    resume_text = st.text_area(
        "Resume Text",
        key="wizard_resume_text",
        height=200,
        help="Primary supporting evidence for AI scoring and cover letters.",
    )
    profile_summary = st.text_area(
        "Executive Summary",
        key="wizard_profile_summary",
        height=120,
        help="High-priority scoring input. Use this for your executive summary and target profile.",
    )
    strengths_to_highlight = st.text_area(
        "Strengths to Highlight",
        key="wizard_strengths_to_highlight",
        height=120,
        help="High-priority scoring input. Example: AI transformation, enterprise IT leadership, ServiceNow.",
    )
    cover_letter_voice = st.text_area(
        "Cover Letter Voice",
        key="wizard_cover_letter_voice",
        height=100,
        help="Cover letters only. This does not affect job scoring.",
    )

    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c1:
        back_clicked = st.button("Back", use_container_width=True, key="wizard_profile_back")
    with c2:
        save_clicked = st.button("Save and Continue", type="primary", use_container_width=True, key="wizard_profile_save_continue")
    with c3:
        skip_clicked = st.button("Skip for Now", use_container_width=True, key="wizard_profile_skip")

    if back_clicked:
        _go_back()
        st.rerun()
    if save_clicked:
        save_settings(
            {
                "resume_text": str(resume_text or "").strip(),
                "profile_summary": str(profile_summary or "").strip(),
                "strengths_to_highlight": str(strengths_to_highlight or "").strip(),
                "cover_letter_voice": str(cover_letter_voice or "").strip(),
            }
        )
        st.session_state["wizard_resume_text"] = str(resume_text or "").strip()
        st.session_state["wizard_profile_summary"] = str(profile_summary or "").strip()
        st.session_state["wizard_strengths_to_highlight"] = str(strengths_to_highlight or "").strip()
        st.session_state["wizard_cover_letter_voice"] = str(cover_letter_voice or "").strip()
        _go_next()
        st.rerun()
    if skip_clicked:
        _go_next()
        st.rerun()


def _render_openai_step() -> None:
    st.markdown("## OpenAI API")
    st.write(
        "Optional, but recommended. This powers AI title suggestions during setup, AI scoring, AI scrub, and cover letters."
    )

    details = get_openai_api_key_details()
    source_label_map = {
        "saved": "Saved local key",
        "environment": "Environment variable",
        "none": "No key configured",
    }
    status_label = "Configured" if details["active_key_present"] else "Not Configured"
    source_label = source_label_map.get(str(details["active_source"]), "No key configured")

    st.markdown(f"**Status:** {status_label}")
    st.markdown(f"**Active key source:** {source_label}")
    if details["active_key_present"]:
        st.markdown(f"**Active key:** `{details['active_key_masked']}`")
        st.success("AI-assisted features are ready to use during setup and later runs.")
    else:
        st.caption("Without a key, you can still finish setup and discover jobs, but AI title suggestions, scoring, scrub, and cover letters will stay off.")

    if str(details["active_source"]) == "environment" and not bool(details["saved_key_present"]):
        st.caption(
            "This app is using OPENAI_API_KEY from the environment. There is no saved local key to delete here."
        )
    elif bool(details["saved_key_present"]) and bool(details["environment_key_present"]):
        st.caption(
            "A saved local key is currently overriding the environment key. "
            "If you delete the saved key, the environment key will become active."
        )

    st.text_input(
        "OpenAI API Key",
        key="wizard_openai_api_key_value",
        type="password",
        help="Paste the API key you want to save locally for this machine.",
    )

    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c1:
        if st.button("Back", use_container_width=True, key="wizard_openai_back"):
            _go_back()
            st.rerun()
    with c2:
        if st.button("Save and Continue", type="primary", use_container_width=True, key="wizard_openai_save"):
            key_value = str(st.session_state.get("wizard_openai_api_key_value", "")).strip()
            if key_value:
                try:
                    save_openai_api_key(key_value)
                except Exception as exc:
                    st.error(f"Failed to save API key: {exc}")
                    return
            _go_next()
            st.rerun()
    with c3:
        if st.button("Skip for Now", use_container_width=True, key="wizard_openai_skip"):
            _go_next()
            st.rerun()

    if details["can_delete_saved_key"]:
        if st.button("Delete Saved Local Key", type="secondary", key="wizard_delete_saved_openai"):
            try:
                delete_saved_openai_api_key()
                st.session_state["wizard_openai_api_key_value"] = ""
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to delete saved API key: {exc}")


def _render_ai_review_step() -> None:
    st.markdown("## Review Relevant Updates")
    st.write("Before your first run, review AI-suggested updates to broaden your search. For now this step suggests related titles. Keyword suggestions can be added next.")

    if not st.session_state.get("wizard_ai_review_generated", False):
        with st.spinner("Reviewing titles and suggesting relevant updates..."):
            _generate_wizard_title_suggestions()

    message = str(st.session_state.get("wizard_ai_review_message", "") or "").strip()
    if message:
        if st.session_state.get("wizard_title_suggestions"):
            st.info(message)
        else:
            st.warning(message)

    st.markdown("### Target Titles")
    st.text_area(
        "Target Titles",
        value=str(st.session_state.get("wizard_target_titles", "") or ""),
        height=120,
        disabled=True,
        label_visibility="collapsed",
    )

    suggestions = st.session_state.get("wizard_title_suggestions", []) or []
    notes = str(st.session_state.get("wizard_title_suggestions_notes", "") or "").strip()
    choice_made = bool(st.session_state.get("wizard_ai_review_choice_made", False))

    if suggestions and not choice_made:
        with st.container(border=True):
            st.markdown("### Suggested Titles")
            if notes:
                st.caption(notes)
            st.caption("Choose which suggested titles you want to add before your first run.")

            selected: list[str] = []
            for index, title in enumerate(suggestions):
                checkbox_key = f"wizard_title_checkbox_{index}"
                if checkbox_key not in st.session_state:
                    st.session_state[checkbox_key] = True
                if st.checkbox(title, key=checkbox_key):
                    selected.append(title)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Accept Title Suggestions", type="primary", use_container_width=True, key="wizard_accept_titles"):
                    updated = _append_comma_separated(st.session_state.get("wizard_target_titles", ""), selected)
                    st.session_state["wizard_target_titles"] = updated
                    st.session_state["wizard_target_titles_widget"] = updated
                    save_settings({"target_titles": updated})
                    st.session_state["wizard_ai_review_choice_made"] = True
                    st.session_state["wizard_ai_review_message"] = "Selected title suggestions were added. Review the final Target Titles below, then click Find and Add Jobs."
                    st.rerun()
            with c2:
                if st.button("Cancel", use_container_width=True, key="wizard_cancel_titles"):
                    st.session_state["wizard_ai_review_choice_made"] = True
                    st.session_state["wizard_ai_review_message"] = "No AI title updates were applied. Review the final Target Titles below, then click Find and Add Jobs."
                    st.rerun()
    else:
        st.markdown("### Target Titles")
        st.text_area(
            "Target Titles",
            value=str(st.session_state.get("wizard_target_titles", "") or ""),
            height=140,
            disabled=True,
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([1.4, 1])
        with c1:
            if st.button("Find and Add Jobs", type="primary", use_container_width=True, key="wizard_find_and_add_jobs"):
                _start_first_discovery()
                st.rerun()
        with c2:
            if st.button("Back", use_container_width=True, key="wizard_ai_review_back"):
                st.session_state["wizard_ai_review_generated"] = False
                st.session_state["wizard_ai_review_choice_made"] = False
                _go_back()
                st.rerun()


def render_setup_wizard() -> None:
    settings = load_settings()
    _initialize_wizard_state(settings)

    step_index = _current_step_index()

    _render_shell_open()
    _render_progress(step_index)

    current_step = SETUP_WIZARD_STEPS[step_index]
    if current_step == "Welcome":
        _render_welcome_step()
    elif current_step == "OpenAI API":
        _render_openai_step()
    elif current_step == "Profile Context":
        _render_profile_step()
    elif current_step == "Search Criteria":
        _render_search_step()
    else:
        _render_ai_review_step()

    _render_shell_close()
