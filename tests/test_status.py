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
