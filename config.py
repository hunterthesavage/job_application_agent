from pathlib import Path

APP_NAME = "Job Application Agent"
APP_VERSION = "1.0.1"

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
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

DEFAULT_STORAGE_BACKEND = "sqlite"
