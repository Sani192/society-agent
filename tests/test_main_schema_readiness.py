import pytest

import app.main as main


def test_enforce_schema_readiness_creates_schema_for_local(monkeypatch):
    create_all_called = {"called": False}

    def _fake_create_all(*, bind):
        create_all_called["called"] = bind is main.engine

    monkeypatch.setattr(main.settings, "APP_ENV_NORMALIZED", "local")
    monkeypatch.setattr(main.Base.metadata, "create_all", _fake_create_all)

    main._enforce_schema_readiness()

    assert create_all_called["called"] is True


def test_enforce_schema_readiness_raises_when_staging_has_pending(monkeypatch):
    monkeypatch.setattr(main.settings, "APP_ENV_NORMALIZED", "staging")
    monkeypatch.setattr(main.settings, "APP_ENV", "staging")
    monkeypatch.setattr(main.settings, "STARTUP_MIGRATIONS_ENABLED", False)
    monkeypatch.setattr(main, "_run_migration_pipeline", lambda: None)
    monkeypatch.setattr(main, "_pending_schema_differences", lambda: (["societies", "users"], {}))

    with pytest.raises(RuntimeError, match="Run the migration pipeline"):
        main._enforce_schema_readiness()


def test_enforce_schema_readiness_skips_when_staging_has_no_pending(monkeypatch):
    monkeypatch.setattr(main.settings, "APP_ENV_NORMALIZED", "staging")
    monkeypatch.setattr(main.settings, "STARTUP_MIGRATIONS_ENABLED", False)
    monkeypatch.setattr(main, "_run_migration_pipeline", lambda: None)
    monkeypatch.setattr(main, "_pending_schema_differences", lambda: ([], {}))

    main._enforce_schema_readiness()


def test_app_env_normalized_falls_back_to_app_env(monkeypatch):
    monkeypatch.setattr(main.settings, "APP_ENV_NORMALIZED", "")
    monkeypatch.setattr(main.settings, "APP_ENV", "Production")

    assert main._app_env_normalized() == "production"


def test_migration_file_paths_filters_and_sorts(tmp_path, monkeypatch):
    (tmp_path / "002_second.sql").write_text("-- second", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("-- first", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("ignored", encoding="utf-8")

    monkeypatch.setattr(main, "MIGRATIONS_DIR", tmp_path)

    assert [path.name for path in main._migration_file_paths()] == ["001_first.sql", "002_second.sql"]


def test_staging_runs_pipeline_only_when_enabled(monkeypatch):
    state = {"pipeline_called": False}
    monkeypatch.setattr(main.settings, "APP_ENV_NORMALIZED", "staging")
    monkeypatch.setattr(main.settings, "STARTUP_MIGRATIONS_ENABLED", True)
    monkeypatch.setattr(main, "_pending_schema_differences", lambda: ([], {}))

    def _fake_pipeline():
        state["pipeline_called"] = True

    monkeypatch.setattr(main, "_run_migration_pipeline", _fake_pipeline)

    main._enforce_schema_readiness()

    assert state["pipeline_called"] is True


def test_enforce_schema_readiness_raises_when_staging_has_missing_columns(monkeypatch):
    monkeypatch.setattr(main.settings, "APP_ENV_NORMALIZED", "staging")
    monkeypatch.setattr(main.settings, "APP_ENV", "staging")
    monkeypatch.setattr(main.settings, "STARTUP_MIGRATIONS_ENABLED", False)
    monkeypatch.setattr(main, "_run_migration_pipeline", lambda: None)
    monkeypatch.setattr(
        main,
        "_pending_schema_differences",
        lambda: ([], {"audit_logs": ["metadata_json"]}),
    )

    with pytest.raises(RuntimeError, match="Missing columns: audit_logs: metadata_json"):
        main._enforce_schema_readiness()
