import pytest
from furnace.runtime.lease import WorkspaceBusy, WorkspaceLease
from furnace_api import desktop_cleanup


def test_optional_uninstall_refuses_unknown_cleanup_before_deleting_records(tmp_path, monkeypatch):
    db = tmp_path / "studio.sqlite3"
    db.write_bytes(b"keep")
    monkeypatch.setattr(desktop_cleanup, "cleanup", lambda *a, **k: {"docker": "unavailable"})
    with pytest.raises(RuntimeError, match="data retained"):
        desktop_cleanup.remove_owned(tmp_path, True, True)
    assert db.read_bytes() == b"keep"


def test_optional_uninstall_removes_only_owned_records_and_preserves_models(tmp_path, monkeypatch):
    for name in ("studio.sqlite3", "model.gguf", "export.zip"):
        (tmp_path / name).write_bytes(b"data")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/operations.jsonl").write_text("metadata")
    calls = []
    monkeypatch.setattr(desktop_cleanup, "cleanup", lambda *a, **k: calls.append(k) or {})
    desktop_cleanup.remove_owned(tmp_path, records=True, weights=False)
    assert not (tmp_path / "studio.sqlite3").exists()
    assert not (tmp_path / "logs").exists()
    assert (tmp_path / "model.gguf").exists() and (tmp_path / "export.zip").exists()
    assert calls == [{"dry_run": False}]


def test_optional_uninstall_cannot_delete_a_live_workspaces_records(tmp_path, monkeypatch):
    def real_lease(*args, **kwargs):
        with WorkspaceLease(tmp_path):
            return {}

    monkeypatch.setattr(desktop_cleanup, "cleanup", real_lease)
    with WorkspaceLease(tmp_path), pytest.raises(WorkspaceBusy):
        desktop_cleanup.remove_owned(tmp_path, records=True, weights=False)
