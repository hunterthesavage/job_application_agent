from __future__ import annotations

import os
import subprocess
import sys
import time

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
            homepage_response = requests.get(url, timeout=2)
            last_status = str(homepage_response.status_code)
            page_text = homepage_response.text
            lower_text = page_text.lower()

            if any(signature in lower_text for signature in error_signatures):
                return False, last_status, "error_signature_detected"

            if homepage_response.ok and APP_NAME.lower() in lower_text:
                return True, last_status, "app_name_visible"

            if homepage_response.ok and "streamlit" in lower_text:
                saw_streamlit_shell = True
        except requests.RequestException:
            pass

        time.sleep(0.5)

    if saw_streamlit_shell:
        return True, last_status, "streamlit_shell_visible"
    return False, last_status, "homepage_not_ready"


def main() -> int:
    project_root = PROJECT_ROOT
    launch_script = os.path.join(project_root, "run_desktop_app.sh")
    port = find_free_port()
    url = streamlit_url(port)
    health_url = streamlit_health_url(port)

    env = os.environ.copy()
    env["JAA_DESKTOP_PORT"] = str(port)
    env["JAA_DESKTOP_AUTOCLOSE_SECONDS"] = "5"

    process = subprocess.Popen(
        [launch_script],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    health_ok = False
    page_ok = False
    exit_ok = False
    shutdown_ok = False
    homepage_status = "n/a"
    homepage_reason = "not_checked"
    start = time.time()

    try:
        deadline = start + 30
        while time.time() < deadline:
            if process.poll() is not None:
                break
            try:
                health_response = requests.get(health_url, timeout=1.5)
                if health_response.ok:
                    health_ok = True
                    break
            except requests.RequestException:
                pass
            time.sleep(0.35)

        if health_ok:
            page_ok, homepage_status, homepage_reason = assess_homepage(url)

        try:
            process.wait(timeout=20)
            exit_ok = process.returncode == 0
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            exit_ok = False

        try:
            requests.get(health_url, timeout=1.5)
            shutdown_ok = False
        except requests.RequestException:
            shutdown_ok = True

        stdout_text = process.stdout.read() if process.stdout is not None else ""
        stderr_text = process.stderr.read() if process.stderr is not None else ""

        print("Desktop wrapper smoke test")
        print(f"- URL: {url}")
        print(f"- Health endpoint reached: {'yes' if health_ok else 'no'}")
        print(f"- Homepage served: {'yes' if page_ok else 'no'}")
        print(f"- Homepage status: {homepage_status}")
        print(f"- Homepage check: {homepage_reason}")
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
