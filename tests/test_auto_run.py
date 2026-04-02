def test_format_auto_run_summary_for_custom_schedule():
    from services.auto_run import format_auto_run_summary

    summary = format_auto_run_summary(
        {
            "auto_run_enabled": "true",
            "auto_run_frequency": "custom_weekly",
            "auto_run_time": "07:30",
            "auto_run_days": "mon,wed,fri",
        }
    )

    assert summary == "Runs on Mon, Wed, Fri at 07:30."


def test_configure_auto_run_schedule_builds_launchd_plist(monkeypatch, tmp_path):
    import services.auto_run as auto_run

    launch_agent_path = tmp_path / "com.jobapplicationagent.autorun.plist"
    commands = []

    monkeypatch.setattr(auto_run.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(auto_run, "get_launch_agent_path", lambda: launch_agent_path)
    monkeypatch.setattr(auto_run, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        auto_run,
        "_run_subprocess",
        lambda command: (commands.append(command) or (True, "")),
    )

    result = auto_run.configure_auto_run_schedule(
        {
            "auto_run_enabled": "true",
            "auto_run_frequency": "weekdays",
            "auto_run_time": "06:45",
            "auto_run_days": "mon,tue,wed,thu,fri",
        }
    )

    assert result["ok"] is True
    assert launch_agent_path.exists()
    content = launch_agent_path.read_text(encoding="utf-8")
    assert "StartCalendarInterval" in content
    assert any(command[0] == "launchctl" for command in commands)


def test_disable_auto_run_schedule_removes_launch_agent(monkeypatch, tmp_path):
    import services.auto_run as auto_run

    launch_agent_path = tmp_path / "com.jobapplicationagent.autorun.plist"
    launch_agent_path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(auto_run.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(auto_run, "get_launch_agent_path", lambda: launch_agent_path)
    monkeypatch.setattr(auto_run, "_run_subprocess", lambda command: (True, ""))

    result = auto_run.disable_auto_run_schedule()

    assert result["ok"] is True
    assert not launch_agent_path.exists()


def test_run_subprocess_hides_console_on_windows(monkeypatch):
    import services.auto_run as auto_run

    captured_kwargs = {}

    class DummyCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    class DummyStartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = None

    monkeypatch.setattr(auto_run.platform, "system", lambda: "Windows")
    monkeypatch.setattr(auto_run.subprocess, "STARTUPINFO", DummyStartupInfo, raising=False)
    monkeypatch.setattr(auto_run.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(auto_run.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    def fake_run(command, **kwargs):
        captured_kwargs.update(kwargs)
        return DummyCompleted()

    monkeypatch.setattr(auto_run.subprocess, "run", fake_run)

    ok, _ = auto_run._run_subprocess(["schtasks", "/Query"])

    assert ok is True
    assert captured_kwargs["creationflags"] == 0x08000000
    assert captured_kwargs["startupinfo"].wShowWindow == 0
