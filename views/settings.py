from datetime import datetime
from pathlib import Path
import subprocess

import streamlit as st

from config import DATABASE_PATH, OPENAI_API_KEY_FILE
from services.backup import backup_database, restore_latest_backup
from services.health import run_health_check
from services.openai_key import (
    delete_saved_openai_api_key,
    get_openai_validation_status,
    load_saved_openai_api_key,
    mask_openai_api_key,
    save_openai_api_key,
    validate_openai_api_key,
)
from services.settings import DEFAULT_SETTINGS, load_settings, save_settings
from services.status import get_system_status
from services.ui_busy import (
    app_is_busy,
    clear_action,
    get_action,
    move_action_to_execute,
    queue_action,
    stop_busy,
)


FIT_OPTIONS = ["Any", "60", "70", "75", "80", "85", "90"]
PAGE_SIZE_OPTIONS = ["5", "10", "20", "500"]

CONFIG_SAVED_KEY = "configuration_last_saved_at"
SEARCH_SAVED_KEY = "search_criteria_last_saved_at"
PROFILE_SAVED_KEY = "profile_context_last_saved_at"
OPENAI_SAVED_KEY = "openai_api_key_last_saved_at"


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")


def format_saved_timestamp(value: str) -> str:
    text = str(value or "").strip()
    return text if text else "Not saved yet"


def set_flash_message(section: str, level: str, message: str) -> None:
    st.session_state[f"{section}_flash_level"] = level
    st.session_state[f"{section}_flash_message"] = message


def render_flash_message(section: str) -> None:
    message = st.session_state.pop(f"{section}_flash_message", "")
    level = st.session_state.pop(f"{section}_flash_level", "success")

    if not message:
        return

    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.success(message)


def _process_pending_action_before_render() -> None:
    action = get_action("settings")
    if not action or action.get("phase") != "execute":
        return

    try:
        action_type = action.get("type")
        label = action.get("label", "Working")

        with st.spinner(f"{label}..."):
            if action_type == "create_backup":
                backup_path = backup_database()
                set_flash_message("health_status", "success", f"✓ Backup created: {backup_path}")

            elif action_type == "run_health_check":
                result = run_health_check()
                st.session_state["settings_last_health_check_result"] = result
                if result["status"] == "ok":
                    set_flash_message("health_status", "success", "✓ Health check passed")
                else:
                    set_flash_message("health_status", "warning", "Health check found issues")

            elif action_type == "restore_latest_backup":
                restored_from = restore_latest_backup()
                st.cache_data.clear()
                set_flash_message("health_status", "success", f"✓ Latest backup restored: {restored_from}")

    except Exception as exc:
        set_flash_message("health_status", "error", f"Action failed: {exc}")
    finally:
        clear_action("settings")
        stop_busy()
        st.rerun()


def _advance_pending_action_after_render() -> None:
    action = get_action("settings")
    if action and action.get("phase") == "prepare":
        move_action_to_execute("settings")
        st.rerun()


def str_to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def pick_folder_dialog(initial_path: str) -> str:
    start_path = str(Path(initial_path).expanduser()) if initial_path else str(Path.home())

    script = f'''
set startFolder to POSIX file "{start_path}" as alias
try
    set chosenFolder to choose folder with prompt "Select Cover Letter Output Folder" default location startFolder
on error
    set chosenFolder to choose folder with prompt "Select Cover Letter Output Folder"
end try
POSIX path of chosenFolder
'''.strip()

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            selected = result.stdout.strip()
            if selected:
                return selected

        stderr_text = (result.stderr or "").strip()
        if stderr_text and "User canceled" not in stderr_text:
            st.warning(f"Could not open folder picker: {stderr_text}")
    except Exception as exc:
        st.warning(f"Could not open folder picker: {exc}")

    return initial_path


def save_cover_letter_output_settings(folder_value: str, pattern_value: str) -> None:
    save_settings(
        {
            "cover_letter_output_folder": str(folder_value).strip(),
            "cover_letter_filename_pattern": str(pattern_value).strip(),
        }
    )


def handle_cover_letter_folder_change() -> None:
    folder_value = st.session_state.get(
        "settings_cover_letter_output_folder_value",
        DEFAULT_SETTINGS["cover_letter_output_folder"],
    )
    pattern_value = st.session_state.get(
        "settings_cover_letter_filename_pattern_value",
        DEFAULT_SETTINGS["cover_letter_filename_pattern"],
    )

    try:
        save_cover_letter_output_settings(folder_value, pattern_value)
        st.session_state["cover_letter_output_settings_saved_message"] = "Cover letter output folder saved."
    except Exception as exc:
        st.session_state["cover_letter_output_settings_saved_message"] = f"Failed to save folder: {exc}"


def handle_cover_letter_pattern_change() -> None:
    folder_value = st.session_state.get(
        "settings_cover_letter_output_folder_value",
        DEFAULT_SETTINGS["cover_letter_output_folder"],
    )
    pattern_value = st.session_state.get(
        "settings_cover_letter_filename_pattern_value",
        DEFAULT_SETTINGS["cover_letter_filename_pattern"],
    )

    try:
        save_cover_letter_output_settings(folder_value, pattern_value)
        st.session_state["cover_letter_output_settings_saved_message"] = "Cover letter filename pattern saved."
    except Exception as exc:
        st.session_state["cover_letter_output_settings_saved_message"] = f"Failed to save filename pattern: {exc}"


def initialize_settings_state(settings: dict[str, str]) -> None:
    if "settings_cover_letter_output_folder_value" not in st.session_state:
        st.session_state["settings_cover_letter_output_folder_value"] = settings.get(
            "cover_letter_output_folder",
            DEFAULT_SETTINGS["cover_letter_output_folder"],
        )

    if "settings_cover_letter_filename_pattern_value" not in st.session_state:
        st.session_state["settings_cover_letter_filename_pattern_value"] = settings.get(
            "cover_letter_filename_pattern",
            DEFAULT_SETTINGS["cover_letter_filename_pattern"],
        )

    if "configuration_widget_nonce" not in st.session_state:
        st.session_state["configuration_widget_nonce"] = 0


def apply_configuration_defaults_to_session(
    default_min_fit_score: str,
    default_jobs_per_page: str,
) -> None:
    fit_value = "Any"
    if str(default_min_fit_score) != "Any":
        try:
            fit_value = int(default_min_fit_score)
        except Exception:
            fit_value = "Any"

    try:
        page_size_value = int(default_jobs_per_page)
    except Exception:
        page_size_value = 10

    st.session_state["filter_min_fit"] = fit_value
    st.session_state["new_roles_page_size"] = page_size_value
    st.session_state["new_roles_current_page"] = 1
    st.session_state["applied_roles_page_size"] = page_size_value
    st.session_state["applied_roles_current_page"] = 1

    st.session_state["configuration_widget_nonce"] = int(
        st.session_state.get("configuration_widget_nonce", 0)
    ) + 1


def render_health_status_tab() -> None:
    status = get_system_status()

    st.markdown("### System Status")
    st.caption(f"Database path: {DATABASE_PATH}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs", status["jobs_total"])
    c2.metric("New Roles", status["jobs_new"])
    c3.metric("Applied", status["jobs_applied"])
    c4.metric("Removed", status["removed_total"])

    st.caption(f"Latest backup: {status.get('latest_backup_path', '—')}")
    st.caption(
        f"OpenAI API key: {status.get('openai_api_key_status', 'Unknown')} | "
        f"{status.get('openai_api_key_masked', 'Not saved')} | "
        f"Last validated: {status.get('openai_api_key_last_validated_at', '—')}"
    )
    st.caption(f"Last cover letter: {status['last_cover_letter_path']}")
    st.caption(f"Last cover letter time: {status['last_cover_letter_at']}")
    st.caption(f"Last import: {status['last_import_at']} | status: {status['last_import_status']}")

    st.markdown("---")
    st.markdown("### Backup and Health Tools")

    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button("Create Backup", use_container_width=True, type="secondary", disabled=app_is_busy()):
            queue_action("settings", "create_backup", {}, "Creating backup")
            st.rerun()

    with b2:
        if st.button("Run Health Check", use_container_width=True, type="secondary", disabled=app_is_busy()):
            queue_action("settings", "run_health_check", {}, "Running health check")
            st.rerun()

    with b3:
        if st.button("Restore Latest Backup", use_container_width=True, type="secondary", disabled=app_is_busy()):
            queue_action("settings", "restore_latest_backup", {}, "Restoring latest backup")
            st.rerun()

    render_flash_message("health_status")

    result = st.session_state.get("settings_last_health_check_result")
    if result:
        st.markdown("---")
        st.json(result)


def render_configuration_tab(settings: dict[str, str]) -> None:
    st.markdown("### Cover Letter Output")

    folder_col, browse_col = st.columns([5, 1.2])

    with browse_col:
        st.markdown("<div style='height: 1.9rem;'></div>", unsafe_allow_html=True)
        browse_clicked = st.button(
            "Browse",
            use_container_width=True,
            key="browse_cover_letter_folder",
            disabled=app_is_busy(),
        )

    if browse_clicked:
        current_folder = st.session_state.get(
            "settings_cover_letter_output_folder_value",
            DEFAULT_SETTINGS["cover_letter_output_folder"],
        )
        selected_folder = pick_folder_dialog(current_folder)
        st.session_state["settings_cover_letter_output_folder_value"] = selected_folder

        try:
            save_cover_letter_output_settings(
                st.session_state["settings_cover_letter_output_folder_value"],
                st.session_state["settings_cover_letter_filename_pattern_value"],
            )
            st.session_state["cover_letter_output_settings_saved_message"] = "Cover letter output folder saved."
        except Exception as exc:
            st.session_state["cover_letter_output_settings_saved_message"] = f"Failed to save folder: {exc}"

        st.rerun()

    with folder_col:
        st.text_input(
            "Cover Letter Output Folder",
            key="settings_cover_letter_output_folder_value",
            help="Folder where generated .txt cover letters will be saved.",
            on_change=handle_cover_letter_folder_change,
            disabled=app_is_busy(),
        )

    resolved_folder = Path(
        st.session_state.get(
            "settings_cover_letter_output_folder_value",
            DEFAULT_SETTINGS["cover_letter_output_folder"],
        )
    ).expanduser()
    st.caption(f"Resolved output path: {resolved_folder}")

    st.text_input(
        "Cover Letter Filename Pattern",
        key="settings_cover_letter_filename_pattern_value",
        help="Use placeholders like {company}, {title}, {date}. Example: CL_Hunter_Samuels_{company}.txt",
        on_change=handle_cover_letter_pattern_change,
        disabled=app_is_busy(),
    )

    st.caption("Available placeholders: {company}, {title}, {date}")

    saved_message = st.session_state.get("cover_letter_output_settings_saved_message", "")
    if saved_message:
        if saved_message.lower().startswith("failed"):
            st.error(saved_message)
        else:
            st.success(saved_message)

    with st.form("settings_configuration_form"):
        st.markdown("---")
        st.markdown("### Page Defaults")

        d1, d2 = st.columns(2)

        current_fit = str(settings.get("default_min_fit_score", "Any"))
        if current_fit not in FIT_OPTIONS:
            current_fit = "Any"

        current_page_size = str(settings.get("default_jobs_per_page", "10"))
        if current_page_size not in PAGE_SIZE_OPTIONS:
            current_page_size = "10"

        with d1:
            default_min_fit_score = st.selectbox(
                "Default Minimum Fit Score",
                FIT_OPTIONS,
                index=FIT_OPTIONS.index(current_fit),
                disabled=app_is_busy(),
            )

        with d2:
            default_jobs_per_page = st.selectbox(
                "Default Jobs Per Page",
                PAGE_SIZE_OPTIONS,
                index=PAGE_SIZE_OPTIONS.index(current_page_size),
                disabled=app_is_busy(),
            )

        save_main = st.form_submit_button("Save Configuration", type="primary", use_container_width=False, disabled=app_is_busy())

        if save_main:
            try:
                saved_at = now_timestamp()
                save_settings(
                    {
                        "default_min_fit_score": str(default_min_fit_score),
                        "default_jobs_per_page": str(default_jobs_per_page),
                        CONFIG_SAVED_KEY: saved_at,
                    }
                )

                apply_configuration_defaults_to_session(
                    default_min_fit_score=str(default_min_fit_score),
                    default_jobs_per_page=str(default_jobs_per_page),
                )

                set_flash_message("configuration", "success", "✓ Configuration saved")
                st.rerun()
            except Exception as exc:
                set_flash_message("configuration", "error", f"Configuration save failed: {exc}")
                st.rerun()

    render_flash_message("configuration")
    st.caption(f"Last saved: {format_saved_timestamp(load_settings().get(CONFIG_SAVED_KEY, ''))}")


def render_search_criteria_tab(settings: dict[str, str]) -> None:
    with st.form("settings_search_criteria_form"):
        st.markdown("### Search Criteria")

        c1, c2 = st.columns(2)

        with c1:
            target_titles = st.text_area(
                "Target Titles",
                value=settings.get("target_titles", ""),
                height=100,
                help="Comma-separated values",
                disabled=app_is_busy(),
            )
            preferred_locations = st.text_area(
                "Preferred Locations",
                value=settings.get("preferred_locations", ""),
                height=100,
                help="Comma-separated values",
                disabled=app_is_busy(),
            )
            include_keywords = st.text_area(
                "Include Keywords",
                value=settings.get("include_keywords", ""),
                height=100,
                help="Comma-separated values",
                disabled=app_is_busy(),
            )

        with c2:
            exclude_keywords = st.text_area(
                "Exclude Keywords",
                value=settings.get("exclude_keywords", ""),
                height=100,
                help="Comma-separated values",
                disabled=app_is_busy(),
            )
            remote_only = st.toggle(
                "Remote Only",
                value=str_to_bool(settings.get("remote_only", "false"), default=False),
                disabled=app_is_busy(),
            )
            minimum_compensation = st.text_input(
                "Minimum Compensation",
                value=settings.get("minimum_compensation", ""),
                disabled=app_is_busy(),
            )

        save_search = st.form_submit_button("Save Search Criteria", type="primary", use_container_width=False, disabled=app_is_busy())

        if save_search:
            try:
                saved_at = now_timestamp()
                save_settings(
                    {
                        "target_titles": target_titles,
                        "preferred_locations": preferred_locations,
                        "include_keywords": include_keywords,
                        "exclude_keywords": exclude_keywords,
                        "remote_only": "true" if remote_only else "false",
                        "minimum_compensation": minimum_compensation,
                        SEARCH_SAVED_KEY: saved_at,
                    }
                )
                set_flash_message("search", "success", "✓ Search criteria saved")
                st.rerun()
            except Exception as exc:
                set_flash_message("search", "error", f"Search criteria save failed: {exc}")
                st.rerun()

    render_flash_message("search")
    st.caption(f"Last saved: {format_saved_timestamp(load_settings().get(SEARCH_SAVED_KEY, ''))}")


def render_profile_context_tab(settings: dict[str, str]) -> None:
    with st.form("settings_profile_context_form"):
        st.markdown("### Profile Context")

        resume_text = st.text_area(
            "Resume Text",
            value=settings.get("resume_text", ""),
            height=240,
            help="Paste resume text here so the agent can better tailor cover letters and fit scoring.",
            disabled=app_is_busy(),
        )
        profile_summary = st.text_area(
            "Executive Summary",
            value=settings.get("profile_summary", ""),
            height=140,
            help="Short bio or leadership summary to influence cover letter tone and framing.",
            disabled=app_is_busy(),
        )
        strengths_to_highlight = st.text_area(
            "Strengths to Highlight",
            value=settings.get("strengths_to_highlight", ""),
            height=140,
            help="Examples: AI transformation, enterprise IT leadership, ServiceNow, operational excellence.",
            disabled=app_is_busy(),
        )
        cover_letter_voice = st.text_area(
            "Cover Letter Voice",
            value=settings.get("cover_letter_voice", ""),
            height=120,
            help="Describe how you want cover letters to sound.",
            disabled=app_is_busy(),
        )

        save_profile = st.form_submit_button("Save Profile Context", type="primary", use_container_width=False, disabled=app_is_busy())

        if save_profile:
            try:
                saved_at = now_timestamp()
                save_settings(
                    {
                        "resume_text": resume_text,
                        "profile_summary": profile_summary,
                        "strengths_to_highlight": strengths_to_highlight,
                        "cover_letter_voice": cover_letter_voice,
                        PROFILE_SAVED_KEY: saved_at,
                    }
                )
                set_flash_message("profile", "success", "✓ Profile context saved")
                st.rerun()
            except Exception as exc:
                set_flash_message("profile", "error", f"Profile context save failed: {exc}")
                st.rerun()

    render_flash_message("profile")
    st.caption(f"Last saved: {format_saved_timestamp(load_settings().get(PROFILE_SAVED_KEY, ''))}")


def render_openai_api_tab() -> None:
    st.markdown("### OpenAI API")
    st.caption("Save and validate the API key used for cover letter generation. The key is stored locally on this machine in a dedicated file.")

    st.markdown(
        """
Create or manage your API key here: [OpenAI API keys](https://platform.openai.com/api-keys)

Check billing or credits here: [OpenAI Billing](https://platform.openai.com/settings/organization/billing/overview)

The key must be saved and validated before the Cover Letter button becomes available.
        """
    )

    saved_key = load_saved_openai_api_key()
    validation = get_openai_validation_status()

    st.caption(f"Current saved key: {mask_openai_api_key(saved_key)}")
    st.caption(f"Validation status: {'Validated' if validation['validated'] == 'true' else 'Not validated'}")
    st.caption(f"Last validated: {validation['last_validated_at'] or '—'}")
    st.caption(f"Last saved: {format_saved_timestamp(load_settings().get(OPENAI_SAVED_KEY, ''))}")
    st.caption(f"Saved file path: {OPENAI_API_KEY_FILE}")

    with st.form("settings_openai_api_form"):
        api_key_value = st.text_area(
            "OpenAI API Key",
            value="",
            height=100,
            help="Paste your API key here. The app will not redisplay the raw saved value, only a masked preview above.",
            disabled=app_is_busy(),
        )

        c1, c2, c3 = st.columns(3)
        save_api = c1.form_submit_button("Save API Key", type="primary", use_container_width=True, disabled=app_is_busy())
        validate_api = c2.form_submit_button("Validate API Key", type="secondary", use_container_width=True, disabled=app_is_busy())
        delete_api = c3.form_submit_button("Delete Saved API Key", type="secondary", use_container_width=True, disabled=app_is_busy())

        if save_api:
            try:
                if not str(api_key_value).strip():
                    set_flash_message("openai", "error", "Paste an API key before saving.")
                    st.rerun()

                save_openai_api_key(api_key_value)
                save_settings({OPENAI_SAVED_KEY: now_timestamp()})
                set_flash_message("openai", "success", "✓ OpenAI API key saved")
                st.rerun()
            except Exception as exc:
                set_flash_message("openai", "error", f"Failed to save API key: {exc}")
                st.rerun()

        if validate_api:
            try:
                result = validate_openai_api_key()
                set_flash_message("openai", "success", f"✓ OpenAI API key validated at {result['validated_at']}")
                st.rerun()
            except Exception as exc:
                set_flash_message("openai", "error", f"API key validation failed: {exc}")
                st.rerun()

        if delete_api:
            try:
                delete_saved_openai_api_key()
                save_settings({OPENAI_SAVED_KEY: ""})
                set_flash_message("openai", "success", "✓ Saved OpenAI API key deleted")
                st.rerun()
            except Exception as exc:
                set_flash_message("openai", "error", f"Failed to delete saved API key: {exc}")
                st.rerun()

    render_flash_message("openai")


def render_settings() -> None:
    _process_pending_action_before_render()

    st.subheader("Settings")

    settings = load_settings()
    initialize_settings_state(settings)

    tab_configuration, tab_search, tab_profile, tab_openai, tab_health = st.tabs(
        ["Configuration", "Search Criteria", "Profile Context", "OpenAI API", "Health/Status"]
    )

    with tab_configuration:
        render_configuration_tab(settings)

    with tab_search:
        render_search_criteria_tab(settings)

    with tab_profile:
        render_profile_context_tab(settings)

    with tab_openai:
        render_openai_api_tab()

    with tab_health:
        render_health_status_tab()

    _advance_pending_action_after_render()
