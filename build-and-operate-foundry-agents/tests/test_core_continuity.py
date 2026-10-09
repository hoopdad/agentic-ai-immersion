"""Accepted learner behavior and immutable core release evidence, without Azure calls."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "3-day-labs")]
from common import foundry_env


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = ROOT / f".core-continuity-{uuid.uuid4().hex}"
        self.workspace.mkdir()
        self.addCleanup(shutil.rmtree, self.workspace)

    def test_invocation_requires_exact_fixed_version_routing(self) -> None:
        with patch.object(foundry_env, "load_env", return_value={
                "MARKETPLACE_RESOURCE_SUFFIX": "offline", "AZURE_AI_MODEL_DEPLOYMENT_NAME": "chat-offline"}):
            basics = load("core_pinned_basics", ROOT / "shared/hosted-agent-basics/lab2_hosted_basics.py")
        project = MagicMock()
        project.__enter__.return_value = project
        fixed = SimpleNamespace(type="FixedRatio", agent_version="3", traffic_percentage=100)
        rules = [fixed]
        project.agents.get.return_value = SimpleNamespace(
            agent_endpoint=SimpleNamespace(version_selector=SimpleNamespace(version_selection_rules=rules)))
        with patch.object(foundry_env, "get_project_client", return_value=project):
            basics.require_pinned_version("core-concierge", "3")
            for changed in ([], [SimpleNamespace(type="Latest")],
                            [SimpleNamespace(type="FixedRatio", agent_version="4", traffic_percentage=100)],
                            [SimpleNamespace(type="FixedRatio", agent_version="3", traffic_percentage=50)],
                            [fixed, fixed]):
                rules[:] = changed
                with self.assertRaisesRegex(RuntimeError, "Pin 100%"):
                    basics.require_pinned_version("core-concierge", "3")

    def test_transfer_retains_learner_function_policy_and_survives_packaging(self) -> None:
        prepare = load("core_transfer_prepare", ROOT / "shared/hosted-knowledge-sessions/hosted/prepare.py")
        source = self.workspace / "basics.py"
        source.write_text('''ROLE_INSTRUCTIONS = """1. Use facts.
2. No retrieval yet.
3. Offer an advisor, name AEP and preserve this learner policy.
4. Be concise.
"""
@tool(approval_mode="never_require")
def get_sponsor(sponsor_id: Annotated[str, Field(description="Sponsor id")]) -> dict:
    result = marketplace_data.get_sponsor(sponsor_id)
    return {**result, "learner_note": "retained"}
TOOLS = [get_sponsor]
''', encoding="utf-8")
        package = self.workspace / "hosted"
        common = self.workspace / "original_common"
        common.mkdir()
        (common / "__init__.py").write_text("")
        with patch.object(prepare, "HERE", package), patch.object(prepare, "SOURCES", {"common": common}):
            prepare.vendor()
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            state = prepare.transfer_accepted_behavior(source, digest)
            product = package / "common/accepted_concierge.py"
            accepted = product.read_bytes()
            module = load("accepted_learner_behavior", product)
            facts = module.get_sponsor.func("SP-NORTHWIND")
            self.assertEqual(facts["learner_note"], "retained")
            self.assertIn("AEP", module.HANDOFF_POLICY)
            prepare.vendor()
            self.assertEqual(product.read_bytes(), accepted)
            source.write_text(source.read_text().replace("retained", "changed"))
            with self.assertRaisesRegex(RuntimeError, "Labs 3-4"):
                prepare.transfer_accepted_behavior(source, digest)
            self.assertEqual(product.read_bytes(), accepted)
            self.assertEqual(state["transfer_sha256"], hashlib.sha256(accepted).hexdigest())

    def test_release_rejects_changed_runtime_questions_scores_or_bundle(self) -> None:
        with patch.object(foundry_env, "load_env", return_value={
                "MARKETPLACE_RESOURCE_SUFFIX": "offline", "FOUNDRY_PROJECT_ENDPOINT": "https://offline.example.test",
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "chat-offline",
                "PROJECT_RESOURCE_ID": "/subscriptions/offline/resourceGroups/workshop/providers/Microsoft.CognitiveServices/accounts/workshop/projects/project",
                "EMBEDDING_MODEL_DEPLOYMENT_NAME": "embed-offline"}):
            operate = load("core_evidence_operate", ROOT / "shared/operate-hosted-agents/lab5_operate.py")
        product = self.workspace / "shared/hosted-knowledge-sessions/hosted"
        (product / "common").mkdir(parents=True)
        for name in ("main.py", "prepare.py", "requirements.txt", "common/accepted_concierge.py"):
            (product / name).write_text("# accepted product\n")
        questions = self.workspace / "questions.jsonl"
        questions.write_text('{"query":"accepted question"}\n')
        source = self.workspace / "operate.py"
        source.write_text("# accepted evaluator\n")
        hosted = {"agent_name": "core-concierge", "model": "chat-offline", "deployed": {"version": "3"}}
        knowledge = {"mcp_endpoint": "https://offline.example.test/mcp"}
        with patch.object(operate, "ROOT", self.workspace), patch.object(operate, "GOLDEN", questions), \
                patch.object(operate, "SOURCE_PATH", source):
            reference = operate.evaluated_target(hosted, knowledge)
            for path in (product / "main.py", questions):
                original = path.read_bytes()
                path.write_text("changed")
                with self.assertRaisesRegex(RuntimeError, "Lab 9 evaluation"):
                    operate.validate_evaluated_target(reference, hosted, knowledge)
                path.write_bytes(original)
            operate.validate_evaluated_target(reference, hosted, knowledge)
            folder = self.workspace / "release"
            folder.mkdir()
            bundle = folder / "evaluation_bundle.json"
            bundle.write_text(json.dumps({"info": {"evaluated_target": reference}}))
            results = folder / "eval_results.jsonl"
            results.write_text('{"scores":{"groundedness":4,"relevance":4}}\n')
            gate = folder / "gate_result.json"
            gate.write_text(json.dumps({
                "passed": True, "evaluated_at": "offline", "questions": 1, "failures": [],
                "thresholds": {"strict": True},
                "evaluation_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "evaluation_results_sha256": hashlib.sha256(results.read_bytes()).hexdigest(),
            }))
            promote = load("core_evidence_promote", ROOT / "shared/operate-hosted-agents/promote.py")
            with patch.object(promote, "ROOT", self.workspace), patch.object(promote, "GATE_PATH", gate):
                self.assertTrue(promote.check_gate()["passed"])
                for path in (product / "main.py", results, bundle):
                    original = path.read_bytes()
                    path.write_text("changed")
                    with self.assertRaises(ValueError):
                        promote.check_gate()
                    path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
