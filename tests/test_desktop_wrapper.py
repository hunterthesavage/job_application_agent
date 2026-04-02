from services.desktop_wrapper import (
    build_streamlit_command,
    find_free_port,
    resolve_window_dimensions,
    streamlit_health_url,
    streamlit_url,
)


def test_find_free_port_returns_positive_integer() -> None:
    port = find_free_port()
    assert isinstance(port, int)
    assert port > 0


def test_streamlit_urls_use_localhost_health_endpoint() -> None:
    assert streamlit_url(8505) == "http://127.0.0.1:8505"
    assert streamlit_health_url(8505) == "http://127.0.0.1:8505/_stcore/health"


def test_build_streamlit_command_uses_headless_local_server() -> None:
    command = build_streamlit_command(8510)
    assert command[1:4] == ["-m", "streamlit", "run"]
    assert "--server.headless" in command
    assert "--server.address" in command
    assert "--server.port" in command
    assert "127.0.0.1" in command
    assert "8510" in command


def test_resolve_window_dimensions_returns_usable_bounds() -> None:
    width, height, min_size = resolve_window_dimensions()
    assert width >= 1024
    assert height >= 720
    assert min_size[0] < width
    assert min_size[1] < height
