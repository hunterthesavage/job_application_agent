import os
import sys
from pathlib import Path

APP_NAME = "Job Application Agent"
APP_VERSION = "1.0.2"

PROJECT_ROOT = Path(__file__).resolve().parent


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def _default_frozen_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return Path(xdg_data_home) / "job_application_agent"
    return Path.home() / ".local" / "share" / "job_application_agent"


def resolve_data_dir() -> Path:
    override = os.environ.get("JAA_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen_app():
        return _default_frozen_data_dir()
    return PROJECT_ROOT / "data"


DATA_DIR = resolve_data_dir()
LOGS_DIR = DATA_DIR / "logs"
LATEST_PIPELINE_LOG_PATH = LOGS_DIR / "latest_pipeline_run.txt"

DATABASE_FILENAME = "job_agent.db"
DATABASE_PATH = DATA_DIR / DATABASE_FILENAME
APP_SERVER_PID_FILE = DATA_DIR / "jaa_server.pid"
APP_STDOUT_LOG_PATH = LOGS_DIR / "jaa_stdout.log"
APP_STDERR_LOG_PATH = LOGS_DIR / "jaa_stderr.log"

BACKUPS_DIR = DATA_DIR / "backups"
OPENAI_API_KEY_FILE = DATA_DIR / "openai_api_key.txt"
JOB_URLS_FILE = DATA_DIR / "job_urls.txt"
MANUAL_URLS_FILE = DATA_DIR / "manual_urls.txt"
RUNTIME_SETTINGS_FILE = DATA_DIR / "runtime_settings.json"

DEFAULT_STORAGE_BACKEND = "sqlite"
