from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from config import APP_NAME, APP_STDERR_LOG_PATH, APP_STDOUT_LOG_PATH, APP_VERSION, DATA_DIR, PROJECT_ROOT

STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_BOOT_TIMEOUT_SECONDS = 45.0


class DesktopWrapperLaunchError(RuntimeError):
    """Raised when the local Streamlit server cannot be started for the desktop shell."""


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    APP_STDOUT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def find_free_port(host: str = STREAMLIT_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def resolve_desktop_port() -> int:
    raw_value = str(os.environ.get("JAA_DESKTOP_PORT", "")).strip()
    if raw_value:
        try:
            port = int(raw_value)
            if port > 0:
                return port
        except Exception:
            pass
    return find_free_port()


def resolve_auto_close_seconds() -> float:
    raw_value = str(os.environ.get("JAA_DESKTOP_AUTOCLOSE_SECONDS", "")).strip()
    if not raw_value:
        return 0.0
    try:
        return max(0.0, float(raw_value))
    except Exception:
        return 0.0


def resolve_webview_gui() -> str | None:
    if sys.platform == "win32":
        return "qt"
    return None


def resolve_window_dimensions() -> tuple[int, int, tuple[int, int]]:
    if sys.platform == "win32":
        return (1024, 720, (860, 620))
    if sys.platform == "darwin":
        return (1360, 920, (1100, 760))
    return (1280, 860, (1024, 720))


def resolve_window_launch_flags() -> dict[str, bool]:
    if sys.platform == "win32":
        return {"maximized": True}
    return {"maximized": False}


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def resolve_streamlit_script_path() -> Path:
    if is_frozen_app():
        frozen_root = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
        return frozen_root / "app.py"
    return PROJECT_ROOT / "app.py"


def streamlit_url(port: int) -> str:
    return f"http://{STREAMLIT_HOST}:{int(port)}"


def streamlit_health_url(port: int) -> str:
    return f"{streamlit_url(port)}/_stcore/health"


def build_streamlit_command(port: int) -> list[str]:
    python_path = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not python_path.exists():
        raise DesktopWrapperLaunchError(
            "The virtual environment is missing. Run ./install_mac.sh before launching the desktop app."
        )

    return [
        str(python_path),
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app.py"),
        "--server.headless",
        "true",
        "--server.address",
        STREAMLIT_HOST,
        "--server.port",
        str(int(port)),
        "--browser.gatherUsageStats",
        "false",
    ]


def build_streamlit_flag_options(port: int) -> dict[str, object]:
    return {
        "global_developmentMode": False,
        "server_headless": True,
        "server_address": STREAMLIT_HOST,
        "server_port": int(port),
        "browser_gatherUsageStats": False,
        "client_toolbarMode": "minimal",
        "client_showSidebarNavigation": False,
        "theme_base": "dark",
    }


def start_streamlit_server(port: int) -> subprocess.Popen[str]:
    ensure_runtime_dirs()
    env = os.environ.copy()
    env.setdefault("BROWSER", "none")
    env["PYTHONUNBUFFERED"] = "1"
    stdout_handle = APP_STDOUT_LOG_PATH.open("a", encoding="utf-8")
    stderr_handle = APP_STDERR_LOG_PATH.open("a", encoding="utf-8")
    process = subprocess.Popen(
        build_streamlit_command(port),
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    return process


def start_embedded_streamlit_server(port: int) -> threading.Thread:
    try:
        from streamlit.web import bootstrap
    except Exception as exc:  # pragma: no cover - depends on frozen runtime
        raise DesktopWrapperLaunchError("Streamlit bootstrap is unavailable in the packaged desktop runtime.") from exc

    script_path = resolve_streamlit_script_path()
    if not script_path.exists():
        raise DesktopWrapperLaunchError(f"Bundled app.py was not found at {script_path}.")

    def _run_streamlit() -> None:
        original_signal_setup = bootstrap._set_up_signal_handler
        bootstrap._set_up_signal_handler = lambda server: None
        try:
            bootstrap.load_config_options(build_streamlit_flag_options(port))
            bootstrap.run(
                str(script_path),
                False,
                [],
                build_streamlit_flag_options(port),
            )
        finally:
            bootstrap._set_up_signal_handler = original_signal_setup

    thread = threading.Thread(target=_run_streamlit, daemon=True, name="jaa-streamlit-embedded")
    thread.start()
    return thread


def wait_for_streamlit(port: int, process: subprocess.Popen[str], timeout_seconds: float = STREAMLIT_BOOT_TIMEOUT_SECONDS) -> None:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    health_url = streamlit_health_url(port)
    while time.time() < deadline:
        if process.poll() is not None:
            raise DesktopWrapperLaunchError(f"Streamlit exited early with code {process.returncode}.")
        try:
            response = requests.get(health_url, timeout=1.5)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.35)
    raise DesktopWrapperLaunchError("Timed out waiting for the local Streamlit server to become healthy.")


def stop_streamlit_server(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return

    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=3)
        except Exception:
            pass


def stop_embedded_server() -> None:
    os._exit(0)


def _monitor_server(window: object, process: subprocess.Popen[str]) -> None:
    maximized_once = False
    while True:
        if sys.platform == "win32" and not maximized_once:
            try:
                maximize = getattr(window, "maximize", None)
                if callable(maximize):
                    maximize()
                    maximized_once = True
            except Exception:
                pass
        if process.poll() is not None:
            try:
                destroy = getattr(window, "destroy", None)
                if callable(destroy):
                    destroy()
            except Exception:
                pass
            return
        time.sleep(0.5)


def _monitor_embedded_server(window: object) -> None:
    maximized_once = False
    while True:
        time.sleep(0.5)
        if sys.platform == "win32" and not maximized_once:
            try:
                maximize = getattr(window, "maximize", None)
                if callable(maximize):
                    maximize()
                    maximized_once = True
            except Exception:
                pass
        try:
            _ = window.title
        except Exception:
            return


def launch_desktop_window() -> int:
    try:
        import webview
    except Exception as exc:  # pragma: no cover - import failure depends on local env
        raise DesktopWrapperLaunchError(
            "pywebview is not installed. Run ./install_mac.sh or pip install -r requirements.txt first."
        ) from exc

    port = resolve_desktop_port()
    process: subprocess.Popen[str] | None = None
    embedded_mode = is_frozen_app()

    if embedded_mode:
        start_embedded_streamlit_server(port)
    else:
        process = start_streamlit_server(port)
        atexit.register(stop_streamlit_server, process)

    wait_for_streamlit(port, process if process is not None else _EmbeddedServerSentinel())

    window_width, window_height, min_size = resolve_window_dimensions()
    launch_flags = resolve_window_launch_flags()
    window = webview.create_window(
        f"{APP_NAME} {APP_VERSION}",
        streamlit_url(port),
        width=window_width,
        height=window_height,
        min_size=min_size,
        maximized=bool(launch_flags.get("maximized", False)),
        text_select=True,
    )

    def _on_closed() -> None:
        if embedded_mode:
            stop_embedded_server()
        else:
            stop_streamlit_server(process)

    window.events.closed += _on_closed

    auto_close_seconds = resolve_auto_close_seconds()
    if auto_close_seconds > 0:
        def _auto_close() -> None:
            time.sleep(auto_close_seconds)
            try:
                window.destroy()
            except Exception:
                pass

        threading.Thread(target=_auto_close, daemon=True, name="jaa-desktop-autoclose").start()

    gui = resolve_webview_gui()
    if embedded_mode:
        webview.start(_monitor_embedded_server, args=(window,), gui=gui)
    else:
        webview.start(_monitor_server, args=(window, process), gui=gui)
    return 0


def main() -> int:
    try:
        return launch_desktop_window()
    except DesktopWrapperLaunchError as exc:
        print(f"{APP_NAME} desktop wrapper could not launch: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


class _EmbeddedServerSentinel:
    def poll(self) -> None:
        return None

    @property
    def returncode(self) -> None:
        return None
