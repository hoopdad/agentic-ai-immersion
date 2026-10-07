from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "labs"))

from common import foundry_env
import lab_helpers


class NotebookEnvironmentTests(unittest.TestCase):
    def test_defaults_do_not_enable_redis(self) -> None:
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(foundry_env, "ENV_FILE_CANDIDATES", ()):
            env = foundry_env.load_env()
        self.assertNotIn("MARKETPLACE_REDIS_URL", env)
        self.assertNotIn("MARKETPLACE_REDIS_URL", foundry_env.DEFAULTS)

    def test_exported_values_remain_available(self) -> None:
        with patch.dict(os.environ, {"FOUNDRY_PROJECT_ENDPOINT": "https://example.test/project"}), \
                patch.object(foundry_env, "ENV_FILE_CANDIDATES", ()):
            self.assertEqual(
                foundry_env.load_env()["FOUNDRY_PROJECT_ENDPOINT"],
                "https://example.test/project",
            )

    def test_preflight_does_not_require_redis(self) -> None:
        source = (ROOT / "tools/preflight.py").read_text(encoding="utf-8")
        self.assertNotIn('"redis"', source)
        self.assertNotIn("MARKETPLACE_REDIS_URL", source)

    def test_pipeline_uses_blob_history_settings(self) -> None:
        paths = list((ROOT / "labs").glob("lab*-operate-hosted-agents/.github/workflows/agent-ci.yml"))
        self.assertEqual(len(paths), 1)
        source = paths[0].read_text(encoding="utf-8")
        self.assertNotIn("MARKETPLACE_REDIS_URL", source)
        self.assertIn("MARKETPLACE_BLOB_STORAGE_URL", source)
        self.assertIn("MARKETPLACE_BLOB_STORAGE_CONTAINER", source)

    def test_missing_checkpoint_points_to_notebooks(self) -> None:
        with patch.object(lab_helpers, "artifact_path", return_value=ROOT / "labs/artifacts/missing.json"):
            with self.assertRaises(SystemExit) as error:
                lab_helpers.require_artifact("lab1", "project.json", through=1, caller="lab2")
        self.assertIn("walkthrough notebooks through Lab 1", str(error.exception))
        self.assertNotIn("python catch_up.py", str(error.exception))


if __name__ == "__main__":
    unittest.main()
