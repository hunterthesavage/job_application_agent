from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import APP_NAME
from services.desktop_wrapper import find_free_port, streamlit_health_url, streamlit_url


def assess_homepage(url: str, *, timeout_seconds: float = 12.0) -> tuple[bool, str, str]:
    error_signatures = [
        "module not found",
        "modulenotfounderror",
        "traceback",
        "no module named",
    ]
    deadline = time.time() + max(1.0, float(timeout_seconds))
    last_status = "n/a"
    saw_streamlit_shell = False

    while time.time() < deadline:
        try:
            page = requests.get(url, timeout=2)
            last_status = str(page.status_code)
            page_text = page.text
            lower_text = page_text.lower()

            if any(signature in lower_text for signature in error_signatures):
                return False, last_status, "error_signature_detected"

            if page.ok and APP_NAME.lower() in lower_text:
                return True, last_status, "app_name_visible"

            if page.ok and "streamlit" in lower_text:
                saw_streamlit_shell = True
        except requests.RequestException:
            pass

        time.sleep(0.5)

    if saw_streamlit_shell:
        return True, last_status, "streamlit_shell_visible"
    return False, last_status, "homepage_not_ready"


def main() -> int:
    exe = PROJECT_ROOT / "dist" / "windows-desktop" / "JobApplicationAgentDesktop" / "JobApplicationAgentDesktop.exe"
    if not exe.exists():
        raise SystemExit(f"Packaged executable not found: {exe}")

    port = find_free_port()
    env = os.environ.copy()
    env["JAA_DESKTOP_PORT"] = str(port)
    env["JAA_DESKTOP_AUTOCLOSE_SECONDS"] = "5"

    process = subprocess.Popen(
        [str(exe)],
        cwd=str(exe.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    health_ok = False
    page_ok = False
    page_status = "n/a"
    page_reason = "not_checked"
    start = time.time()

    try:
        deadline = start + 40
        while time.time() < deadline:
            if process.poll() is not None:
                break
            try:
                if requests.get(streamlit_health_url(port), timeout=1.5).ok:
                    health_ok = True
                    break
            except requests.RequestException:
                pass
            time.sleep(0.35)

        if health_ok:
            page_ok, page_status, page_reason = assess_homepage(streamlit_url(port))

        try:
            process.wait(timeout=20)
            exit_ok = process.returncode == 0
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            exit_ok = False

        try:
            requests.get(streamlit_health_url(port), timeout=1.5)
            shutdown_ok = False
        except requests.RequestException:
            shutdown_ok = True

        stdout_text = process.stdout.read() if process.stdout else ""
        stderr_text = process.stderr.read() if process.stderr else ""

        print("Packaged Windows desktop smoke test")
        print(f"- Executable: {exe}")
        print(f"- URL: {streamlit_url(port)}")
        print(f"- Health endpoint reached: {'yes' if health_ok else 'no'}")
        print(f"- Homepage served: {'yes' if page_ok else 'no'}")
        print(f"- Homepage status: {page_status}")
        print(f"- Homepage check: {page_reason}")
        print(f"- Wrapper exited cleanly after auto-close: {'yes' if exit_ok else 'no'}")
        print(f"- Server stopped after window close: {'yes' if shutdown_ok else 'no'}")
        print(f"- Elapsed seconds: {time.time() - start:.2f}")
        if stderr_text.strip():
            print("- stderr:")
            print(stderr_text.strip())
        if stdout_text.strip():
            print("- stdout:")
            print(stdout_text.strip())

        return 0 if health_ok and page_ok and exit_ok and shutdown_ok else 1
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
