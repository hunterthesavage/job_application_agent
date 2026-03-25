def test_system_status_returns_counts(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.status as status_module
    import services.backup as backup_module
    import config

    inserted = job_store.upsert_job(sample_job_payload)

    monkeypatch.setattr(config, "DATABASE_PATH", temp_db_path, raising=False)
    monkeypatch.setattr(backup_module, "DATABASE_PATH", temp_db_path, raising=False)

    status = status_module.get_system_status()

    assert status["jobs_total"] == "1"
    assert status["jobs_new"] == "1"


def test_system_status_reports_environment_openai_key_source(temp_db_path, monkeypatch):
    import services.status as status_module
    import services.backup as backup_module
    import config

    monkeypatch.setattr(config, "DATABASE_PATH", temp_db_path, raising=False)
    monkeypatch.setattr(backup_module, "DATABASE_PATH", temp_db_path, raising=False)
    monkeypatch.setattr(
        status_module,
        "get_openai_api_key_details",
        lambda: {
            "active_key_present": True,
            "active_key_masked": "sk-e********1234",
            "active_source": "environment",
        },
        raising=False,
    )

    status = status_module.get_system_status()

    assert status["openai_api_key_status"] == "Configured"
    assert status["openai_api_key_source"] == "Environment key"
    assert status["openai_api_key_masked"] == "sk-e********1234"
