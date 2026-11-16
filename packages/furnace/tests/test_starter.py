import json
from pathlib import Path

import pytest
from furnace import starter
from furnace.cli import main


def test_real_kit_does_not_execute_model_load_weights_or_copy_secrets(tmp_path, monkeypatch):
    project = tmp_path / "research-model"
    project.mkdir()
    marker = tmp_path / "executed"
    (project / "model.py").write_text(f"from pathlib import Path; Path({str(marker)!r}).touch()")
    (project / "weights.pt").write_bytes(b"not a valid checkpoint")
    (project / ".env").write_text("SECRET=private-value-do-not-copy")
    (project / "config.json").write_text(
        json.dumps(
            {
                "model_type": "custom_recurrent",
                "api_key": "private-value-do-not-copy",
                "auto_map": {"AutoModel": "model.Custom"},
            }
        )
    )
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        if path.suffix == ".pt" or path.name == ".env":
            pytest.fail("weights/secrets must never be read")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    output = tmp_path / "kit"
    result = starter.export_starter(project, output)
    assert not marker.exists()
    assert result["file_evidence"]["checkpoint_file_present"]
    assert result["declared_metadata"] == {
        "declared_model_type": "custom_recurrent",
        "custom_code_declared": True,
    }
    assert all(c["status"] == "unverified" for c in result["capabilities"])
    assert not result["execution_performed"] and not result["provisioning_performed"]
    assert len(list(output.iterdir())) == 5
    for file in output.iterdir():
        assert "private-value-do-not-copy" not in file.read_text()
    assert json.loads((output / "assessment.json").read_text()) == result
    assert json.loads((output / "model-contract.json").read_text())["architecture"] is None
    assert (
        json.loads((output / "evaluation-cases.example.jsonl").read_text())["status"] == "not_run"
    )


def test_custom_project_needs_no_transformer_config(tmp_path):
    (tmp_path / "research.py").write_text("# arbitrary architecture")
    result = starter.assess_model(tmp_path)
    assert result["file_evidence"]["python_source_present"]
    assert not result["file_evidence"]["configuration_file_present"]
    assert result["declared_metadata"] == {}
    assert all(c["status"] == "unverified" for c in result["capabilities"])


@pytest.mark.parametrize("raw", ["[]", "{bad json", "\ufeff{}", '{"model_type":"bad\\nvalue"}'])
def test_bad_or_unsafe_metadata_never_becomes_an_architecture_claim(tmp_path, raw):
    (tmp_path / "config.json").write_text(raw, encoding="utf-8")
    result = starter.assess_model(tmp_path)
    assert "declared_model_type" not in result["declared_metadata"]
    assert not result["execution_performed"]


def test_oversized_config_is_not_parsed(tmp_path, monkeypatch):
    monkeypatch.setattr(starter, "MAX_CONFIG_BYTES", 10)
    (tmp_path / "config.json").write_text("{" + " " * 50 + "}")
    assert "size limit" in starter.assess_model(tmp_path)["warnings"][0]


def test_inventory_limit_fails_before_writing_kit(tmp_path, monkeypatch):
    project = tmp_path / "model"
    project.mkdir()
    (project / "a.py").touch()
    (project / "b.py").touch()
    monkeypatch.setattr(starter, "MAX_FILES", 1)
    with pytest.raises(ValueError, match="inventory exceeds"):
        starter.export_starter(project, tmp_path / "kit")
    assert not (tmp_path / "kit").exists()


def test_output_refuses_existing_directory_and_source_mutation(tmp_path):
    project = tmp_path / "model"
    project.mkdir()
    output = tmp_path / "kit"
    output.mkdir()
    (output / "keep").write_text("unchanged")
    with pytest.raises(FileExistsError):
        starter.export_starter(project, output)
    assert (output / "keep").read_text() == "unchanged"
    with pytest.raises(ValueError, match="outside"):
        starter.export_starter(project, project / "kit")
    assert list(project.iterdir()) == []


def test_symlinks_are_not_followed(tmp_path):
    project = tmp_path / "model"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "weights.pt").touch()
    try:
        (project / "linked").symlink_to(outside, target_is_directory=True)
        (project / "config.json").symlink_to(outside / "weights.pt")
    except OSError:
        pytest.skip("symlink creation requires OS permission")
    result = starter.assess_model(project)
    assert result["inventory"]["skipped_links"] == 2
    assert not result["file_evidence"]["checkpoint_file_present"]
    assert not result["file_evidence"]["configuration_file_present"]


def test_cli_writes_kit_and_reports_invalid_input(tmp_path, capsys):
    project = tmp_path / "model"
    project.mkdir()
    output = tmp_path / "kit"
    assert main(["starter", str(project), "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "local_static_assessment"
    assert (output / "README.md").is_file()
    assert main(["starter", str(project), "--output", str(output)]) == 1
    assert "already exists" in capsys.readouterr().err
    assert main(["starter", str(tmp_path / "absent"), "--output", str(tmp_path / "other")]) == 1
    assert not (tmp_path / "other").exists()


def test_junction_directories_are_excluded_before_walk(tmp_path, monkeypatch):
    nested = tmp_path / "junction"
    nested.mkdir()
    (nested / "weights.pt").touch()
    monkeypatch.setattr(Path, "is_junction", lambda p: p == nested)
    result = starter.assess_model(tmp_path)
    assert result["inventory"]["skipped_links"] == 1
    assert not result["file_evidence"]["checkpoint_file_present"]
