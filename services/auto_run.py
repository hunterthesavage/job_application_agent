from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any

from config import LOGS_DIR, PROJECT_ROOT


AUTO_RUN_FREQUENCY_OPTIONS: dict[str, str] = {
    "Off": "off",
    "Daily": "daily",
    "Weekdays": "weekdays",
    "Custom Weekly": "custom_weekly",
}

WEEKDAY_OPTIONS: list[tuple[str, str]] = [
    ("Mon", "mon"),
    ("Tue", "tue"),
    ("Wed", "wed"),
    ("Thu", "thu"),
    ("Fri", "fri"),
    ("Sat", "sat"),
    ("Sun", "sun"),
]

WEEKDAY_LABELS = {value: label for label, value in WEEKDAY_OPTIONS}
LAUNCHD_WEEKDAY_MAP = {
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
    "sun": 0,
}
WINDOWS_WEEKDAY_MAP = {
    "mon": "MON",
    "tue": "TUE",
    "wed": "WED",
    "thu": "THU",
    "fri": "FRI",
    "sat": "SAT",
    "sun": "SUN",
}

AUTO_RUN_LAUNCHD_LABEL = "com.jobapplicationagent.autorun"
AUTO_RUN_WINDOWS_TASK_NAME = "JobApplicationAgent Auto Run"


def normalize_auto_run_frequency(value: str) -> str:
    normalized = str(value or "").strip().lower()
    valid_values = set(AUTO_RUN_FREQUENCY_OPTIONS.values())
    if normalized in valid_values:
        return normalized
    return "off"


def parse_auto_run_days(value: str) -> list[str]:
    requested = []
    seen: set[str] = set()
    for raw in str(value or "").split(","):
        token = str(raw or "").strip().lower()
        if token not in WEEKDAY_LABELS or token in seen:
            continue
        requested.append(token)
        seen.add(token)
    return requested


def serialize_auto_run_days(days: list[str]) -> str:
    normalized = [day for day in parse_auto_run_days(",".join(days))]
    return ",".join(normalized)


def parse_auto_run_time(value: str) -> tuple[int, int, str]:
    raw = str(value or "").strip()
    try:
        parsed = datetime.strptime(raw, "%H:%M")
        return parsed.hour, parsed.minute, parsed.strftime("%H:%M")
    except Exception:
        return 8, 0, "08:00"


def parse_auto_run_time_value(value: str) -> dt_time:
    hour, minute, _ = parse_auto_run_time(value)
    return dt_time(hour=hour, minute=minute)


def format_auto_run_summary(settings: dict[str, str]) -> str:
    enabled = str(settings.get("auto_run_enabled", "false")).strip().lower() == "true"
    frequency = normalize_auto_run_frequency(settings.get("auto_run_frequency", "off"))
    _, _, time_text = parse_auto_run_time(settings.get("auto_run_time", "08:00"))
    days = parse_auto_run_days(settings.get("auto_run_days", "mon,tue,wed,thu,fri"))

    if not enabled or frequency == "off":
        return "Automatic job runs are off."
    if frequency == "daily":
        return f"Runs every day at {time_text}."
    if frequency == "weekdays":
        return f"Runs Monday through Friday at {time_text}."

    if not days:
        return f"Runs weekly at {time_text}."
    labels = ", ".join(WEEKDAY_LABELS.get(day, day.title()) for day in days)
    return f"Runs on {labels} at {time_text}."


def get_current_python_executable() -> str:
    return str(Path(sys.executable).resolve())


def get_scheduled_runner_script_path() -> str:
    return str((PROJECT_ROOT / "scripts" / "run_scheduled_jobs.py").resolve())


def build_headless_run_command() -> list[str]:
    return [get_current_python_executable(), get_scheduled_runner_script_path()]


def get_launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{AUTO_RUN_LAUNCHD_LABEL}.plist"


def get_windows_task_name() -> str:
    return AUTO_RUN_WINDOWS_TASK_NAME


def _build_launchd_intervals(*, frequency: str, hour: int, minute: int, days: list[str]) -> list[dict[str, int]]:
    if frequency == "daily":
        return [{"Hour": hour, "Minute": minute}]
    if frequency == "weekdays":
        return [{"Weekday": day_number, "Hour": hour, "Minute": minute} for day_number in [1, 2, 3, 4, 5]]

    requested_days = days or ["mon"]
    return [
        {"Weekday": LAUNCHD_WEEKDAY_MAP[day], "Hour": hour, "Minute": minute}
        for day in requested_days
        if day in LAUNCHD_WEEKDAY_MAP
    ]


def _run_subprocess(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return False, str(exc)

    if completed.returncode == 0:
        return True, (completed.stdout or completed.stderr or "").strip()
    return False, (completed.stderr or completed.stdout or "").strip()


def _configure_launchd(settings: dict[str, str]) -> dict[str, Any]:
    hour, minute, normalized_time = parse_auto_run_time(settings.get("auto_run_time", "08:00"))
    frequency = normalize_auto_run_frequency(settings.get("auto_run_frequency", "off"))
    days = parse_auto_run_days(settings.get("auto_run_days", "mon,tue,wed,thu,fri"))
    launch_agent_path = get_launch_agent_path()
    launch_agent_path.parent.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    plist_payload = {
        "Label": AUTO_RUN_LAUNCHD_LABEL,
        "ProgramArguments": build_headless_run_command(),
        "WorkingDirectory": str(PROJECT_ROOT.resolve()),
        "RunAtLoad": False,
        "StartCalendarInterval": _build_launchd_intervals(
            frequency=frequency,
            hour=hour,
            minute=minute,
            days=days,
        ),
        "StandardOutPath": str((LOGS_DIR / "auto_run_stdout.log").resolve()),
        "StandardErrorPath": str((LOGS_DIR / "auto_run_stderr.log").resolve()),
    }
    launch_agent_path.write_bytes(plistlib.dumps(plist_payload))

    _run_subprocess(["launchctl", "unload", str(launch_agent_path)])
    ok, detail = _run_subprocess(["launchctl", "load", "-w", str(launch_agent_path)])

    return {
        "ok": ok,
        "detail": detail or f"Saved LaunchAgent to {launch_agent_path}",
        "scheduler_path": str(launch_agent_path),
        "normalized_time": normalized_time,
    }


def _configure_windows_task(settings: dict[str, str]) -> dict[str, Any]:
    _, _, normalized_time = parse_auto_run_time(settings.get("auto_run_time", "08:00"))
    frequency = normalize_auto_run_frequency(settings.get("auto_run_frequency", "off"))
    days = parse_auto_run_days(settings.get("auto_run_days", "mon,tue,wed,thu,fri"))
    command = f'"{get_current_python_executable()}" "{get_scheduled_runner_script_path()}"'

    delete_command = ["schtasks", "/Delete", "/TN", AUTO_RUN_WINDOWS_TASK_NAME, "/F"]
    _run_subprocess(delete_command)

    create_command = [
        "schtasks",
        "/Create",
        "/TN",
        AUTO_RUN_WINDOWS_TASK_NAME,
        "/TR",
        command,
        "/ST",
        normalized_time,
        "/F",
    ]

    if frequency == "daily":
        create_command.extend(["/SC", "DAILY"])
    else:
        create_command.extend(["/SC", "WEEKLY"])
        selected_days = days if frequency == "custom_weekly" else ["mon", "tue", "wed", "thu", "fri"]
        windows_days = ",".join(WINDOWS_WEEKDAY_MAP[day] for day in selected_days if day in WINDOWS_WEEKDAY_MAP)
        create_command.extend(["/D", windows_days or "MON"])

    ok, detail = _run_subprocess(create_command)
    return {
        "ok": ok,
        "detail": detail or f"Updated task {AUTO_RUN_WINDOWS_TASK_NAME}",
        "scheduler_path": AUTO_RUN_WINDOWS_TASK_NAME,
        "normalized_time": normalized_time,
    }


def disable_auto_run_schedule() -> dict[str, Any]:
    system_name = platform.system().lower()
    if system_name == "darwin":
        launch_agent_path = get_launch_agent_path()
        if launch_agent_path.exists():
            _run_subprocess(["launchctl", "unload", str(launch_agent_path)])
            try:
                launch_agent_path.unlink()
            except FileNotFoundError:
                pass
        return {
            "ok": True,
            "detail": "Automatic job runs are off.",
            "scheduler_path": str(launch_agent_path),
        }

    if system_name == "windows":
        _run_subprocess(["schtasks", "/Delete", "/TN", AUTO_RUN_WINDOWS_TASK_NAME, "/F"])
        return {
            "ok": True,
            "detail": "Automatic job runs are off.",
            "scheduler_path": AUTO_RUN_WINDOWS_TASK_NAME,
        }

    return {
        "ok": False,
        "detail": f"Automatic job runs are not supported on {platform.system()} yet.",
        "scheduler_path": "",
    }


def configure_auto_run_schedule(settings: dict[str, str]) -> dict[str, Any]:
    enabled = str(settings.get("auto_run_enabled", "false")).strip().lower() == "true"
    frequency = normalize_auto_run_frequency(settings.get("auto_run_frequency", "off"))
    if not enabled or frequency == "off":
        return disable_auto_run_schedule()

    system_name = platform.system().lower()
    if system_name == "darwin":
        return _configure_launchd(settings)
    if system_name == "windows":
        return _configure_windows_task(settings)
    return {
        "ok": False,
        "detail": f"Automatic job runs are not supported on {platform.system()} yet.",
        "scheduler_path": "",
    }


def get_auto_run_runtime_status(settings: dict[str, str]) -> dict[str, Any]:
    system_name = platform.system().lower()
    scheduler_supported = system_name in {"darwin", "windows"}
    scheduler_path = ""
    scheduler_installed = False

    if system_name == "darwin":
        launch_agent_path = get_launch_agent_path()
        scheduler_path = str(launch_agent_path)
        scheduler_installed = launch_agent_path.exists()
    elif system_name == "windows":
        scheduler_path = AUTO_RUN_WINDOWS_TASK_NAME
        ok, _ = _run_subprocess(["schtasks", "/Query", "/TN", AUTO_RUN_WINDOWS_TASK_NAME])
        scheduler_installed = ok

    return {
        "platform": platform.system(),
        "scheduler_supported": scheduler_supported,
        "scheduler_installed": scheduler_installed,
        "scheduler_path": scheduler_path,
        "summary": format_auto_run_summary(settings),
    }
