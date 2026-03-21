from pathlib import Path
import os


APP_NAME = "Job Application Agent"
APP_VERSION = "v1.3"

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
BACKUPS_DIR = PROJECT_ROOT / "backups"

DATABASE_FILENAME = "job_agent.db"
DATABASE_PATH = DATA_DIR / DATABASE_FILENAME
OPENAI_API_KEY_FILE = DATA_DIR / "openai_api_key.txt"

JOB_URLS_FILE = PROJECT_ROOT / "job_urls.txt"
MANUAL_URLS_FILE = DATA_DIR / "manual_urls.txt"

SPREADSHEET_ID = os.getenv("JOB_AGENT_SPREADSHEET_ID", "")
NEW_ROLES_SHEET = "New Validated Roles"
APPLIED_SHEET = "Applied Pipeline"
SETTINGS_SHEET = "Settings"
REMOVED_SHEET = "Removed Roles"

PAGE_SIZE_OPTIONS = [5, 10, 20, 500]
FIT_SCORE_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]

DEFAULT_STORAGE_BACKEND = "sqlite"
SUPPORTED_STORAGE_BACKENDS = {"sqlite"}
