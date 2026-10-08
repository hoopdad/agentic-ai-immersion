from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import notebook_parts


class NotebookPartCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = Path(self.directory.name) / "artifacts"
        self.path = self.artifacts / "lab2" / "part_a.json"
        self.context = {"project_resource_id": "/projects/demo", "resource_suffix": "jd-4821"}
        self.evidence = self.path.parent / "local_checks.json"
        self.evidence.parent.mkdir(parents=True)
        self.evidence.write_text('{"passed": true}\n', encoding="utf-8")

    def publish(self, **kwargs) -> dict:
        return notebook_parts.write_checkpoint(
            self.path, lab="lab2", part="a", context=self.context,
            evidence=[self.evidence], **kwargs,
        )

    def read(self, **kwargs) -> dict:
        return notebook_parts.read_checkpoint(
            self.path, lab="lab2", part="a", context=kwargs.get("context", self.context),
        )

    def test_fresh_process_state_is_json_and_evidence_is_fingerprinted(self) -> None:
        self.publish(state={"agent_name": "concierge-jd-4821", "version": None})
        self.assertEqual(self.read()["state"]["agent_name"], "concierge-jd-4821")
        self.assertEqual(json.loads(self.path.read_text())["evidence"][0]["path"],
                         "lab2/local_checks.json")

    def test_missing_checkpoint_blocks_part_b(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Run Lab 3"):
            self.read()

    def test_artifact_namespaces_map_to_consecutive_learner_numbers(self) -> None:
        numbers = [number for parts in notebook_parts.LAB_NUMBERS.values() for number in parts.values()]
        self.assertEqual(numbers, list(range(1, 15)))
        self.assertEqual(notebook_parts.lab_label("stretch7", "b"), "Lab 14")

    def test_changed_context_blocks_part_b(self) -> None:
        self.publish()
        with self.assertRaisesRegex(RuntimeError, "current project/model context"):
            self.read(context={**self.context, "resource_suffix": "another-user"})

    def test_changed_or_missing_evidence_blocks_part_b(self) -> None:
        self.publish()
        self.evidence.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "evidence changed"):
            self.read()
        self.evidence.unlink()
        with self.assertRaisesRegex(RuntimeError, "evidence is missing"):
            self.read()

    def test_corrupt_checkpoint_blocks_part_b(self) -> None:
        self.path.write_text("not JSON", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "valid checkpoint"):
            self.read()

    def test_no_credentials_or_sas_in_saved_state(self) -> None:
        for state in ({"access_token": "not-a-real-token"},
                      {"url": "https://example.test/blob?sig=not-a-real-signature"},
                      {"storage": "AccountKey=not-a-real-key"}):
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.publish(state=state)
        self.assertFalse(self.path.exists())

    def test_evidence_cannot_escape_artifacts(self) -> None:
        outside = Path(self.directory.name) / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            notebook_parts.write_checkpoint(self.path, lab="lab2", part="a",
                                            context=self.context, evidence=[outside])

    def test_scope_does_not_capture_arbitrary_environment(self) -> None:
        env = {key: name for name, key in notebook_parts.SCOPE_KEYS.items()}
        env["AZURE_OPENAI_API_KEY"] = "not-a-real-key"
        self.assertEqual(set(notebook_parts.scope(env)), set(notebook_parts.SCOPE_KEYS))
        with self.assertRaises(ValueError):
            notebook_parts.scope({})


if __name__ == "__main__":
    unittest.main()
