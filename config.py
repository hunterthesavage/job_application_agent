from pathlib import Path


APP_NAME = "Job Application Agent"
APP_VERSION = "v1.2"

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
BACKUPS_DIR = PROJECT_ROOT / "backups"

DATABASE_FILENAME = "job_agent.db"
DATABASE_PATH = DATA_DIR / DATABASE_FILENAME

OPENAI_API_KEY_FILE = DATA_DIR / "openai_api_key.txt"
OPENAI_API_KEY_META_FILE = DATA_DIR / "openai_api_key.meta.json"
OPENAI_API_STATE_FILE = DATA_DIR / "openai_api_state.json"

JOB_URLS_FILE = PROJECT_ROOT / "job_urls.txt"
MANUAL_URLS_FILE = DATA_DIR / "manual_urls.txt"

SPREADSHEET_ID = "1h0LEK4-t6-j7rmdxjWeO8XY_Kx9L5HfQpOdkJtf_p_E"
NEW_ROLES_SHEET = "New Validated Roles"
APPLIED_SHEET = "Applied Pipeline"
SETTINGS_SHEET = "Settings"
REMOVED_SHEET = "Removed Roles"

PAGE_SIZE_OPTIONS = [5, 10, 20, 500]
FIT_SCORE_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]

DEFAULT_STORAGE_BACKEND = "sqlite"
SUPPORTED_STORAGE_BACKENDS = {"sqlite"}
