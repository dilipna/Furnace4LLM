"""An aborted validation must never leave a successful evidence record."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("error", [RuntimeError, SystemExit, KeyboardInterrupt])
@pytest.mark.parametrize("phase", ["startup", "after_check"])
def test_aborted_validation_retains_failed_evidence_and_original_exit(
    tmp_path, monkeypatch, error, phase
):
    spec = importlib.util.spec_from_file_location(
        "model_validation", ROOT / "scripts/validate_managed_model.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "aborted.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_managed_model.py",
            "--model",
            "qwen2.5-0.5b-instruct-q8_0",
            "--out",
            str(output),
        ],
    )
    monkeypatch.setattr(module, "environment", lambda: {"test_only": True})
    monkeypatch.setattr(module, "model_container", lambda scope: [])
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: "")

    def abort(self):
        # Error text may contain private server data; evidence needs only its type.
        raise error("private-error-detail")

    if phase == "startup":
        monkeypatch.setattr(module.Studio, "start", abort)
    else:
        monkeypatch.setattr(module.Studio, "start", lambda self: 0)
        monkeypatch.setattr(
            module.Studio,
            "api",
            lambda *args, **kwargs: httpx.Response(200, json={"id": "a" * 32}),
        )
        original_check = module.check

        def abort_after_check(condition, label, record):
            original_check(condition, label, record)
            raise error("private-error-detail")

        monkeypatch.setattr(module, "check", abort_after_check)
    with pytest.raises(error, match="private-error-detail"):
        module.main()
    record = json.loads(output.read_text())
    assert record["result"] == "failed"
    assert record["completed"] is False
    assert record["failures"] == [f"validation_aborted:{error.__name__}"]
    assert "private-error-detail" not in output.read_text()
    if phase == "after_check":
        assert record["steps"]["select"]["checks"] == {"selection saved": True}
