from services import app_control


def test_write_and_read_server_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "jaa_server.pid"
    monkeypatch.setattr(app_control, "APP_SERVER_PID_FILE", pid_file)
    monkeypatch.setattr(app_control, "DATA_DIR", tmp_path)

    app_control.write_server_pid(4321)

    assert app_control.read_server_pid() == 4321


def test_clear_server_pid_respects_expected_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "jaa_server.pid"
    monkeypatch.setattr(app_control, "APP_SERVER_PID_FILE", pid_file)
    monkeypatch.setattr(app_control, "DATA_DIR", tmp_path)

    app_control.write_server_pid(1111)
    app_control.clear_server_pid(expected_pid=2222)

    assert pid_file.exists()

    app_control.clear_server_pid(expected_pid=1111)

    assert not pid_file.exists()


def test_request_process_shutdown_clears_pid_and_exits(tmp_path, monkeypatch):
    pid_file = tmp_path / "jaa_server.pid"
    monkeypatch.setattr(app_control, "APP_SERVER_PID_FILE", pid_file)
    monkeypatch.setattr(app_control, "DATA_DIR", tmp_path)
    monkeypatch.setattr(app_control.os, "getpid", lambda: 9876)
    monkeypatch.setattr(app_control.time, "sleep", lambda _seconds: None)

    exit_calls: list[int] = []
    monkeypatch.setattr(app_control.os, "_exit", lambda code: exit_calls.append(code))

    shutdown_thread = app_control.request_process_shutdown()
    shutdown_thread.join(timeout=2)

    assert exit_calls == [0]
    assert not pid_file.exists()
