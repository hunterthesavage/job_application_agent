def test_health_check_passes_core_checks(temp_db_path, patch_backup_dir, monkeypatch):
    import config
    import services.backup as backup_module
    import services.health as health_module

    monkeypatch.setattr(config, "DATABASE_PATH", temp_db_path, raising=False)
    monkeypatch.setattr(health_module, "DATABASE_PATH", temp_db_path, raising=False)
    monkeypatch.setattr(backup_module, "DATABASE_PATH", temp_db_path, raising=False)

    backup_module.backup_database()
    result = health_module.run_health_check()

    assert result["database_exists"] is True
    assert result["required_tables_ok"] is True
    assert result["latest_backup_exists"] is True
