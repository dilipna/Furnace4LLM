"""Forge never commits CI workflow files through the App (GitHub's separate `workflows`
permission, which Furnace does not request); the first live run hit 403 on exactly this."""

from furnace.github.flows import split_workflow_files, workflow_note


def test_workflow_files_are_held_back_and_shown_to_the_reviewer():
    files = {
        "tests/furnace/test_prefix.py": "def test(): pass\n",
        ".github/workflows/furnace.yml": "name: furnace\non: pull_request\n",
        "furnace_harness.py": "x = 1\n",
    }
    keep, held = split_workflow_files(files)
    assert set(keep) == {"tests/furnace/test_prefix.py", "furnace_harness.py"}
    assert set(held) == {".github/workflows/furnace.yml"}
    note = workflow_note(held)
    assert ".github/workflows/furnace.yml" in note
    assert "name: furnace" in note and "```yaml" in note
    assert "workflows" in note and "permission" in note


def test_no_workflow_files_means_nothing_held_back():
    keep, held = split_workflow_files({"a.py": "1\n"})
    assert keep == {"a.py": "1\n"} and held == {}
