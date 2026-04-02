import html
from datetime import time as dt_time
from pathlib import Path

import streamlit as st

from config import (
    APP_NAME,
    APP_VERSION,
    BACKUPS_DIR,
    DATA_DIR,
    DATABASE_PATH,
    JOB_URLS_FILE,
    LOGS_DIR,
    MANUAL_URLS_FILE,
    OPENAI_API_KEY_FILE,
    PROJECT_ROOT,
    RUNTIME_SETTINGS_FILE,
)
from services.auto_run import (
    AUTO_RUN_FREQUENCY_OPTIONS,
    WEEKDAY_OPTIONS,
    configure_auto_run_schedule,
    format_auto_run_summary,
    get_auto_run_runtime_status,
    parse_auto_run_days,
    parse_auto_run_time,
    parse_auto_run_time_value,
    serialize_auto_run_days,
)
from services.backlog import get_backlog_summary
from services.backup import backup_database, get_latest_backup, restore_latest_backup
from services.health import run_health_check
from services.job_store import count_jobs_for_rescoring
from services.job_levels import (
    JOB_LEVEL_OPTIONS,
    parse_preferred_job_levels,
    serialize_preferred_job_levels,
)
from services.folder_picker import pick_folder_dialog
from services.openai_key import (
    delete_saved_openai_api_key,
    get_effective_openai_api_key,
    get_openai_api_key_details,
    has_openai_api_key,
    load_saved_openai_api_key,
    mask_openai_api_key,
    save_openai_api_key,
)
from services.pipeline_runtime import rescore_existing_jobs
from services.profile_context_templates import generate_profile_context_from_resume
from services.settings import (
    DEFAULT_SETTINGS,
    get_default_cover_letter_output_folder,
    load_settings,
    normalize_cover_letter_output_settings,
    save_settings,
)
from services.source_layer import (
    SOURCE_LAYER_MODE_ENV_VAR,
    get_source_layer_mode,
    set_source_layer_mode,
)
from services.source_layer_shadow_populate import populate_shadow_from_legacy_export
from services.source_layer_status_smoke import build_source_layer_status_summary
from services.status import get_system_status
from services.ui_busy import app_is_busy, queue_action
from ui.navigation import initialize_nav_state, render_button_nav


SETTINGS_NAV_OPTIONS = [
    "Configuration",
    "Profile Context",
    "OpenAI API",
    "System Status",
]

def _get_status_nav_options(*, show_internal_search_tools: bool) -> list[str]:
    options = ["Overview"]
    if show_internal_search_tools:
        options.extend(["Source Layer", "Backlog"])
    return options



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


def _save_internal_search_tools_visibility() -> None:
    show_internal = bool(st.session_state.get("settings_show_internal_search_tools_value", False))
    save_settings({"show_internal_search_tools": "true" if show_internal else "false"})
    st.session_state["settings_internal_search_tools_notice"] = (
        "Internal search tools are visible now."
        if show_internal
        else "Internal search tools are hidden now."
    )


def save_cover_letter_output_settings(folder_value: str, pattern_value: str) -> dict[str, str]:
    folder_value, pattern_value = normalize_cover_letter_output_settings(folder_value, pattern_value)
    return save_settings(
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
        saved_settings = save_cover_letter_output_settings(folder_value, pattern_value)
        st.session_state["settings_cover_letter_output_folder_value"] = saved_settings["cover_letter_output_folder"]
        st.session_state["settings_cover_letter_filename_pattern_value"] = saved_settings["cover_letter_filename_pattern"]
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
        saved_settings = save_cover_letter_output_settings(folder_value, pattern_value)
        st.session_state["settings_cover_letter_output_folder_value"] = saved_settings["cover_letter_output_folder"]
        st.session_state["settings_cover_letter_filename_pattern_value"] = saved_settings["cover_letter_filename_pattern"]
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
    if "settings_auto_run_enabled_value" not in st.session_state:
        st.session_state["settings_auto_run_enabled_value"] = str_to_bool(settings.get("auto_run_enabled", "false"))
    if "settings_auto_run_frequency_value" not in st.session_state:
        current_frequency = str(settings.get("auto_run_frequency", "off") or "off")
        current_frequency_label = next(
            (label for label, value in AUTO_RUN_FREQUENCY_OPTIONS.items() if value == current_frequency and value != "off"),
            "Daily",
        )
        st.session_state["settings_auto_run_frequency_value"] = current_frequency_label
    if "settings_auto_run_time_value" not in st.session_state:
        st.session_state["settings_auto_run_time_value"] = parse_auto_run_time_value(settings.get("auto_run_time", "08:00"))
    if "settings_auto_run_days_value" not in st.session_state:
        st.session_state["settings_auto_run_days_value"] = parse_auto_run_days(
            settings.get("auto_run_days", "mon,tue,wed,thu,fri")
        )


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
        RUNTIME_SETTINGS_FILE,
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
            if (
                key.startswith("wizard_")
                or key.startswith("setup_wizard_")
                or key.startswith("settings_")
            ):
                st.session_state.pop(key, None)

        st.session_state["_app_initialized"] = False
        st.session_state["_wizard_run_discovery_on_load"] = False
        st.session_state.pop("_post_wizard_run_message", None)
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


def _render_maintenance_notice() -> None:
    notice = st.session_state.pop("settings_maintenance_notice", None)
    if not isinstance(notice, dict):
        return

    kind = str(notice.get("kind", "info") or "info").strip().lower()
    message = str(notice.get("message", "") or "").strip()
    details = str(notice.get("details", "") or "").strip()

    if not message:
        return

    styles = {
        "success": ("rgba(34,197,94,0.16)", "rgba(134,239,172,0.95)", "rgba(34,197,94,0.34)"),
        "warning": ("rgba(250,204,21,0.14)", "rgba(254,240,138,0.95)", "rgba(250,204,21,0.30)"),
        "error": ("rgba(248,113,113,0.16)", "rgba(254,202,202,0.96)", "rgba(248,113,113,0.32)"),
        "info": ("rgba(96,165,250,0.14)", "rgba(191,219,254,0.96)", "rgba(96,165,250,0.30)"),
    }
    background, text_color, border = styles.get(kind, styles["info"])
    details_markup = f'<div style="margin-top:0.35rem;font-size:0.92rem;opacity:0.9;">{html.escape(details)}</div>' if details else ""
    st.markdown(
        f"""
        <div id="settings-maintenance-notice" style="
            margin-bottom: 0.8rem;
            border-radius: 16px;
            border: 1px solid {border};
            background: {background};
            color: {text_color};
            padding: 0.85rem 1rem;
        ">
            <div style="font-weight:700;">{html.escape(message)}</div>
            {details_markup}
        </div>
        <script>
            setTimeout(function() {{
                const node = window.parent.document.getElementById("settings-maintenance-notice");
                if (node) {{
                    node.style.transition = "opacity 0.35s ease";
                    node.style.opacity = "0";
                    setTimeout(function() {{ node.remove(); }}, 350);
                }}
            }}, 4500);
        </script>
        """,
        unsafe_allow_html=True,
    )


def _render_status_overview(*, show_internal_search_tools: bool = False) -> None:
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
    st.caption("Backups and restores change local app data only. Create Backup makes a timestamped copy. Restore Latest Backup replaces the current local database with the newest saved backup.")
    _render_maintenance_notice()
    b1, b2, b3 = st.columns(3)
    latest_backup = get_latest_backup()

    with b1:
        if st.button(
            "Create Backup",
            use_container_width=True,
            type="secondary",
            help="Create a timestamped local backup of the current app database.",
        ):
            try:
                with st.spinner("Creating backup..."):
                    backup_path = backup_database()

                st.session_state["settings_maintenance_notice"] = {
                    "kind": "success",
                    "message": "Backup created.",
                    "details": str(backup_path),
                }
                st.rerun()
            except Exception as exc:
                st.error("Backup failed.")
                st.text(str(exc))

    with b2:
        if st.button(
            "Run Health Check",
            use_container_width=True,
            type="secondary",
            help="Run a local diagnostic sweep across the database, backups, key status, and cover letter output path.",
        ):
            with st.spinner("Running health check..."):
                result = run_health_check()

            st.session_state["settings_last_health_check_result"] = result
            st.rerun()

    with b3:
        restore_confirmed = bool(st.session_state.get("settings_confirm_restore_latest_backup", False))
        restore_label = "Confirm Restore" if restore_confirmed else "Restore Latest Backup"
        if st.button(
            restore_label,
            use_container_width=True,
            type="secondary",
            disabled=latest_backup is None,
            help=(
                "Replace the current local database with the latest backup."
                if latest_backup is not None
                else "No backup exists yet, so there is nothing to restore."
            ),
        ):
            if not restore_confirmed:
                st.session_state["settings_confirm_restore_latest_backup"] = True
                st.rerun()

            try:
                with st.spinner("Restoring latest backup..."):
                    restored_from = restore_latest_backup()

                st.session_state["settings_maintenance_notice"] = {
                    "kind": "success",
                    "message": "Latest backup restored.",
                    "details": str(restored_from),
                }
                st.cache_data.clear()
                st.session_state.pop("settings_confirm_restore_latest_backup", None)
                st.rerun()
            except Exception as exc:
                st.error("Restore failed.")
                st.text(str(exc))
                st.session_state.pop("settings_confirm_restore_latest_backup", None)
        if restore_confirmed and latest_backup is not None:
            st.caption("Click Confirm Restore to replace the current local database with the latest backup.")

    last_health_check_result = st.session_state.get("settings_last_health_check_result")
    if isinstance(last_health_check_result, dict):
        st.markdown("---")
        _render_health_check_result(last_health_check_result)

    if show_internal_search_tools:
        st.markdown("---")
        st.markdown("#### Internal Maintenance")
        st.caption("Use this hidden internal area when you want to run secondary discovery/import actions or refresh existing jobs with the latest parser, AI scoring, and scrub rules.")

        internal_busy = app_is_busy()
        saved_job_links_exist = Path(JOB_URLS_FILE).exists()

        action_left, action_right = st.columns(2)
        with action_left:
            if st.button(
                "Find Job Links Only",
                use_container_width=True,
                type="secondary",
                disabled=internal_busy,
                key="settings_discover_only",
            ):
                queue_action(
                    "pipeline",
                    "discover_only",
                    payload={"use_ai_title_expansion": True},
                    label="Find Job Links Only",
                )
                st.session_state["top_nav_selection"] = "Pipeline"
                st.session_state["pipeline_subnav_selection"] = "Run Jobs"
                st.rerun()
        with action_right:
            if st.button(
                "Add Saved Job Links",
                use_container_width=True,
                type="secondary",
                disabled=internal_busy or (not saved_job_links_exist),
                key="settings_ingest_saved",
                help=(
                    "Saved job links file found and ready to import."
                    if saved_job_links_exist
                    else "No saved job links file exists yet. Run discovery first or paste job links."
                ),
            ):
                queue_action(
                    "pipeline",
                    "ingest_saved",
                    payload={"use_ai_scoring": True},
                    label="Add Saved Job Links",
                )
                st.session_state["top_nav_selection"] = "Pipeline"
                st.session_state["pipeline_subnav_selection"] = "Run Jobs"
                st.rerun()

        rescore_left, rescore_right = st.columns(2)
        with rescore_left:
            selected_rescore_label = st.selectbox(
                "Rescore Range",
                options=[label for label, _ in RESCORE_LIMIT_OPTIONS],
                index=1,
                key="settings_rescore_limit",
                help="Use a smaller batch for faster maintenance runs. Choose All only when you want to refresh the full backlog.",
            )
        selected_rescore_limit = dict(RESCORE_LIMIT_OPTIONS).get(selected_rescore_label, 50)

        with rescore_right:
            selected_stale_label = st.selectbox(
                "Rescore Age",
                options=[label for label, _ in RESCORE_STALE_OPTIONS],
                index=1,
                key="settings_rescore_stale_age",
                help="Use this to avoid spending AI calls on jobs that were refreshed recently.",
            )
        selected_stale_days = dict(RESCORE_STALE_OPTIONS).get(selected_stale_label, 7)

        ai_ready_for_rescore = has_openai_api_key()
        matching_jobs = count_jobs_for_rescoring(stale_days=selected_stale_days or None)
        selected_jobs = matching_jobs if selected_rescore_limit == 0 else min(matching_jobs, selected_rescore_limit)
        st.caption(
            f"Current rescore policy matches {matching_jobs} jobs. "
            f"This run will process {selected_jobs}."
        )
        if not ai_ready_for_rescore:
            st.caption("Add an OpenAI API key in Settings -> OpenAI API to enable batch rescoring.")

        if st.button(
            "Rescore Existing Jobs",
            use_container_width=False,
            type="secondary",
            disabled=not ai_ready_for_rescore,
            key="settings_rescore_existing_jobs",
            help=(
                "Refresh existing jobs with current AI scoring and scrub rules."
                if ai_ready_for_rescore
                else "No OpenAI API key is configured. Add one in Settings > OpenAI API."
            ),
        ):
            try:
                with st.spinner("Refreshing and rescoring existing jobs..."):
                    result = rescore_existing_jobs(
                        limit=selected_rescore_limit,
                        stale_days=selected_stale_days,
                    )
                rescored_count = int(result.get("rescored_count", 0) or 0)
                errors = int(result.get("errors", 0) or 0)
                st.session_state["settings_maintenance_notice"] = {
                    "kind": "success" if rescored_count > 0 else "warning",
                    "message": (
                        f"Refreshed and rescored {rescored_count} existing jobs."
                        if rescored_count > 0
                        else "No existing jobs were available to refresh and rescore."
                    ),
                    "details": f"Errors: {errors}",
                }
            except Exception as exc:
                st.session_state["settings_maintenance_notice"] = {
                    "kind": "error",
                    "message": "Existing job refresh failed.",
                    "details": str(exc),
                }
            st.rerun()

    _render_reset_app_section()


def _render_backlog_lane_card(lane: str, count: int, copy: str) -> str:
    priority_class = lane.strip().lower().replace(" ", "-")
    return (
        f'<div class="settings-backlog-card {priority_class}">'
        f'<div class="settings-backlog-kicker">{html.escape(lane)}</div>'
        f'<div class="settings-backlog-count">{count}</div>'
        f'<div class="settings-backlog-copy">{html.escape(copy)}</div>'
        '</div>'
    )


def _render_status_backlog() -> None:
    summary = get_backlog_summary()
    counts = summary.get("counts", {}) or {}
    items_by_lane = summary.get("items_by_lane", {}) or {}
    done_or_stale = summary.get("done_or_stale", []) or []
    recently_completed = summary.get("recently_completed", []) or []
    percent = int(summary.get("soft_launch_percent", 0) or 0)

    st.markdown("### Backlog")
    st.caption("This is the current launch-focused backlog based on what needs to move now, what is next, what can wait, and what is already settled or stale.")

    progress_left, progress_right = st.columns([1.15, 2.2])
    with progress_left:
        st.metric("Soft Launch Progress", f"{percent}%")
    with progress_right:
        st.info(
            "The goal is to finish validation, launch hardening, and legacy quality improvements first. "
            "New infrastructure or discovery expansion should wait unless it clearly helps the shipped V1 path."
        )

    card_markup = (
        '<div class="settings-backlog-grid">'
        + _render_backlog_lane_card(
            "Now",
            int(counts.get("Now", 0) or 0),
            "Highest-ROI launch and quality work that should move before broader scope.",
        )
        + _render_backlog_lane_card(
            "Next",
            int(counts.get("Next", 0) or 0),
            "Important follow-up work once the immediate validation and blocker loop is under control.",
        )
        + _render_backlog_lane_card(
            "Later",
            int(counts.get("Later", 0) or 0),
            "Useful expansion and cleanup work that can wait until after the core path is validated.",
        )
        + '</div>'
    )
    st.markdown(card_markup, unsafe_allow_html=True)

    for lane in ("Now", "Next", "Later"):
        items = items_by_lane.get(lane, []) or []
        with st.expander(f"{lane} ({len(items)})", expanded=(lane == "Now")):
            for item in items:
                st.markdown(f"**{item.get('title', 'Backlog item')}**")
                st.write(str(item.get("detail", "") or ""))

    if done_or_stale:
        with st.expander(f"Done / Stale ({len(done_or_stale)})", expanded=False):
            for item in done_or_stale:
                st.markdown(f"**{item.get('title', 'Closed item')}**")
                st.write(str(item.get("detail", "") or ""))

    if recently_completed:
        with st.expander("Recently completed", expanded=False):
            for item in recently_completed:
                st.write(f"- {item}")


def _render_status_source_layer() -> None:
    summary = build_source_layer_status_summary()
    legacy = summary.get("legacy", {}) or {}
    shadow = summary.get("shadow", {}) or {}
    next_gen = summary.get("next_gen", {}) or {}
    latest_run = summary.get("latest_run")
    effective_mode = get_source_layer_mode()
    saved_mode = str(load_settings().get("source_layer_mode", "legacy") or "legacy").strip().lower()
    env_override_mode = str(os.getenv(SOURCE_LAYER_MODE_ENV_VAR, "") or "").strip().lower()

    def _humanize(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "Unknown"
        aliases = {
            "next_gen": "Direct Source",
            "direct_source_seed_experiment": "Direct Source Seed Experiment",
        }
        if text in aliases:
            return aliases[text]
        return text.replace("_", " ").title()

    st.markdown("### Source Layer")
    st.caption(
        "This is an internal read-only view of the current source-layer state. "
        "Legacy remains the current source of truth, shadow reflects locally populated endpoint inventory, and next_gen currently layers supported direct-source seeds on top of legacy discovery."
    )

    st.markdown("#### Internal Source Layer Mode")
    st.caption(
        "This controls the app's internal source-layer mode for testing. "
        "Visible discovery behavior still stays legacy-first unless the current source-layer plumbing adds comparison output or supported direct-source seeds."
    )

    if "settings_source_layer_mode_value" not in st.session_state:
        st.session_state["settings_source_layer_mode_value"] = saved_mode

    mode_help = {
        "legacy": "Current source of truth only.",
        "shadow": "Keep legacy visible, but include shadow comparison diagnostics.",
        "next_gen": "Keep legacy discovery primary, but add supported direct-source seed URLs when available.",
    }

    selected_mode = st.radio(
        "Source Layer Mode",
        options=["legacy", "shadow", "next_gen"],
        format_func=lambda value: f"{_humanize(value)}",
        key="settings_source_layer_mode_value",
        horizontal=True,
        help="Internal-only testing control for source-layer mode.",
    )

    mode_dirty = selected_mode != saved_mode
    mode_col_1, mode_col_2 = st.columns([1.2, 3.2])
    with mode_col_1:
        if st.button(
            "Save Mode",
            type="primary",
            use_container_width=True,
            disabled=not mode_dirty,
            key="settings_save_source_layer_mode",
            help=(
                "Save this internal source-layer mode."
                if mode_dirty
                else "Change the selected mode before saving."
            ),
        ):
            new_mode = set_source_layer_mode(selected_mode)
            st.session_state["settings_source_layer_notice"] = {
                "kind": "success",
                "message": f"Saved source-layer mode: {_humanize(new_mode)}.",
                "details": (
                    f"Effective mode is currently {_humanize(env_override_mode)} via {SOURCE_LAYER_MODE_ENV_VAR}."
                    if env_override_mode
                    else f"Effective mode is now {_humanize(new_mode)}."
                ),
            }
            st.rerun()
    with mode_col_2:
        st.caption(
            f"Selected mode meaning: {mode_help.get(selected_mode, '')}"
        )

    st.write(f"- Saved mode: {_humanize(saved_mode)}")
    st.write(f"- Effective mode: {_humanize(effective_mode)}")
    if env_override_mode:
        st.warning(
            f"{SOURCE_LAYER_MODE_ENV_VAR} is set to {_humanize(env_override_mode)}. "
            "That environment override takes precedence over the saved mode until the app is restarted without it."
        )

    notice = st.session_state.pop("settings_source_layer_notice", None)
    if isinstance(notice, dict):
        kind = str(notice.get("kind", "info") or "info").strip().lower()
        message = str(notice.get("message", "") or "").strip()
        details = str(notice.get("details", "") or "").strip()
        if message:
            if kind == "success":
                st.success(message)
            elif kind == "error":
                st.error(message)
            else:
                st.info(message)
            if details:
                st.caption(details)

    action_col_1, action_col_2 = st.columns([1.2, 3.2])
    with action_col_1:
        if st.button(
            "Populate Shadow From Legacy",
            type="secondary",
            use_container_width=True,
            help="Internal-only action. Loads the current legacy export into local shadow source-layer tables without changing live discovery.",
            key="settings_source_layer_populate_shadow",
        ):
            try:
                with st.spinner("Populating shadow from legacy export..."):
                    result = populate_shadow_from_legacy_export()
                import_summary = result.get("legacy_import", {}) or {}
                st.session_state["settings_source_layer_notice"] = {
                    "kind": "success",
                    "message": "Shadow populated from legacy export.",
                    "details": (
                        f"Imported {int(import_summary.get('endpoint_inserted', 0) or 0)} new endpoint(s), "
                        f"updated {int(import_summary.get('endpoint_updated', 0) or 0)} existing endpoint(s)."
                    ),
                }
            except Exception as exc:
                st.session_state["settings_source_layer_notice"] = {
                    "kind": "error",
                    "message": "Shadow population failed.",
                    "details": str(exc),
                }
            st.rerun()
    with action_col_2:
        st.caption(
            "Use this to refresh local shadow source-layer tables from the current legacy export. "
            "This does not change visible app behavior; it only refreshes the local inventory used by shadow diagnostics and direct-source seeds."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Legacy Status", _humanize(legacy.get("status", "unknown")))
    c2.metric("Shadow Companies", int(shadow.get("company_count", 0) or 0))
    c3.metric("Shadow Endpoints", int(shadow.get("endpoint_count", 0) or 0))
    c4.metric("Approved", int(shadow.get("approved_endpoint_count", 0) or 0))

    st.markdown("#### Current Mode Snapshot")
    st.write(f"- Legacy status: {_humanize(legacy.get('status', 'unknown'))}")
    st.write(f"- Shadow active endpoints: {int(shadow.get('active_endpoint_count', 0) or 0)}")
    st.write(f"- Shadow approved endpoints: {int(shadow.get('approved_endpoint_count', 0) or 0)}")
    st.write(f"- Direct-source status: {_humanize(next_gen.get('status', 'unknown'))}")
    if str(next_gen.get("note", "") or "").strip():
        st.write(f"- Direct-source note: {str(next_gen.get('note', '')).strip()}")

    if latest_run:
        st.markdown("#### Latest Source Layer Run")
        latest_run_mode = str(latest_run.get("mode", "unknown") or "unknown")
        st.write(f"- Mode: {_humanize(latest_run_mode)}")
        if latest_run_mode == "import":
            st.write(f"- Imported records: {int(latest_run.get('imported_records', 0) or 0)}")
        st.write(f"- Selected endpoints: {int(latest_run.get('selected_endpoints', 0) or 0)}")
        st.write(f"- Discovered URLs: {int(latest_run.get('discovered_urls', 0) or 0)}")
        st.write(f"- Accepted jobs: {int(latest_run.get('accepted_jobs', 0) or 0)}")
        if latest_run_mode == "next_gen":
            st.write(
                f"- Direct-source seeds scanned: {int(latest_run.get('next_gen_supported_seeds_scanned', 0) or 0)}"
            )
            st.write(
                f"- Direct-source unsupported seeds skipped: {int(latest_run.get('next_gen_unsupported_seeds_skipped', 0) or 0)}"
            )
            st.write(f"- Direct-source seeded URLs: {int(latest_run.get('next_gen_seeded_urls', 0) or 0)}")
            st.write(
                f"- Direct-source seeded accepted jobs: {int(latest_run.get('next_gen_seeded_accepted_jobs', 0) or 0)}"
            )
            seeded_companies = str(latest_run.get("seeded_accepted_companies", "") or "").strip()
            if seeded_companies:
                st.write(f"- Seeded accepted companies: {seeded_companies}")
            seed_failures = str(latest_run.get("next_gen_seed_failures", "") or "").strip()
            if seed_failures:
                st.write(f"- Direct-source seed failures: {seed_failures}")
        first_pipeline_error = str(latest_run.get("first_pipeline_error", "") or "").strip()
        if first_pipeline_error:
            st.write(f"- First pipeline error: {first_pipeline_error}")
        st.write(f"- Errors: {int(latest_run.get('errors', 0) or 0)}")
        if str(latest_run.get("notes", "") or "").strip():
            st.write(f"- Notes: {latest_run.get('notes', '')}")
    else:
        st.info("No source-layer runs have been recorded yet.")


def render_system_status_tab() -> None:
    _inject_settings_css()
    settings = load_settings()
    show_internal_search_tools = str_to_bool(settings.get("show_internal_search_tools", "false"))
    status_nav_options = _get_status_nav_options(show_internal_search_tools=show_internal_search_tools)
    initialize_nav_state("settings_status_subnav_selection", status_nav_options[0])

    st.markdown("### System Status")
    st.caption("Use this area for maintenance, local app health, and launch tracking.")
    st.caption(f"{APP_NAME} version {APP_VERSION}")
    st.caption(f"Database path: {DATABASE_PATH}")

    if "settings_show_internal_search_tools_value" not in st.session_state:
        st.session_state["settings_show_internal_search_tools_value"] = show_internal_search_tools

    st.toggle(
        "Show Internal Search Tools",
        key="settings_show_internal_search_tools_value",
        help="Internal-only testing toggle. Turn this on when you want Source Layer diagnostics and backlog views visible in Settings.",
        on_change=_save_internal_search_tools_visibility,
    )

    internal_tools_notice = st.session_state.pop("settings_internal_search_tools_notice", "")
    if internal_tools_notice:
        st.caption(internal_tools_notice)

    selected_status_section = render_button_nav(
        options=status_nav_options,
        state_key="settings_status_subnav_selection",
        key_prefix="settings_status_subnav",
        selected_button_type="tertiary",
    )
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

    if selected_status_section == "Backlog":
        _render_status_backlog()
    elif selected_status_section == "Source Layer":
        _render_status_source_layer()
    else:
        _render_status_overview(show_internal_search_tools=show_internal_search_tools)


def render_configuration_tab(settings: dict[str, str]) -> None:
    st.markdown("### Cover Letter Output")
    st.caption("This only affects generated cover letters. Discovery and AI scoring still work without it.")
    st.caption(f"If you do nothing, letters will go here by default: {get_default_cover_letter_output_folder()}")

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
        selected_folder, picker_error = pick_folder_dialog(
            current_folder,
            title="Select Cover Letter Output Folder",
        )
        if picker_error:
            st.session_state["cover_letter_output_settings_saved_message"] = (
                f"Could not open folder picker: {picker_error}"
            )
        st.session_state["settings_cover_letter_output_folder_value"] = selected_folder

        try:
            saved_settings = save_cover_letter_output_settings(
                st.session_state["settings_cover_letter_output_folder_value"],
                st.session_state["settings_cover_letter_filename_pattern_value"],
            )
            st.session_state["settings_cover_letter_output_folder_value"] = saved_settings["cover_letter_output_folder"]
            st.session_state["settings_cover_letter_filename_pattern_value"] = saved_settings["cover_letter_filename_pattern"]
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
        st.info("This folder will be created automatically the first time you generate a cover letter.")

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

    st.markdown("---")
    st.markdown("### Page Defaults")

    current_fit = str(settings.get("default_min_fit_score", "75"))
    if current_fit not in FIT_OPTIONS:
        current_fit = "75"

    current_page_size = str(settings.get("default_jobs_per_page", "10"))
    if current_page_size not in PAGE_SIZE_OPTIONS:
        current_page_size = "10"

    current_new_roles_sort = str(settings.get("default_new_roles_sort", "Highest Fit Score"))
    if current_new_roles_sort not in NEW_ROLES_SORT_OPTIONS:
        current_new_roles_sort = "Highest Fit Score"

    saved_levels = parse_preferred_job_levels(settings.get("preferred_job_levels", ""))

    if "settings_default_min_fit_score_value" not in st.session_state:
        st.session_state["settings_default_min_fit_score_value"] = current_fit
    if "settings_default_jobs_per_page_value" not in st.session_state:
        st.session_state["settings_default_jobs_per_page_value"] = current_page_size
    if "settings_default_new_roles_sort_value" not in st.session_state:
        st.session_state["settings_default_new_roles_sort_value"] = current_new_roles_sort
    if "settings_preferred_job_levels_value" not in st.session_state:
        st.session_state["settings_preferred_job_levels_value"] = saved_levels

    d1, d2, d3 = st.columns(3)

    with d1:
        st.selectbox(
            "Default Minimum Fit Score",
            FIT_OPTIONS,
            key="settings_default_min_fit_score_value",
        )

    with d2:
        st.selectbox(
            "Default Jobs Per Page",
            PAGE_SIZE_OPTIONS,
            key="settings_default_jobs_per_page_value",
        )

    with d3:
        st.selectbox(
            "Default New Roles Sort",
            NEW_ROLES_SORT_OPTIONS,
            key="settings_default_new_roles_sort_value",
            help="Controls the default sort used when you open New Roles.",
        )

    st.markdown("---")
    st.markdown("### Automatic Job Runs")
    st.caption(
        "Use one schedule for the same Run Jobs flow the app uses manually. When this is on, the app can discover new jobs, refresh stale existing jobs, and re-run AI scoring in the background."
    )

    current_auto_run_enabled = str_to_bool(settings.get("auto_run_enabled", "false"))
    current_auto_run_frequency = str(settings.get("auto_run_frequency", "off") or "off")
    current_auto_run_time = str(settings.get("auto_run_time", "08:00") or "08:00")
    current_auto_run_days = parse_auto_run_days(settings.get("auto_run_days", "mon,tue,wed,thu,fri"))

    auto_run_notice = st.session_state.pop("settings_auto_run_notice", None)
    if auto_run_notice:
        kind = str(auto_run_notice.get("kind", "info")).strip().lower()
        message = str(auto_run_notice.get("message", "")).strip()
        if message:
            if kind == "success":
                st.success(message)
            elif kind == "warning":
                st.warning(message)
            else:
                st.info(message)

    frequency_options = [label for label, value in AUTO_RUN_FREQUENCY_OPTIONS.items() if value != "off"]
    weekday_labels = {value: label for label, value in WEEKDAY_OPTIONS}

    if bool(st.session_state.get("settings_auto_run_enabled_value", current_auto_run_enabled)):
        current_frequency_selection = str(st.session_state.get("settings_auto_run_frequency_value", "Daily"))
        if current_frequency_selection not in frequency_options:
            st.session_state["settings_auto_run_frequency_value"] = "Daily"

    schedule_left, schedule_right = st.columns([1.15, 1])
    with schedule_left:
        st.toggle(
            "Enable Automatic Job Runs",
            key="settings_auto_run_enabled_value",
            help="When on, the app installs a background scheduler on this machine and runs the full Run Jobs flow at the time you choose below.",
        )

        st.selectbox(
            "Automatic Run Frequency",
            options=frequency_options,
            key="settings_auto_run_frequency_value",
            disabled=not bool(st.session_state.get("settings_auto_run_enabled_value", current_auto_run_enabled)),
        )

        st.time_input(
            "Automatic Run Time",
            key="settings_auto_run_time_value",
            disabled=not bool(st.session_state.get("settings_auto_run_enabled_value", current_auto_run_enabled)),
            help="Local machine time. The background run uses this machine's time zone.",
        )

        selected_frequency_value = AUTO_RUN_FREQUENCY_OPTIONS.get(
            str(st.session_state.get("settings_auto_run_frequency_value", "Off")),
            "off",
        )
        if selected_frequency_value == "custom_weekly":
            st.multiselect(
                "Run On These Days",
                options=[label for label, _ in WEEKDAY_OPTIONS],
                default=[weekday_labels.get(day, day.title()) for day in current_auto_run_days],
                key="settings_auto_run_days_label_value",
                help="Choose one or more days for the weekly schedule.",
            )
            selected_auto_run_days = [
                value
                for label, value in WEEKDAY_OPTIONS
                if label in st.session_state.get("settings_auto_run_days_label_value", [])
            ]
        elif selected_frequency_value == "weekdays":
            selected_auto_run_days = ["mon", "tue", "wed", "thu", "fri"]
            st.caption("Weekdays means Monday through Friday.")
        else:
            selected_auto_run_days = current_auto_run_days or ["mon", "tue", "wed", "thu", "fri"]

    with schedule_right:
        selected_time_value = st.session_state.get("settings_auto_run_time_value", parse_auto_run_time_value(current_auto_run_time))
        selected_time_text = (
            selected_time_value.strftime("%H:%M")
            if isinstance(selected_time_value, dt_time)
            else parse_auto_run_time(current_auto_run_time)[2]
        )
        selected_enabled = bool(st.session_state.get("settings_auto_run_enabled_value", current_auto_run_enabled))
        selected_frequency = AUTO_RUN_FREQUENCY_OPTIONS.get(
            str(st.session_state.get("settings_auto_run_frequency_value", "Daily")),
            "daily",
        )
        staged_schedule = {
            "auto_run_enabled": "true" if selected_enabled else "false",
            "auto_run_frequency": selected_frequency if selected_enabled else "off",
            "auto_run_time": selected_time_text,
            "auto_run_days": serialize_auto_run_days(selected_auto_run_days),
        }
        runtime_status = get_auto_run_runtime_status(settings)
        if str(settings.get("auto_run_last_summary", "") or "").strip():
            st.info(str(settings.get("auto_run_last_summary", "") or "").strip())
        if str(settings.get("auto_run_last_started_at", "") or "").strip():
            st.caption(f"Last automatic run started: {settings.get('auto_run_last_started_at', '')}")
        if str(settings.get("auto_run_last_finished_at", "") or "").strip():
            st.caption(f"Last automatic run finished: {settings.get('auto_run_last_finished_at', '')}")
        if str(settings.get("auto_run_last_status", "") or "").strip():
            st.caption(f"Last automatic run status: {settings.get('auto_run_last_status', '')}")
        if (not runtime_status["scheduler_supported"]) and selected_enabled:
            st.warning(f"Automatic job runs are not supported on {runtime_status['platform']} yet.")

    current_frequency_label = next(
        (label for label, value in AUTO_RUN_FREQUENCY_OPTIONS.items() if value == current_auto_run_frequency and value != "off"),
        "Daily",
    )
    current_time_text = parse_auto_run_time(current_auto_run_time)[2]
    selected_time_text_for_compare = (
        st.session_state.get("settings_auto_run_time_value", parse_auto_run_time_value(current_auto_run_time)).strftime("%H:%M")
        if isinstance(st.session_state.get("settings_auto_run_time_value", parse_auto_run_time_value(current_auto_run_time)), dt_time)
        else current_time_text
    )
    schedule_has_changes = any(
        [
            bool(st.session_state.get("settings_auto_run_enabled_value", current_auto_run_enabled)) != current_auto_run_enabled,
            str(st.session_state.get("settings_auto_run_frequency_value", current_frequency_label)) != current_frequency_label,
            selected_time_text_for_compare != current_time_text,
            serialize_auto_run_days(selected_auto_run_days) != serialize_auto_run_days(current_auto_run_days),
        ]
    )

    if st.button(
        "Save Automatic Run Schedule",
        type="primary",
        use_container_width=False,
        disabled=not schedule_has_changes,
        key="settings_save_auto_run_schedule",
    ):
        saved_settings = save_settings(staged_schedule)
        schedule_result = configure_auto_run_schedule(saved_settings)
        if schedule_result.get("ok"):
            st.session_state["settings_auto_run_notice"] = {
                "kind": "success",
                "message": schedule_result.get("detail", "Automatic job run schedule saved."),
            }
        else:
            st.session_state["settings_auto_run_notice"] = {
                "kind": "warning",
                "message": schedule_result.get("detail", "Automatic job run schedule was saved, but the local scheduler could not be updated."),
            }
        st.rerun()

    st.markdown("---")
    st.markdown("### AI Scoring Preferences")

    st.multiselect(
        "Preferred Job Levels",
        options=JOB_LEVEL_OPTIONS,
        key="settings_preferred_job_levels_value",
        help="AI scoring will penalize jobs whose title level falls below the levels you select here.",
    )

    has_configuration_changes = any(
        [
            str(st.session_state.get("settings_default_min_fit_score_value", current_fit)) != str(settings.get("default_min_fit_score", "Any")),
            str(st.session_state.get("settings_default_jobs_per_page_value", current_page_size)) != str(settings.get("default_jobs_per_page", "10")),
            str(st.session_state.get("settings_default_new_roles_sort_value", current_new_roles_sort)) != str(settings.get("default_new_roles_sort", "Highest Fit Score")),
            serialize_preferred_job_levels(st.session_state.get("settings_preferred_job_levels_value", saved_levels)) != str(settings.get("preferred_job_levels", "")),
        ]
    )

    if st.button(
        "Save Configuration",
        type="primary",
        use_container_width=False,
        disabled=not has_configuration_changes,
        key="settings_save_configuration_button",
    ):
        default_min_fit_score = str(st.session_state.get("settings_default_min_fit_score_value", current_fit))
        default_jobs_per_page = str(st.session_state.get("settings_default_jobs_per_page_value", current_page_size))
        default_new_roles_sort = str(st.session_state.get("settings_default_new_roles_sort_value", current_new_roles_sort))
        preferred_job_levels = st.session_state.get("settings_preferred_job_levels_value", saved_levels)

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
    current_saved_key = str(load_saved_openai_api_key() or "")
    current_key_value = str(st.session_state.get("settings_openai_api_key_value", "") or "")
    api_key_dirty = bool(current_key_value.strip()) and current_key_value != current_saved_key

    with action_col_1:
        if st.button(
            "Save API Key",
            use_container_width=True,
            type="primary",
            key="save_openai_api_key_button",
            disabled=not api_key_dirty,
            help=(
                "Save this key locally for this machine."
                if api_key_dirty
                else "Paste a new API key before saving."
            ),
        ):
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
