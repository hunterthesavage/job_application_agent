from pathlib import Path
import os
import subprocess

import streamlit as st

from config import APP_NAME, APP_VERSION, BACKUPS_DIR, DATA_DIR, DATABASE_PATH, JOB_URLS_FILE, LOGS_DIR, MANUAL_URLS_FILE, OPENAI_API_KEY_FILE, PROJECT_ROOT
from services.backup import backup_database, restore_latest_backup
from services.health import run_health_check
from services.openai_key import (
    delete_saved_openai_api_key,
    get_effective_openai_api_key,
    get_openai_api_key_details,
    has_openai_api_key,
    load_saved_openai_api_key,
    mask_openai_api_key,
    save_openai_api_key,
)
from services.settings import DEFAULT_SETTINGS, load_settings, save_settings
from services.status import get_system_status
from ui.navigation import initialize_nav_state, render_button_nav


SETTINGS_NAV_OPTIONS = [
    "Configuration",
    "Profile Context",
    "OpenAI API",
]



FIT_OPTIONS = ["Any", "60", "70", "75", "80", "85", "90"]
PAGE_SIZE_OPTIONS = ["5", "10", "20", "500"]
NEW_ROLES_SORT_OPTIONS = [
    "Newest First",
    "Highest Fit Score",
    "Highest Compensation",
    "Highest Source Trust",
    "Company A-Z",
]


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

    if "settings_openai_api_key_value" not in st.session_state:
        st.session_state["settings_openai_api_key_value"] = load_saved_openai_api_key()


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


def _label_from_health_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"ok", "healthy", "ready", "pass", "passed"}:
        return "Ready"
    if normalized in {"warning", "warn", "degraded"}:
        return "Warning"
    if normalized in {"error", "failed", "fail", "unhealthy"}:
        return "Needs Attention"
    return "Unknown"


def _badge_for_check_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"ok", "healthy", "ready", "pass", "passed"}:
        return "✅"
    if normalized in {"warning", "warn", "degraded"}:
        return "⚠️"
    if normalized in {"error", "failed", "fail", "unhealthy"}:
        return "❌"
    return "•"


def _render_health_check_result(result: dict) -> None:
    status_label = _label_from_health_status(result.get("status", ""))
    status_value = str(result.get("status", "") or "").strip().lower()

    if status_value in {"ok", "healthy", "ready", "pass", "passed"}:
        st.success("Health Check: Ready")
    elif status_value in {"warning", "warn", "degraded"}:
        st.warning("Health Check: Warning")
    else:
        st.error("Health Check: Needs Attention")

    st.markdown("#### Health Check Summary")

    checks = result.get("checks", {}) if isinstance(result.get("checks", {}), dict) else {}
    issues = result.get("issues", []) if isinstance(result.get("issues", []), list) else []
    errors = result.get("errors", []) if isinstance(result.get("errors", []), list) else []

    ready_count = 0
    warning_count = 0
    error_count = 0
    for item in checks.values():
        item_status = str((item or {}).get("status", "") if isinstance(item, dict) else "").strip().lower()
        if item_status in {"ok", "healthy", "ready", "pass", "passed"}:
            ready_count += 1
        elif item_status in {"warning", "warn", "degraded"}:
            warning_count += 1
        elif item_status in {"error", "failed", "fail", "unhealthy"}:
            error_count += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Status", status_label)
    c2.metric("Ready", ready_count)
    c3.metric("Warnings", warning_count)
    c4.metric("Errors", error_count)

    if issues:
        st.markdown("**What needs attention**")
        for item in issues:
            st.write(f"- {item}")

    if errors:
        st.markdown("**Errors**")
        for item in errors:
            st.write(f"- {item}")

    if checks:
        st.markdown("**Check Results**")
        for _, value in checks.items():
            if isinstance(value, dict):
                pretty_key = str(value.get("label", "Check")).strip() or "Check"
                item_status = str(value.get("status", "")).strip().lower()
                message = str(value.get("message", "")).strip()
                badge = _badge_for_check_status(item_status)
                if message:
                    st.write(f"- {badge} **{pretty_key}**: {message}")
                else:
                    st.write(f"- {badge} **{pretty_key}**")
            else:
                st.write(f"- • {value}")

    with st.expander("Technical details", expanded=False):
        st.json(result)



def _safe_unlink(path: Path, removed: list[str], failed: list[str]) -> None:
    try:
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(str(path))
    except Exception as exc:
        failed.append(f"{path}: {exc}")


def _clear_directory_contents(directory: Path, removed: list[str], failed: list[str]) -> None:
    try:
        if not directory.exists():
            return
        for child in directory.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_file() or child.is_symlink():
                try:
                    child.unlink()
                    removed.append(str(child))
                except Exception as exc:
                    failed.append(f"{child}: {exc}")
            elif child.is_dir():
                try:
                    import shutil
                    shutil.rmtree(child)
                    removed.append(str(child))
                except Exception as exc:
                    failed.append(f"{child}: {exc}")
    except Exception as exc:
        failed.append(f"{directory}: {exc}")


def _reset_app_data() -> tuple[list[str], list[str]]:
    removed: list[str] = []
    failed: list[str] = []

    targets = [
        DATABASE_PATH,
        OPENAI_API_KEY_FILE,
        DATA_DIR / "openai_api_key.meta.json",
        DATA_DIR / "openai_api_state.json",
        JOB_URLS_FILE,
        MANUAL_URLS_FILE,
        PROJECT_ROOT / "runtime_settings.json",
    ]

    for target in targets:
        _safe_unlink(Path(target), removed, failed)

    _clear_directory_contents(BACKUPS_DIR, removed, failed)
    _clear_directory_contents(LOGS_DIR, removed, failed)
    _clear_directory_contents(DATA_DIR, removed, failed)

    return removed, failed


def _render_reset_app_section() -> None:
    st.markdown("---")
    st.markdown("### Reset App / Remove All Data")
    st.warning(
        "This will remove local app data and restart the product as if it were opened for the first time on this machine. "
        "That includes your local database, saved settings, saved OpenAI key, manual URL lists, logs, and backups."
    )
    st.caption("This does not delete the source code. It resets the local app state and sends you back to Setup Wizard.")

    confirm_value = st.text_input(
        "Type RESET to confirm",
        key="settings_reset_app_confirmation",
        help="This action is destructive and cannot be undone.",
    )

    reset_disabled = str(confirm_value or "").strip() != "RESET"

    if st.button(
        "Reset App / Remove All Data",
        type="secondary",
        use_container_width=False,
        disabled=reset_disabled,
        key="settings_reset_app_button",
    ):
        removed, failed = _reset_app_data()

        st.cache_data.clear()

        for key in list(st.session_state.keys()):
            if key.startswith("wizard_") or key.startswith("settings_"):
                st.session_state.pop(key, None)

        st.session_state["_app_initialized"] = False
        st.session_state["_wizard_run_discovery_on_load"] = False
        st.session_state["top_nav_selection"] = "New Roles"
        st.session_state["settings_subnav_selection"] = "Configuration"
        st.session_state["reset_notice"] = {
            "removed_count": len(removed),
            "failed_count": len(failed),
        }

        if failed:
            st.session_state["reset_notice_details"] = failed
        else:
            st.session_state.pop("reset_notice_details", None)

        st.rerun()


def _render_reset_notice() -> None:
    notice = st.session_state.pop("reset_notice", None)
    if not isinstance(notice, dict):
        return

    removed_count = int(notice.get("removed_count", 0) or 0)
    failed_count = int(notice.get("failed_count", 0) or 0)

    if failed_count:
        st.warning(
            f"App reset completed with some cleanup issues. Removed {removed_count} item(s), with {failed_count} item(s) needing manual review."
        )
        details = st.session_state.pop("reset_notice_details", [])
        if details:
            with st.expander("Reset details", expanded=False):
                for item in details:
                    st.write(f"- {item}")
    else:
        st.success(f"App reset complete. Removed {removed_count} local item(s). Setup Wizard is ready again.")


def render_system_status() -> None:
    status = get_system_status()

    st.markdown("### System Status")
    st.caption(f"{APP_NAME} version {APP_VERSION}")
    st.caption(f"Database path: {DATABASE_PATH}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs", status["jobs_total"])
    c2.metric("New Roles", status["jobs_new"])
    c3.metric("Applied", status["jobs_applied"])
    c4.metric("Removed", status["removed_total"])

    st.markdown("#### Current App Status")
    st.write(f"- Latest backup: {status.get('latest_backup_path', '—')}")
    st.write(f"- OpenAI API key: {status.get('openai_api_key_status', 'Unknown')} | {status.get('openai_api_key_masked', 'Not saved')}")
    st.write(f"- Last cover letter: {status['last_cover_letter_path']}")
    st.write(f"- Last cover letter time: {status['last_cover_letter_at']}")
    st.write(f"- Last import: {status['last_import_at']}")
    st.write(f"- Last import status: {status['last_import_status']}")

    st.markdown("### Backup and Health Tools")
    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button("Create Backup", use_container_width=True, type="secondary"):
            try:
                with st.spinner("Creating backup..."):
                    backup_path = backup_database()

                st.success("Backup created.")
                st.text(str(backup_path))
                st.rerun()
            except Exception as exc:
                st.error("Backup failed.")
                st.text(str(exc))

    with b2:
        if st.button("Run Health Check", use_container_width=True, type="secondary"):
            with st.spinner("Running health check..."):
                result = run_health_check()

            st.session_state["settings_last_health_check_result"] = result
            st.rerun()

    with b3:
        if st.button("Restore Latest Backup", use_container_width=True, type="secondary"):
            try:
                with st.spinner("Restoring latest backup..."):
                    restored_from = restore_latest_backup()

                st.success("Latest backup restored.")
                st.text(str(restored_from))
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error("Restore failed.")
                st.text(str(exc))

    last_health_check_result = st.session_state.get("settings_last_health_check_result")
    if isinstance(last_health_check_result, dict):
        st.markdown("---")
        _render_health_check_result(last_health_check_result)


def render_configuration_tab(settings: dict[str, str]) -> None:
    render_system_status()
    st.markdown("---")
    st.markdown("### Cover Letter Output")

    folder_col, browse_col = st.columns([5, 1.2])

    with browse_col:
        st.markdown("<div style='height: 1.9rem;'></div>", unsafe_allow_html=True)
        browse_clicked = st.button(
            "Browse",
            use_container_width=True,
            key="browse_cover_letter_folder",
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

        d1, d2, d3 = st.columns(3)

        current_fit = str(settings.get("default_min_fit_score", "75"))
        if current_fit not in FIT_OPTIONS:
            current_fit = "75"

        current_page_size = str(settings.get("default_jobs_per_page", "10"))
        if current_page_size not in PAGE_SIZE_OPTIONS:
            current_page_size = "10"

        with d1:
            default_min_fit_score = st.selectbox(
                "Default Minimum Fit Score",
                FIT_OPTIONS,
                index=FIT_OPTIONS.index(current_fit),
            )

        current_new_roles_sort = str(settings.get("default_new_roles_sort", "Newest First"))
        if current_new_roles_sort not in NEW_ROLES_SORT_OPTIONS:
            current_new_roles_sort = "Newest First"

        with d2:
            default_jobs_per_page = st.selectbox(
                "Default Jobs Per Page",
                PAGE_SIZE_OPTIONS,
                index=PAGE_SIZE_OPTIONS.index(current_page_size),
            )

        with d3:
            default_new_roles_sort = st.selectbox(
                "Default New Roles Sort",
                NEW_ROLES_SORT_OPTIONS,
                index=NEW_ROLES_SORT_OPTIONS.index(current_new_roles_sort),
                help="Controls the default sort used when you open New Roles.",
            )

        save_main = st.form_submit_button("Save Configuration", type="primary", use_container_width=False)

        if save_main:
            with st.spinner("Saving configuration..."):
                save_settings(
                    {
                        "default_min_fit_score": str(default_min_fit_score),
                        "default_jobs_per_page": str(default_jobs_per_page),
                        "default_new_roles_sort": str(default_new_roles_sort),
                    }
                )

                apply_configuration_defaults_to_session(
                    default_min_fit_score=str(default_min_fit_score),
                    default_jobs_per_page=str(default_jobs_per_page),
                )

            st.success("Configuration saved.")
            st.rerun()

    _render_reset_app_section()


def render_profile_context_tab(settings: dict[str, str]) -> None:
    with st.form("settings_profile_context_form"):
        st.markdown("### Profile Context")

        resume_text = st.text_area(
            "Resume Text",
            value=settings.get("resume_text", ""),
            height=240,
            help="Paste resume text here so the agent can better tailor cover letters and fit scoring.",
        )

        profile_summary = st.text_area(
            "Executive Summary",
            value=settings.get("profile_summary", ""),
            height=140,
            help="Short bio or leadership summary to influence cover letter tone and framing.",
        )

        strengths_to_highlight = st.text_area(
            "Strengths to Highlight",
            value=settings.get("strengths_to_highlight", ""),
            height=140,
            help="Examples: AI transformation, enterprise IT leadership, ServiceNow, operational excellence.",
        )

        cover_letter_voice = st.text_area(
            "Cover Letter Voice",
            value=settings.get("cover_letter_voice", ""),
            height=120,
            help="Describe how you want cover letters to sound.",
        )

        save_profile = st.form_submit_button("Save Profile Context", type="primary", use_container_width=False)

        if save_profile:
            save_settings(
                {
                    "resume_text": resume_text,
                    "profile_summary": profile_summary,
                    "strengths_to_highlight": strengths_to_highlight,
                    "cover_letter_voice": cover_letter_voice,
                }
            )
            st.success("Profile context saved.")
            st.rerun()


def render_openai_api_tab() -> None:
    st.markdown("### OpenAI API")
    st.caption("Add the API key used for cover letter generation. The app uses a saved local key first and falls back to OPENAI_API_KEY from the environment.")

    st.markdown("Create or manage your API key here: [OpenAI API keys](https://platform.openai.com/api-keys)")
    st.markdown("Check billing or credits here: [OpenAI Billing](https://platform.openai.com/settings/organization/billing/overview)")
    st.markdown("Reference: [Where do I find my OpenAI API key?](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key)")

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
    else:
        st.info("No OpenAI API key is configured yet. Save a local key below or provide OPENAI_API_KEY in the environment.")

    if "settings_openai_api_key_value" not in st.session_state:
        st.session_state["settings_openai_api_key_value"] = load_saved_openai_api_key()

    st.markdown("---")

    st.text_input(
        "OpenAI API Key",
        key="settings_openai_api_key_value",
        type="password",
        help="Paste the API key you want to save locally for this machine.",
    )

    action_col_1, action_col_2 = st.columns(2)

    with action_col_1:
        if st.button("Save API Key", use_container_width=True, type="primary", key="save_openai_api_key_button"):
            try:
                saved_path = save_openai_api_key(st.session_state.get("settings_openai_api_key_value", ""))
                st.success(f"Saved API key locally: {saved_path}")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save API key: {exc}")

    with action_col_2:
        if st.button(
            "Delete Saved API Key",
            use_container_width=True,
            type="secondary",
            key="delete_saved_openai_api_key_button",
            disabled=not bool(details["saved_key_present"]),
        ):
            try:
                delete_saved_openai_api_key()
                st.session_state["settings_openai_api_key_value"] = ""
                st.success("Deleted saved local API key.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to delete saved API key: {exc}")

    with st.expander("Advanced key diagnostics"):
        st.markdown(f"**Saved local key present:** {'Yes' if details['saved_key_present'] else 'No'}")
        st.markdown(f"**Environment key present:** {'Yes' if details['environment_key_present'] else 'No'}")
        st.markdown(f"**Saved local key:** `{details['saved_key_masked']}`")
        st.markdown(f"**Environment key:** `{details['environment_key_masked']}`")
        st.markdown("**Precedence:** Saved local key overrides the environment key when both are present.")
        st.caption(f"Saved file path: {details['saved_file_path']}")

def render_settings() -> None:
    st.subheader("Settings")

    _render_reset_notice()

    settings = load_settings()
    initialize_settings_state(settings)
    initialize_nav_state("settings_subnav_selection", "Configuration")

    st.caption("Settings sections")
    selected_section = render_button_nav(
        selected_button_type="tertiary",
        options=SETTINGS_NAV_OPTIONS,
        state_key="settings_subnav_selection",
        key_prefix="settings_subnav",
    )
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

    if selected_section == "Configuration":
        render_configuration_tab(settings)
    elif selected_section == "Profile Context":
        render_profile_context_tab(settings)
    else:
        render_openai_api_tab()
