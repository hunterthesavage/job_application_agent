from __future__ import annotations

import os
import threading
import time

from config import APP_SERVER_PID_FILE, DATA_DIR


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def write_server_pid(pid: int | None = None) -> int:
    _ensure_data_dir()
    resolved_pid = int(pid or os.getpid())
    APP_SERVER_PID_FILE.write_text(str(resolved_pid), encoding="utf-8")
    return resolved_pid


def read_server_pid() -> int | None:
    try:
        raw_value = APP_SERVER_PID_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if not raw_value:
        return None

    try:
        return int(raw_value)
    except Exception:
        return None


def clear_server_pid(expected_pid: int | None = None) -> None:
    current_value = read_server_pid()
    if expected_pid is not None and current_value is not None and current_value != int(expected_pid):
        return

    try:
        APP_SERVER_PID_FILE.unlink()
    except FileNotFoundError:
        return


def register_current_process() -> int:
    return write_server_pid(os.getpid())


def request_process_shutdown(delay_seconds: float = 0.75) -> threading.Thread:
    current_pid = register_current_process()

    def _delayed_shutdown() -> None:
        time.sleep(max(0.0, float(delay_seconds)))
        clear_server_pid(expected_pid=current_pid)
        os._exit(0)

    thread = threading.Thread(target=_delayed_shutdown, daemon=True, name="jaa-shutdown")
    thread.start()
    return thread
