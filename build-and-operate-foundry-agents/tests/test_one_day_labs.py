"""Offline one-day generation, learner handoffs and product isolation."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
import sync_one_day_labs as short
from common import foundry_env, notebook_parts
from py_to_ipynb import build_notebook, validate_notebook

CONTEXT = {
    "project_resource_id": "/subscriptions/offline/resourceGroups/workshop/providers/Microsoft.CognitiveServices/accounts/account/projects/project",
    "project_endpoint": "https://offline.example.test",
    "resource_suffix": "offline",
    "chat_deployment": "chat-offline",
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def snapshot(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}


class OneDayTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="one-day-workshop-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve() / "build-and-operate-foundry-agents"
        self.root.mkdir()
        for folder in ("3-day-labs", "shared", "common", "data"):
            shutil.copytree(ROOT / folder, self.root / folder, ignore=shutil.ignore_patterns(
                "artifacts", "__pycache__", ".azure", ".env", ".env.*", ".vendored*"))
        self.originals = snapshot(self.root / "3-day-labs")

    def test_sync_subset_parity_and_idempotence_without_canonical_writes(self) -> None:
        short.sync(self.root)
        target = self.root / "1-day-labs"
        notebooks = sorted(target.glob("lab*/*.ipynb"))
        self.assertEqual([path.parent.name for path in notebooks], ["lab01", "lab04", "lab07"])
        for path in notebooks:
            source = next(path.parent.glob("*.py"))
            notebook = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(notebook, build_notebook(source.read_text(encoding="utf-8"), seed=source.stem))
            self.assertFalse(validate_notebook(notebook))
            self.assertNotIn(b"\r", path.read_bytes())
            for cell in notebook["cells"]:
                if cell["cell_type"] == "code":
                    ast.parse("".join(cell["source"]))
                    self.assertEqual(cell["outputs"], [])
                    self.assertIsNone(cell["execution_count"])
        before = snapshot(target)
        short.sync(self.root, check=True)
        short.sync(self.root)
        self.assertEqual(snapshot(target), before)
        self.assertEqual(snapshot(self.root / "3-day-labs"), self.originals)

    def test_check_reports_upstream_drift_and_sync_updates_clean_copies(self) -> None:
        short.sync(self.root)
        upstream = short.source_for(self.root / "3-day-labs", 3)
        upstream.write_text(upstream.read_text(encoding="utf-8").replace(
            "reads the real tool and agent implementation", "reads the accepted tool and agent implementation"), encoding="utf-8")
        before = snapshot(self.root / "1-day-labs")
        with self.assertRaisesRegex(ValueError, "sync drift"):
            short.sync(self.root, check=True)
        self.assertEqual(snapshot(self.root / "1-day-labs"), before)
        short.sync(self.root)
        short.sync(self.root, check=True)
        source = next((self.root / "1-day-labs/lab04").glob("*.py"))
        self.assertIn("accepted tool and agent implementation", source.read_text(encoding="utf-8"))

    def test_sync_preserves_learner_edits_and_requires_explicit_overwrite(self) -> None:
        short.sync(self.root)
        product = self.root / "1-day-labs/products/hosted-agent-basics/hosted/main.py"
        product.write_text(product.read_text(encoding="utf-8") + "\n# learner edit\n", encoding="utf-8")
        before = snapshot(self.root / "1-day-labs")
        with self.assertRaisesRegex(ValueError, "Local edits"):
            short.sync(self.root)
        with self.assertRaisesRegex(ValueError, "sync drift"):
            short.sync(self.root, check=True)
        self.assertEqual(snapshot(self.root / "1-day-labs"), before)
        short.sync(self.root, overwrite=True)
        short.sync(self.root, check=True)
        self.assertNotIn("learner edit", product.read_text(encoding="utf-8"))

    def test_sync_excludes_credentials_caches_outputs_and_prepared_packages(self) -> None:
        folder = self.root / "shared/hosted-agent-basics/hosted"
        for name in (".env", ".env.secret", ".azure/state.json", "common/vendor.py",
                     "data/output.json", "__pycache__/cache.pyc", "runtime.json", "run.log"):
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("must not copy")
        outputs = short.render(self.root)
        for name in outputs:
            self.assertFalse(any(token in name for token in (".env", ".azure", "vendor.py", "output.json",
                                                             "__pycache__", "runtime.json", "run.log")))

    def test_lab4_real_acceptance_precedes_deployment_and_rejects_false_or_changed_evidence(self) -> None:
        text = short.adapt_source(self.root / "3-day-labs", 4)[1]
        notebook = build_notebook(text)
        cells = {int("".join(cell["source"]).splitlines()[0].split("Step 4.")[1].split(" ")[0]): "".join(cell["source"])
                 for cell in notebook["cells"] if cell["cell_type"] == "code"}
        self.assertEqual(sorted(cells), list(range(1, 14)))
        self.assertIn('assert "$3,600"', cells[6])
        self.assertIn('assert "AEP"', cells[7])
        self.assertLess(text.index("Publish local checkpoint"), text.index("Deploy the hosted agent"))
        artifacts = self.root / "1-day-labs/artifacts/lab2"
        artifacts.mkdir(parents=True)
        source = self.root / "main.py"
        source.write_text("# accepted source")
        namespace = {
            "ARTIFACTS": artifacts, "BASELINE_OK": False, "SPONSOR_OK": False, "INSTRUCTION_OK": False,
            "TESTED_SOURCE_SHA256": None, "notebook_parts": notebook_parts, "hashlib": hashlib,
        }
        with self.assertRaisesRegex(RuntimeError, "Complete all local acceptance"):
            exec(cells[8], namespace)
        self.assertFalse((artifacts / "part_a.json").exists())
        from types import SimpleNamespace
        namespace.update({
            "BASELINE_OK": True, "SPONSOR_OK": True, "INSTRUCTION_OK": True,
            "TESTED_SOURCE_SHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "lab2": SimpleNamespace(HOSTED_DIR=self.root), "hosted": {"agent_name": "offline"},
        })
        source.write_text("# changed source")
        with self.assertRaisesRegex(RuntimeError, "Hosted source changed"):
            exec(cells[8], namespace)
        self.assertFalse((artifacts / "part_a.json").exists())
        transcript = artifacts / "transcripts.md"
        transcript.write_text("Northwind $3,600; no recommendation, hand off during AEP.")
        namespace["lab2"].TRANSCRIPTS = transcript
        namespace["TESTED_SOURCE_SHA256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        namespace["ENV"] = dict(zip(
            ("PROJECT_RESOURCE_ID", "FOUNDRY_PROJECT_ENDPOINT", "MARKETPLACE_RESOURCE_SUFFIX",
             "AZURE_AI_MODEL_DEPLOYMENT_NAME"),
            CONTEXT.values(), strict=True))
        short.sync(self.root)
        parts = load("one_day_parts", self.root / "1-day-labs/one_day_parts.py")
        namespace["notebook_parts"] = parts
        exec(cells[8], namespace)
        restored = parts.read_checkpoint(
            artifacts / "part_a.json", lab="lab2", part="a", context=CONTEXT)
        self.assertEqual(restored["state"]["hosted_source_sha256"], namespace["TESTED_SOURCE_SHA256"])
        self.assertEqual(restored["state"]["local_tools"], "passed")
        self.assertEqual(restored["state"]["instruction_boundary"], "passed")

    def test_generated_drivers_and_builds_use_short_products_and_artifacts(self) -> None:
        short.sync(self.root)
        old_path = sys.path[:]
        self.addCleanup(setattr, sys, "path", old_path)
        with patch.dict(sys.modules):
            parts = load("one_day_parts", self.root / "1-day-labs/one_day_parts.py")
            helper = load("lab_helpers", self.root / "1-day-labs/lab_helpers.py")
            env = {
                "MARKETPLACE_RESOURCE_SUFFIX": CONTEXT["resource_suffix"],
                "PROJECT_RESOURCE_ID": CONTEXT["project_resource_id"],
                "FOUNDRY_PROJECT_ENDPOINT": CONTEXT["project_endpoint"],
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": CONTEXT["chat_deployment"],
                "MARKETPLACE_KB_MCP_URL": "https://unwanted.example.test/mcp",
            }
            with patch.object(foundry_env, "load_env", return_value=env):
                basics = helper.load_lab_module("hosted-agent-basics/lab2_hosted_basics.py")
                team = helper.load_lab_module("hosted-multi-agent-handoff/lab4_hosted_multi_agent.py")
            target = self.root / "1-day-labs"
            self.assertTrue(basics.HOSTED_DIR.is_relative_to(target / "products"))
            self.assertTrue(team.HOSTED_DIR.is_relative_to(target / "products"))
            self.assertTrue(basics.ARTIFACTS.is_relative_to(target / "artifacts"))
            self.assertTrue(team.ARTIFACTS.is_relative_to(target / "artifacts"))
            prepare = load("short_basics_prepare", basics.HOSTED_DIR / "prepare.py")
            self.assertEqual(prepare.ROOT, self.root)
            prepare.vendor()
            with patch.object(foundry_env, "load_env", return_value=env):
                with self.assertRaisesRegex(RuntimeError, "Lab 4"):
                    team.build(standalone=True)
            project = target / "artifacts/lab2/hosted.json"
            project.write_text(json.dumps({"agent_name": basics.AGENT_NAME}))
            parts.write_checkpoint(
                project.with_name("part_b.json"), lab="lab2", part="b", context=CONTEXT,
                evidence=[project], state={"deployed_inference": "passed"})
            team.ENV = env
            with patch.object(foundry_env, "load_env", return_value=env):
                record = team.build(standalone=True)
            self.assertNotIn("mcp ", record["knowledge"])
            prepared = team.HOSTED_DIR / "common/marketplace_data.py"
            self.assertTrue(prepared.is_file())
            self.assertEqual(team.require_previous_lab(), {"agent_name": basics.AGENT_NAME})
            specialist = team.HOSTED_DIR / "marketplace_specialists.py"
            self.assertIn('KB_MCP_URL = ""', specialist.read_text(encoding="utf-8"))
            self.assertEqual(snapshot(self.root / "3-day-labs"), self.originals)

    def test_team_notebook_requires_human_decisions_and_source_gates_before_cloud_actions(self) -> None:
        from unittest.mock import MagicMock
        text = short.adapt_source(self.root / "3-day-labs", 7)[1]
        notebook = build_notebook(text)
        cells = {int("".join(cell["source"]).splitlines()[0].split("Step 7.")[1].split(" ")[0]): "".join(cell["source"])
                 for cell in notebook["cells"] if cell["cell_type"] == "code"}
        self.assertEqual(sorted(cells), list(range(1, 9)))
        self.assertIn('lab_helpers.artifact_path("lab2", "part_b.json")', cells[1])
        self.assertNotIn('lab_helpers.artifact_path("lab3"', text)
        self.assertNotIn("auto=True", text)
        self.assertIn('expected_version=DEPLOYED_VERSION', cells[7])
        self.assertIn('expected_version=DEPLOYED_VERSION', cells[8])
        artifacts = self.root / "artifacts/lab4"
        artifacts.mkdir(parents=True)
        driver = MagicMock()
        driver.ARTIFACTS = artifacts
        namespace = {"accepted": {"approval": True}, "driver": driver, "team_server": MagicMock()}
        checkpoint = artifacts / "part_a.json"
        checkpoint.write_text("old success")
        with self.assertRaisesRegex(AssertionError, "explicitly enter approve"):
            exec(cells[5], namespace)
        driver.post_turn.assert_not_called()
        namespace["team_server"].stop.assert_called_once()
        self.assertNotIn("approval", namespace["accepted"])
        self.assertFalse(checkpoint.exists())
        namespace.update({"DEPLOYED_VERSION": "3"})
        checkpoint.write_text("old success")
        namespace["accepted"]["deployed_approval"] = True
        with self.assertRaisesRegex(AssertionError, "explicitly enter approve"):
            exec(cells[8], namespace)
        driver.deployed_turn.assert_not_called()
        self.assertFalse(checkpoint.exists())
        self.assertNotIn("deployed_approval", namespace["accepted"])
        namespace.update({"accepted": {"orchestration": True, "classification": True, "approval": True},
                          "tested_sources": {"source": "accepted"}})
        driver.source_fingerprints.return_value = {"source": "changed"}
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(AssertionError, "Source changed"):
                exec(cells[6], namespace)
            run.assert_not_called()

    def test_sync_retires_old_track_only_if_its_learner_files_are_unmodified(self) -> None:
        short.sync(self.root)
        target = self.root / "1-day-labs"
        retired = target / "lab13/lab13_walkthrough.ipynb"
        retired.parent.mkdir()
        retired.write_text("old generated notebook")
        manifest = target / "sync-manifest.json"
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["outputs"]["lab13/lab13_walkthrough.ipynb"] = hashlib.sha256(retired.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(record))
        retired.write_text("learner changes")
        with self.assertRaisesRegex(ValueError, "Local edits"):
            short.sync(self.root)
        self.assertEqual(retired.read_text(), "learner changes")
        retired.write_text("old generated notebook")
        short.sync(self.root)
        self.assertFalse(retired.exists())
        short.sync(self.root, check=True)

    def test_manifest_paths_cannot_escape_short_target(self) -> None:
        short.sync(self.root)
        manifest = self.root / "1-day-labs/sync-manifest.json"
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["outputs"]["../3-day-labs/README.md"] = "forged"
        manifest.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid generated manifest path"):
            short.sync(self.root, overwrite=True)
        self.assertEqual(snapshot(self.root / "3-day-labs"), self.originals)

    def test_combined_setup_calls_chat_only_and_rejects_changed_plan(self) -> None:
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        short.sync(self.root)
        with patch.dict(sys.modules):
            parts = load("one_day_parts", self.root / "1-day-labs/one_day_parts.py")
            text = short.adapt_source(self.root / "3-day-labs", 1)[1]
            notebook = build_notebook(text)
            cells = {int("".join(cell["source"]).splitlines()[0].split("Step 1.")[1].split(" ")[0]): "".join(cell["source"])
                     for cell in notebook["cells"] if cell["cell_type"] == "code"}
            self.assertEqual(sorted(cells), list(range(1, 11)))
            artifacts = self.root / "1-day-labs/artifacts/lab1"
            artifacts.mkdir(parents=True)
            cli = MagicMock()
            cli.run.return_value = {"choices": [{"message": {"content": "Hello"}}]}
            setup = MagicMock()
            setup.read_project_handoff.return_value = (
                {}, {"tenant_id": "tenant", "subscription_id": "subscription"},
                {"id": "account"}, {"id": CONTEXT["project_resource_id"]})
            setup.endpoints.return_value = (CONTEXT["project_endpoint"], "https://openai.example.test/")
            namespace = {
                "CLI": cli, "project_setup": setup, "ARTIFACTS": artifacts,
                "ARTIFACT": artifacts / "project.json", "SUBSCRIPTION_ID": "subscription",
                "TENANT_ID": "tenant", "ATTENDEE_SUFFIX": "offline", "SUFFIX": "offline",
                "CONTEXT": {"tenant_id": "tenant"}, "PROJECT": {"id": CONTEXT["project_resource_id"]},
                "PROJECT_ENDPOINT": CONTEXT["project_endpoint"], "OPENAI_ENDPOINT": "https://openai.example.test/",
                "CHAT_NAME": "chat-offline", "CHAT_SPEC": {"version": "accepted"},
                "json": json, "notebook_parts": parts,
            }
            exec(cells[9], namespace)
            self.assertEqual(cli.run.call_count, 1)
            self.assertTrue(any("chat/completions" in arg for arg in cli.run.call_args.args))
            self.assertEqual(namespace["SMOKE_TESTS"], {"chat": "passed"})
            namespace["CHAT_SPEC"] = {"version": "changed"}
            with self.assertRaisesRegex(RuntimeError, "exact project and chat"):
                exec(cells[10], namespace)
            setup.write_env.assert_not_called()
            namespace.update({
                "CHAT_SPEC": {"version": "accepted"}, "REPO_ROOT": self.root,
                "datetime": datetime, "timezone": timezone,
                "foundry_env": SimpleNamespace(
                    load_env=lambda: namespace["OUTPUT_ENV"],
                    save_artifact=lambda path, data: path.write_text(json.dumps(data), encoding="utf-8"),
                ),
            })
            exec(cells[10], namespace)
            setup.write_env.assert_called_once()
            verified = json.loads(namespace["ARTIFACT"].read_text(encoding="utf-8"))
            self.assertEqual(verified["smoke_tests"], {"chat": "passed"})
            self.assertNotIn("embedding_deployment", verified)
            self.assertTrue((artifacts / "part_b.json").is_file())
            cli.run.return_value = {"choices": []}
            with self.assertRaisesRegex(RuntimeError, "no assistant text"):
                exec(cells[9], namespace)
            self.assertEqual(namespace["SMOKE_TESTS"], {})
            self.assertFalse((artifacts / "part_b.json").exists())
            self.assertNotIn("EMBEDDING_MODEL_DEPLOYMENT_NAME", text)
            self.assertNotIn("text-embedding", text)
            self.assertEqual(parts.scope({
                "PROJECT_RESOURCE_ID": CONTEXT["project_resource_id"],
                "FOUNDRY_PROJECT_ENDPOINT": CONTEXT["project_endpoint"],
                "MARKETPLACE_RESOURCE_SUFFIX": CONTEXT["resource_suffix"],
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": CONTEXT["chat_deployment"],
            }), CONTEXT)


if __name__ == "__main__":
    unittest.main()
