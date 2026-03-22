from __future__ import annotations

import streamlit as st

from services.openai_key import (
    delete_saved_openai_api_key,
    get_openai_api_key_details,
    load_saved_openai_api_key,
    save_openai_api_key,
)
from services.settings import load_settings, save_settings


SETUP_WIZARD_STEPS = [
    "Welcome",
    "Search Criteria",
    "Profile Context",
    "OpenAI API",
    "Ready",
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


def _complete_and_go_to_pipeline() -> None:
    save_settings(
        {
            "setup_wizard_completed": "true",
            "setup_wizard_dismissed": "true",
        }
    )
    st.session_state["top_nav_selection"] = "Pipeline"


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
1. **Search Criteria** so the app knows what roles to look for  
2. **Profile Context** to improve AI-generated content, optional  
3. **OpenAI API** for cover letters, optional  
4. **First action** so you know exactly where to go next
        """
    )

    c1, c2 = st.columns([1.2, 1])
    with c1:
        if st.button("Start Setup", type="primary", use_container_width=True, key="wizard_start_setup"):
            _go_next()
            st.rerun()
    with c2:
        if st.button("Skip to App", type="secondary", use_container_width=True, key="wizard_skip_to_app_welcome"):
            _skip_to_app()
            st.rerun()


def _render_search_step() -> None:
    st.markdown("## Search Criteria")
    st.write("This is the only setup step that really matters to make the app useful.")

    with st.form("setup_wizard_search_form"):
        c1, c2 = st.columns(2)

        with c1:
            target_titles = st.text_area(
                "Target Titles",
                value=st.session_state.get("wizard_target_titles", ""),
                height=120,
                help="Comma-separated values. Example: VP Technology, CIO, Head of Platform",
            )

            preferred_locations = st.text_area(
                "Preferred Locations",
                value=st.session_state.get("wizard_preferred_locations", ""),
                height=120,
                help="Comma-separated values. Example: Dallas, Remote, Seattle",
            )

            include_keywords = st.text_area(
                "Include Keywords",
                value=st.session_state.get("wizard_include_keywords", ""),
                height=100,
                help="Optional. Comma-separated values.",
            )

        with c2:
            exclude_keywords = st.text_area(
                "Exclude Keywords",
                value=st.session_state.get("wizard_exclude_keywords", ""),
                height=100,
                help="Optional. Comma-separated values.",
            )

            remote_only = st.toggle(
                "Remote Only",
                value=bool(st.session_state.get("wizard_remote_only", False)),
            )

            minimum_compensation = st.text_input(
                "Minimum Compensation",
                value=st.session_state.get("wizard_minimum_compensation", ""),
                help="Optional. Leave blank if you do not want to filter on compensation.",
            )

        back_col, save_col = st.columns([1, 1.2])

        with back_col:
            back_clicked = st.form_submit_button("Back", use_container_width=True)

        with save_col:
            save_clicked = st.form_submit_button("Save and Continue", type="primary", use_container_width=True)

        if back_clicked:
            _go_back()
            st.rerun()

        if save_clicked:
            titles_clean = str(target_titles or "").strip()
            locations_clean = str(preferred_locations or "").strip()

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
                    "include_keywords": str(include_keywords or "").strip(),
                    "exclude_keywords": str(exclude_keywords or "").strip(),
                    "remote_only": "true" if remote_only else "false",
                    "minimum_compensation": str(minimum_compensation or "").strip(),
                }
            )

            st.session_state["wizard_target_titles"] = titles_clean
            st.session_state["wizard_preferred_locations"] = locations_clean
            st.session_state["wizard_include_keywords"] = str(include_keywords or "").strip()
            st.session_state["wizard_exclude_keywords"] = str(exclude_keywords or "").strip()
            st.session_state["wizard_remote_only"] = remote_only
            st.session_state["wizard_minimum_compensation"] = str(minimum_compensation or "").strip()

            _go_next()
            st.rerun()


def _render_profile_step() -> None:
    st.markdown("## Profile Context")
    st.write("Optional, but helpful if you want stronger AI-generated cover letters and better context.")

    with st.form("setup_wizard_profile_form"):
        resume_text = st.text_area(
            "Resume Text",
            value=st.session_state.get("wizard_resume_text", ""),
            height=200,
            help="Paste resume text here if you want the app to use it later for cover letter generation.",
        )

        profile_summary = st.text_area(
            "Executive Summary",
            value=st.session_state.get("wizard_profile_summary", ""),
            height=120,
            help="Optional short bio or leadership summary.",
        )

        strengths_to_highlight = st.text_area(
            "Strengths to Highlight",
            value=st.session_state.get("wizard_strengths_to_highlight", ""),
            height=120,
            help="Optional. Example: AI transformation, enterprise IT leadership, ServiceNow.",
        )

        cover_letter_voice = st.text_area(
            "Cover Letter Voice",
            value=st.session_state.get("wizard_cover_letter_voice", ""),
            height=100,
            help="Optional. Describe how you want cover letters to sound.",
        )

        c1, c2, c3 = st.columns([1, 1.2, 1])

        with c1:
            back_clicked = st.form_submit_button("Back", use_container_width=True)

        with c2:
            save_clicked = st.form_submit_button("Save and Continue", type="primary", use_container_width=True)

        with c3:
            skip_clicked = st.form_submit_button("Skip for Now", use_container_width=True)

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
    st.write("Optional. Only needed if you want cover letter generation.")

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

    if details["saved_key_present"]:
        if st.button("Delete Saved API Key", type="secondary", key="wizard_delete_saved_openai"):
            try:
                delete_saved_openai_api_key()
                st.session_state["wizard_openai_api_key_value"] = ""
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to delete saved API key: {exc}")


def _render_ready_step(settings: dict[str, str]) -> None:
    st.markdown("## Ready to Go")
    st.write("Your setup is in place. The next step is to run your first discovery pass.")

    target_titles = str(settings.get("target_titles", "")).strip() or "Not set"
    preferred_locations = str(settings.get("preferred_locations", "")).strip() or "Not set"
    remote_only = str(settings.get("remote_only", "false")).strip().lower() == "true"

    c1, c2, c3 = st.columns(3)
    c1.metric("Target Titles", target_titles[:40] + ("..." if len(target_titles) > 40 else ""))
    c2.metric("Locations", preferred_locations[:40] + ("..." if len(preferred_locations) > 40 else ""))
    c3.metric("Remote Only", "Yes" if remote_only else "No")

    st.info("Next, go to Pipeline and run your first Find and Add Jobs workflow.")

    c1, c2 = st.columns([1.2, 1])

    with c1:
        if st.button("Go to Pipeline", type="primary", use_container_width=True, key="wizard_go_pipeline"):
            _complete_and_go_to_pipeline()
            st.rerun()

    with c2:
        if st.button("Finish for Now", use_container_width=True, key="wizard_finish_for_now"):
            _skip_to_app()
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
    elif current_step == "Search Criteria":
        _render_search_step()
    elif current_step == "Profile Context":
        _render_profile_step()
    elif current_step == "OpenAI API":
        _render_openai_step()
    else:
        _render_ready_step(load_settings())

    _render_shell_close()
