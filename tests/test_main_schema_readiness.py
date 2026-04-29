from unittest.mock import MagicMock

import app.main as main


def test_enforce_schema_readiness_runs_alembic_upgrade(monkeypatch):
    mock_inspect = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["alembic_version", "societies"]
    mock_inspect.return_value = mock_inspector
    monkeypatch.setattr(main, "inspect", mock_inspect)

    mock_upgrade = MagicMock()
    monkeypatch.setattr(main.alembic.command, "upgrade", mock_upgrade)

    mock_stamp = MagicMock()
    monkeypatch.setattr(main.alembic.command, "stamp", mock_stamp)

    main._enforce_schema_readiness()

    mock_upgrade.assert_called_once()
    mock_stamp.assert_not_called()


def test_enforce_schema_readiness_stamps_legacy_db(monkeypatch):
    mock_inspect = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["societies"]
    mock_inspect.return_value = mock_inspector
    monkeypatch.setattr(main, "inspect", mock_inspect)

    mock_upgrade = MagicMock()
    monkeypatch.setattr(main.alembic.command, "upgrade", mock_upgrade)

    mock_stamp = MagicMock()
    monkeypatch.setattr(main.alembic.command, "stamp", mock_stamp)

    main._enforce_schema_readiness()

    mock_stamp.assert_called_once()
    mock_upgrade.assert_called_once()
