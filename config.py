from pathlib import Path

APP_NAME = "Job Application Agent"
APP_VERSION = "1.0"

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
LATEST_PIPELINE_LOG_PATH = LOGS_DIR / "latest_pipeline_run.txt"

DATABASE_FILENAME = "job_agent.db"
DATABASE_PATH = DATA_DIR / DATABASE_FILENAME

BACKUPS_DIR = DATA_DIR / "backups"
OPENAI_API_KEY_FILE = DATA_DIR / "openai_api_key.txt"
JOB_URLS_FILE = DATA_DIR / "job_urls.txt"
MANUAL_URLS_FILE = DATA_DIR / "manual_urls.txt"

DEFAULT_STORAGE_BACKEND = "sqlite"

# Legacy Google Sheets compatibility
SPREADSHEET_ID = "1h0LEK4-t6-j7rmdxjWeO8XY_Kx9L5HfQpOdkJtf_p_E"
NEW_ROLES_SHEET = "New Validated Roles"
APPLIED_SHEET = "Applied Roles"
REMOVED_SHEET = "Removed Roles"
SETTINGS_SHEET = "Settings"
