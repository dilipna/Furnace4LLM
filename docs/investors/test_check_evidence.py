"""Exercise evidence guard failure modes without network or product dependencies."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from check_evidence import ROOT, validate


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "room"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))

    def rewrite(self, file, before, after):
        path = self.root / file
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text)
        path.write_text(text.replace(before, after), encoding="utf-8")

    def registry(self, mutate):
        path = self.root / "claims.json"
        claims = json.loads(path.read_text(encoding="utf-8"))
        mutate(claims)
        path.write_text(json.dumps(claims), encoding="utf-8")

    def test_valid_room(self):
        self.assertEqual(validate(self.root), [])

    def test_raw_evidence_change_is_rejected(self):
        self.rewrite("evidence/qwen-cpu.json", '"passed": 11', '"passed": 12')
        errors = "\n".join(validate(self.root))
        self.assertIn("hash differs", errors)
        self.assertIn("raw value", errors)

    def test_uncited_number_is_rejected(self):
        with (self.root / "memo.md").open("a", encoding="utf-8") as stream:
            stream.write("\nWe have 900 customers.\n")
        self.assertIn("unregistered number 900", "\n".join(validate(self.root)))

    def test_wrong_displayed_value_is_rejected(self):
        self.rewrite("memo.md", "[11](evidence/qwen-cpu.json", "[99](evidence/qwen-cpu.json")
        self.assertIn("claim label differs", "\n".join(validate(self.root)))

    def test_broken_link_and_anchor_are_rejected(self):
        with (self.root / "memo.md").open("a", encoding="utf-8") as stream:
            stream.write("\n[Missing](missing.md) [Bad anchor](market.md#nonexistent)\n")
        errors = "\n".join(validate(self.root))
        self.assertIn("missing link", errors)
        self.assertIn("missing anchor", errors)

    def test_wrong_claim_target_is_rejected(self):
        self.rewrite("memo.md", "[11](evidence/qwen-cpu.json", "[11](evidence/granite-cpu.json")
        self.assertIn("claim target differs", "\n".join(validate(self.root)))

    def test_wrong_calculation_is_rejected(self):
        self.registry(lambda c: c["control-month"].update(value=999, label="$999"))
        self.assertIn("calculated", "\n".join(validate(self.root)))

    def test_cycle_is_rejected(self):
        self.registry(lambda c: c["gpu-hour"].update(inputs=["gpu-hour"]))
        self.assertIn("cyclic claim", "\n".join(validate(self.root)))

    def test_unsourced_external_value_is_rejected(self):
        self.registry(lambda c: c["accepted"].update(value=9999, label="9,999"))
        self.assertIn("source text/value mismatch", "\n".join(validate(self.root)))


if __name__ == "__main__":
    unittest.main()
