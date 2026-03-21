def test_backup_creates_copy(temp_db_path, patch_backup_dir, monkeypatch):
    import config
    import services.backup as backup_module

    monkeypatch.setattr(config, "DATABASE_PATH", temp_db_path, raising=False)
    monkeypatch.setattr(backup_module, "DATABASE_PATH", temp_db_path, raising=False)

    backup_path = backup_module.backup_database()

    assert backup_path.exists()
    assert backup_path.parent == patch_backup_dir
    assert backup_path.name.startswith("job_agent_")
