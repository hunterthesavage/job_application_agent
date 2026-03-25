import html
from pathlib import Path
import os
import subprocess

import streamlit as st

from config import APP_NAME, APP_VERSION, BACKUPS_DIR, DATA_DIR, DATABASE_PATH, JOB_URLS_FILE, LOGS_DIR, MANUAL_URLS_FILE, OPENAI_API_KEY_FILE, PROJECT_ROOT
from services.backlog import get_backlog_summary
from services.backup import backup_database, restore_latest_backup
from services.health import run_health_check
from services.job_levels import (
    JOB_LEVEL_OPTIONS,
    parse_preferred_job_levels,
    serialize_preferred_job_levels,
)
from services.openai_key import (
    delete_saved_openai_api_key,
    get_effective_openai_api_key,
    get_openai_api_key_details,
    has_openai_api_key,
    load_saved_openai_api_key,
    mask_openai_api_key,
    save_openai_api_key,
)
from services.profile_context_templates import generate_profile_context_from_resume
from services.settings import DEFAULT_SETTINGS, load_settings, save_settings
from services.status import get_system_status
from ui.navigation import initialize_nav_state, render_button_nav


SETTINGS_NAV_OPTIONS = [
    "Configuration",
    "Profile Context",
    "OpenAI API",
    "System Status",
]

STATUS_NAV_OPTIONS = [
    "Overview",
    "Backlog",
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


def _inject_settings_css() -> None:
    st.markdown(
        """
        <style>
            .settings-step-heading {
                display: flex;
                align-items: center;
                gap: 0.7rem;
                margin-top: 0.9rem;
                margin-bottom: 0.45rem;
            }

            .settings-step-badge {
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

            .settings-step-title {
                font-size: 1.15rem;
                font-weight: 820;
                color: rgba(255,255,255,0.98);
                letter-spacing: -0.02em;
            }

            .settings-backlog-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.9rem;
                margin-bottom: 1rem;
            }

            .settings-backlog-card {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 22px;
                background: linear-gradient(180deg, rgba(16,22,36,0.96) 0%, rgba(10,14,24,0.98) 100%);
                box-shadow: 0 18px 48px rgba(0,0,0,0.24);
                padding: 1rem 1rem 0.85rem 1rem;
                height: 100%;
            }

            .settings-backlog-card.high {
                background:
                    radial-gradient(circle at top right, rgba(248,113,113,0.13), transparent 28%),
                    linear-gradient(180deg, rgba(20,18,28,0.97) 0%, rgba(12,12,20,0.99) 100%);
            }

            .settings-backlog-card.medium {
                background:
                    radial-gradient(circle at top right, rgba(250,204,21,0.13), transparent 28%),
                    linear-gradient(180deg, rgba(20,20,28,0.97) 0%, rgba(12,12,20,0.99) 100%);
            }

            .settings-backlog-card.low {
                background:
                    radial-gradient(circle at top right, rgba(96,165,250,0.13), transparent 28%),
                    linear-gradient(180deg, rgba(16,22,36,0.97) 0%, rgba(10,14,24,0.99) 100%);
            }

            .settings-backlog-kicker {
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.09em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.62);
                margin-bottom: 0.3rem;
            }

            .settings-backlog-count {
                font-size: 2rem;
                font-weight: 840;
                line-height: 1;
                color: rgba(255,255,255,0.98);
                letter-spacing: -0.03em;
                margin-bottom: 0.25rem;
            }

            .settings-backlog-copy {
                font-size: 0.9rem;
                line-height: 1.45;
                color: rgba(255,255,255,0.72);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_settings_step_heading(step: str, title: str) -> None:
    markup = (
        '<div class="settings-step-heading">'
        f'<span class="settings-step-badge">{html.escape(step)}</span>'
        f'<div class="settings-step-title">{html.escape(title)}</div>'
        '</div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


def str_to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def pick_folder_dialog(initial_path: str) -> str:
    start_path = str(Path(initial_path).expanduser()) if initial_path else str(Path.home())

    if os.name == "nt":
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(
                initialdir=start_path,
                title="Select Cover Letter Output Folder",
                mustexist=False,
            )
            root.destroy()
            if selected:
                return selected
            return initial_path
        except Exception as exc:
            st.session_state["cover_letter_output_settings_saved_message"] = (
                f"Could not open folder picker: {exc}"
            )
            return initial_path

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
            st.session_state["cover_letter_output_settings_saved_message"] = (
                f"Could not open folder picker: {stderr_text}"
            )
    except Exception as exc:
        st.session_state["cover_letter_output_settings_saved_message"] = (
            f"Could not open folder picker: {exc}"
        )

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
    saved_cover_letter_folder = settings.get(
        "cover_letter_output_folder",
        DEFAULT_SETTINGS["cover_letter_output_folder"],
    )
    saved_cover_letter_pattern = settings.get(
        "cover_letter_filename_pattern",
        DEFAULT_SETTINGS["cover_letter_filename_pattern"],
    )

    if "settings_cover_letter_output_folder_value" not in st.session_state:
        st.session_state["settings_cover_letter_output_folder_value"] = saved_cover_letter_folder
    else:
        current_folder_value = str(st.session_state.get("settings_cover_letter_output_folder_value", "") or "").strip()
        last_loaded_folder = str(st.session_state.get("_settings_cover_letter_output_folder_loaded", "") or "").strip()
        if saved_cover_letter_folder and (not current_folder_value or current_folder_value == last_loaded_folder):
            st.session_state["settings_cover_letter_output_folder_value"] = saved_cover_letter_folder
    st.session_state["_settings_cover_letter_output_folder_loaded"] = saved_cover_letter_folder

    if "settings_cover_letter_filename_pattern_value" not in st.session_state:
        st.session_state["settings_cover_letter_filename_pattern_value"] = saved_cover_letter_pattern
    else:
        current_pattern_value = str(st.session_state.get("settings_cover_letter_filename_pattern_value", "") or "").strip()
        last_loaded_pattern = str(st.session_state.get("_settings_cover_letter_filename_pattern_loaded", "") or "").strip()
        if saved_cover_letter_pattern and (not current_pattern_value or current_pattern_value == last_loaded_pattern):
            st.session_state["settings_cover_letter_filename_pattern_value"] = saved_cover_letter_pattern
    st.session_state["_settings_cover_letter_filename_pattern_loaded"] = saved_cover_letter_pattern

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


def _render_status_overview() -> None:
    status = get_system_status()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs", status["jobs_total"])
    c2.metric("New Roles", status["jobs_new"])
    c3.metric("Applied", status["jobs_applied"])
    c4.metric("Removed", status["removed_total"])

    st.markdown("#### App Status")
    st.write(f"- Latest backup: {status.get('latest_backup_path', '—')}")
    st.write(
        f"- OpenAI API key: {status.get('openai_api_key_status', 'Unknown')} | "
        f"{status.get('openai_api_key_source', 'Unknown source')} | "
        f"{status.get('openai_api_key_masked', 'Not saved')}"
    )
    st.write(f"- Last cover letter: {status['last_cover_letter_path']}")
    st.write(f"- Last cover letter time: {status['last_cover_letter_at']}")
    st.write(f"- Last import: {status['last_import_at']}")
    st.write(f"- Last import status: {status['last_import_status']}")

    st.markdown("#### Health Status")
    st.caption("Run this when you want to confirm the local install is healthy before sharing it or troubleshooting it.")

    st.markdown("### Backup and Maintenance")
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

    _render_reset_app_section()


def _render_backlog_priority_card(priority: str, count: int, copy: str) -> str:
    priority_class = priority.strip().lower()
    return (
        f'<div class="settings-backlog-card {priority_class}">'
        f'<div class="settings-backlog-kicker">{html.escape(priority)} priority</div>'
        f'<div class="settings-backlog-count">{count}</div>'
        f'<div class="settings-backlog-copy">{html.escape(copy)}</div>'
        '</div>'
    )


def _render_status_backlog() -> None:
    summary = get_backlog_summary()
    counts = summary.get("counts", {}) or {}
    items_by_priority = summary.get("items_by_priority", {}) or {}
    recently_completed = summary.get("recently_completed", []) or []
    percent = int(summary.get("soft_launch_percent", 0) or 0)

    st.markdown("### Backlog")
    st.caption("This is the current launch-focused backlog based on what has already shipped, what still needs validation, and what can safely wait.")

    progress_left, progress_right = st.columns([1.15, 2.2])
    with progress_left:
        st.metric("Soft Launch Progress", f"{percent}%")
    with progress_right:
        st.info(
            "The goal is to finish validation and launch hardening first. "
            "High-priority items should move before new feature expansion."
        )

    card_markup = (
        '<div class="settings-backlog-grid">'
        + _render_backlog_priority_card(
            "High",
            int(counts.get("High", 0) or 0),
            "Launch blockers or validation gaps that should move before broader sharing.",
        )
        + _render_backlog_priority_card(
            "Medium",
            int(counts.get("Medium", 0) or 0),
            "Important usability and architecture cleanup that improves trust but does not block testing today.",
        )
        + _render_backlog_priority_card(
            "Low",
            int(counts.get("Low", 0) or 0),
            "Useful cleanup and longer-horizon work that can wait until after soft launch feedback.",
        )
        + '</div>'
    )
    st.markdown(card_markup, unsafe_allow_html=True)

    for priority in ("High", "Medium", "Low"):
        items = items_by_priority.get(priority, []) or []
        with st.expander(f"{priority} Priority ({len(items)})", expanded=(priority == "High")):
            for item in items:
                st.markdown(f"**{item.get('title', 'Backlog item')}**")
                st.write(str(item.get("detail", "") or ""))

    if recently_completed:
        with st.expander("Recently completed", expanded=False):
            for item in recently_completed:
                st.write(f"- {item}")


def render_system_status_tab() -> None:
    _inject_settings_css()
    initialize_nav_state("settings_status_subnav_selection", "Overview")

    st.markdown("### System Status")
    st.caption("Use this area for maintenance, local app health, and launch tracking.")
    st.caption(f"{APP_NAME} version {APP_VERSION}")
    st.caption(f"Database path: {DATABASE_PATH}")

    selected_status_section = render_button_nav(
        options=STATUS_NAV_OPTIONS,
        state_key="settings_status_subnav_selection",
        key_prefix="settings_status_subnav",
        selected_button_type="tertiary",
    )
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

    if selected_status_section == "Backlog":
        _render_status_backlog()
    else:
        _render_status_overview()


def render_configuration_tab(settings: dict[str, str]) -> None:
    st.markdown("### Cover Letter Output")
    st.caption("This only affects generated cover letters. Discovery and AI scoring still work without it.")

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
    if not resolved_folder.exists():
        st.info("Set this before generating letters. It is not required for discovery or scoring.")

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

        st.markdown("---")
        st.markdown("### AI Scoring Preferences")

        preferred_job_levels = st.multiselect(
            "Preferred Job Levels",
            options=JOB_LEVEL_OPTIONS,
            default=parse_preferred_job_levels(settings.get("preferred_job_levels", "")),
            help="AI scoring will penalize jobs whose title level falls below the levels you select here.",
        )

        save_main = st.form_submit_button("Save Configuration", type="primary", use_container_width=False)

        if save_main:
            with st.spinner("Saving configuration..."):
                save_settings(
                    {
                        "default_min_fit_score": str(default_min_fit_score),
                        "default_jobs_per_page": str(default_jobs_per_page),
                        "default_new_roles_sort": str(default_new_roles_sort),
                        "preferred_job_levels": serialize_preferred_job_levels(preferred_job_levels),
                    }
                )

                apply_configuration_defaults_to_session(
                    default_min_fit_score=str(default_min_fit_score),
                    default_jobs_per_page=str(default_jobs_per_page),
                )

            st.success("Configuration saved.")
            st.rerun()

def render_profile_context_tab(settings: dict[str, str]) -> None:
    _inject_settings_css()

    if "settings_resume_text_value" not in st.session_state:
        st.session_state["settings_resume_text_value"] = settings.get("resume_text", "")
    if "settings_profile_summary_value" not in st.session_state:
        st.session_state["settings_profile_summary_value"] = settings.get("profile_summary", "")
    if "settings_strengths_to_highlight_value" not in st.session_state:
        st.session_state["settings_strengths_to_highlight_value"] = settings.get("strengths_to_highlight", "")
    if "settings_cover_letter_voice_value" not in st.session_state:
        st.session_state["settings_cover_letter_voice_value"] = settings.get("cover_letter_voice", "")

    st.markdown("### Profile Context")
    st.caption(
        "This is the primary candidate context used by AI scoring. If this is blank, discovery can still run, but accepted jobs will skip AI scoring unless a fallback profile file exists."
    )

    resume_present = bool(str(st.session_state.get("settings_resume_text_value", "") or "").strip())
    api_key_present = bool(get_effective_openai_api_key())
    can_generate = resume_present and api_key_present

    current_resume_text = str(st.session_state.get("settings_resume_text_value", "") or "")
    current_profile_summary = str(st.session_state.get("settings_profile_summary_value", "") or "")
    current_strengths = str(st.session_state.get("settings_strengths_to_highlight_value", "") or "")
    current_cover_letter_voice = str(st.session_state.get("settings_cover_letter_voice_value", "") or "")

    saved_resume_text = str(settings.get("resume_text", "") or "")
    saved_profile_summary = str(settings.get("profile_summary", "") or "")
    saved_strengths = str(settings.get("strengths_to_highlight", "") or "")
    saved_cover_letter_voice = str(settings.get("cover_letter_voice", "") or "")

    has_unsaved_changes = any(
        [
            current_resume_text != saved_resume_text,
            current_profile_summary != saved_profile_summary,
            current_strengths != saved_strengths,
            current_cover_letter_voice != saved_cover_letter_voice,
        ]
    )

    _render_settings_step_heading("1", "Paste Resume")
    resume_text = st.text_area(
        "Paste Resume",
        key="settings_resume_text_value",
        height=240,
        help="Primary source for AI scoring. Paste resume text here so scoring can compare your background to job requirements.",
    )

    _render_settings_step_heading("2", "Generate from Resume")
    if st.button(
        "Generate from Resume",
        key="settings_generate_profile_from_resume",
        disabled=not can_generate,
        help=(
            "Generate Executive Summary, Strengths to Highlight, and Cover Letter Voice from the current resume text. This does not overwrite Paste Resume."
            if can_generate
            else "Paste resume text and add an OpenAI API key first."
        ),
        use_container_width=False,
    ):
        with st.spinner("Generating profile context from resume..."):
            result = generate_profile_context_from_resume(
                st.session_state.get("settings_resume_text_value", "")
            )
        if result.get("ok"):
            st.session_state["settings_profile_summary_value"] = str(result.get("profile_summary", "") or "")
            st.session_state["settings_strengths_to_highlight_value"] = str(result.get("strengths_to_highlight", "") or "")
            st.session_state["settings_cover_letter_voice_value"] = str(result.get("cover_letter_voice", "") or "")
            st.success("Generated profile fields from your resume text. Review them, then save.")
            st.rerun()
        st.error(str(result.get("error", "") or "Could not generate profile context from resume."))

    profile_summary = st.text_area(
        "Executive Summary",
        key="settings_profile_summary_value",
        height=140,
        help="Primary source for AI scoring. Use this for your high level leadership summary and target profile.",
    )

    strengths_to_highlight = st.text_area(
        "Strengths to Highlight",
        key="settings_strengths_to_highlight_value",
        height=140,
        help="Primary source for AI scoring. Examples: AI transformation, enterprise IT leadership, ServiceNow, operational excellence.",
    )

    cover_letter_voice = st.text_area(
        "Cover Letter Voice",
        key="settings_cover_letter_voice_value",
        height=120,
        help="Used for cover letters only. This field does not affect job scoring.",
    )

    _render_settings_step_heading("3", "Save Profile Context")
    if not has_unsaved_changes:
        st.caption("Make a change before saving Profile Context.")

    if st.button(
        "Save Profile Context",
        type="primary",
        use_container_width=False,
        key="settings_save_profile_context",
        disabled=not has_unsaved_changes,
        help=(
            "Save the current Profile Context changes."
            if has_unsaved_changes
            else "Save becomes available after you change one of the Profile Context fields."
        ),
    ):
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
    st.caption(
        "Add the API key used for AI title expansion, AI scoring, AI scrub, and cover letters. "
        "The app uses a saved local key first and falls back to OPENAI_API_KEY from the environment."
    )

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
        st.success("AI-assisted discovery, scoring, scrub, and cover letters can use this key.")
    else:
        st.info("No OpenAI API key is configured yet. Save a local key below or provide OPENAI_API_KEY in the environment.")
        st.caption("Without a key, you can still discover and import jobs, but AI title expansion, scoring, scrub, and cover letters stay off.")

    if str(details["active_source"]) == "environment" and not bool(details["saved_key_present"]):
        st.warning(
            "The app is currently using OPENAI_API_KEY from the environment. "
            "There is no saved local key to delete from inside the app."
        )
        st.caption("If you want AI features fully off, unset OPENAI_API_KEY in the terminal or shell profile that launches the app, then restart it.")
        st.code("unset OPENAI_API_KEY", language="bash")
    elif bool(details["saved_key_present"]) and bool(details["environment_key_present"]):
        st.caption(
            "A saved local key is currently overriding OPENAI_API_KEY from the environment. "
            "If you delete the saved local key, the environment key will become active."
        )

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
            "Delete Saved Local Key",
            use_container_width=True,
            type="secondary",
            key="delete_saved_openai_api_key_button",
            disabled=not bool(details["can_delete_saved_key"]),
            help=(
                "Deletes only the locally saved key file for this machine."
                if details["can_delete_saved_key"]
                else "There is no saved local key file to delete."
            ),
        ):
            try:
                delete_saved_openai_api_key()
                st.session_state["settings_openai_api_key_value"] = ""
                st.success("Deleted saved local API key.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to delete saved API key: {exc}")

    if not bool(details["can_delete_saved_key"]) and bool(details["environment_key_present"]):
        st.caption("Delete is disabled because the active key is coming from the environment, not from a saved local file.")

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
    elif selected_section == "OpenAI API":
        render_openai_api_tab()
    else:
        render_system_status_tab()
