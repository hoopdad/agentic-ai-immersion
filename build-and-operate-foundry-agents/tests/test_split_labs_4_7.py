"""Execute each paired notebook in separate namespaces with offline cloud boundaries."""
from __future__ import annotations

from contextlib import ExitStack
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "labs"))
from common import foundry_env, notebook_parts
import lab_helpers


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


converter = load(ROOT / "tools/py_to_ipynb.py", "split_4_7_converter")
PARTS = {
    "lab4": ("hosted-multi-agent-handoff", "lab7_specialist_orchestration", "lab8_advisor_recovery", "lab4_hosted_multi_agent"),
    "lab5": ("operate-hosted-agents", "lab9_tracing_evaluation", "lab10_release_rollback", "lab5_operate"),
    "stretch6": ("prompt-agents-and-workflows", "lab11_prompt_agents", "lab12_workflows_delegation", "stretch6_prompt_agents"),
    "stretch7": ("invocations-toolbox-skills", "lab13_invocations", "lab14_skills_toolbox", "stretch7_invocations"),
}
ENV = {
    "PROJECT_RESOURCE_ID": "/subscriptions/offline/resourceGroups/workshop/providers/Microsoft.CognitiveServices/accounts/workshop/projects/project",
    "FOUNDRY_PROJECT_ENDPOINT": "https://offline.services.ai.azure.com/api/projects/project",
    "MARKETPLACE_RESOURCE_SUFFIX": "offline",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME": "chat-offline",
    "EMBEDDING_MODEL_DEPLOYMENT_NAME": "embed-offline",
}


def packet(lob: str, participant_id: str = "P-1003") -> dict:
    return {
        "case_id": "CASE-offline", "participant_id": participant_id, "lob": lob,
        "summary": "Neutral education for an advisor.", "participant_goals": ["Understand the facts"],
        "facts_gathered": [], "options_discussed": [], "open_questions": [],
        "recommended_next_step_for_advisor": "Review the participant's questions.",
        "compliance_flags": [], "created_at": "2026-10-01T00:00:00+00:00", "packet_attempts": 1,
    }


class SplitNotebookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory(prefix=".split-labs-", dir=ROOT)
        self.addCleanup(self.scratch.cleanup)
        self.workspace = Path(self.scratch.name)
        self.artifacts = self.workspace / "artifacts"
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, ENV))
        self.stack.enter_context(patch.object(foundry_env, "load_env", return_value=dict(ENV)))
        self.stack.enter_context(patch.object(lab_helpers, "artifact_path", side_effect=self.artifact))
        self.loaded = {}
        for lab, (folder, _, _, original) in PARTS.items():
            self.loaded[original] = load(ROOT / "shared" / folder / f"{original}.py", f"split_test_{original}")
            self.loaded[original].LABS_DIR = self.workspace
        self.gate = load(ROOT / "shared/operate-hosted-agents/eval_gate.py", "split_test_gate")
        self.promotion = load(ROOT / "shared/operate-hosted-agents/promote.py", "split_test_promotion")
        self.modules = {**self.loaded, "eval_gate": self.gate, "promote": self.promotion}
        self.stack.enter_context(patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="offline")))
        self.stack.enter_context(patch.object(
            lab_helpers, "load_lab_module", side_effect=lambda relative: self.modules[Path(relative).stem],
        ))

    def artifact(self, lab: str, *names: str) -> Path:
        folder = self.artifacts / lab
        folder.mkdir(parents=True, exist_ok=True)
        return folder.joinpath(*names)

    def cells(self, lab: str, part: str) -> list[str]:
        folder, a, b, _ = PARTS[lab]
        stem = a if part == "a" else b
        source = ROOT / "labs" / stem.split("_")[0] / f"{stem}.py"
        notebook = converter.build_notebook(source.read_text(encoding="utf-8"), seed=source.stem)
        return ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]

    def execute(self, lab: str, part: str, *, limit: int | None = None) -> dict:
        namespace = {"__name__": "__main__"}
        for code in self.cells(lab, part)[:limit]:
            code = code.replace('DEPLOYED_VERSION = ""', 'DEPLOYED_VERSION = "3"')
            code = code.replace('ACTIVE_VERSION = ""', 'ACTIVE_VERSION = "3"')
            code = code.replace('KNOWN_GOOD_VERSION = ""', 'KNOWN_GOOD_VERSION = "2"')
            code = code.replace('KNOWN_GOOD_REVISION = ""', 'KNOWN_GOOD_REVISION = "offline-reviewed-revision"')
            code = code.replace('RELEASE_TAG = ""', 'RELEASE_TAG = "healthcare-marketplace-concierge-test-offline"')
            exec(compile(code, f"{lab}{part}_cell", "exec"), namespace)
        return namespace

    def test_generated_notebooks_are_narrow_ordered_and_clean(self) -> None:
        for lab, (folder, a, b, _) in PARTS.items():
            for stem in (a, b):
                with self.subTest(stem=stem):
                    source = ROOT / "labs" / stem.split("_")[0] / f"{stem}.py"
                    expected = converter.build_notebook(source.read_text(encoding="utf-8"), seed=stem)
                    actual = json.loads(source.with_name(f"{stem.split('_')[0]}_walkthrough.ipynb").read_text())
                    self.assertEqual(actual, expected)
                    prefix = stem.split("_")[0].removeprefix("lab")
                    self.assertEqual(converter.validate_step_ids(actual, prefix), [])
                    self.assertEqual(converter.validate_cell_descriptions(actual), [])
                    self.assertNotIn("%run", source.read_text())
                    for cell in actual["cells"]:
                        if cell["cell_type"] == "code":
                            self.assertIsNone(cell["execution_count"])
                            self.assertEqual(cell["outputs"], [])
                    self.assertEqual(len(list(source.parent.glob("*.ipynb"))), 1)

    def test_b_requires_a_before_cloud_actions(self) -> None:
        with patch.object(foundry_env, "get_project_client") as project, \
                patch.object(foundry_env, "get_openai_client") as client:
            for lab in PARTS:
                self.artifact(lab, "part_b.json").write_text('{"old_success": true}')
                with self.subTest(lab=lab), self.assertRaises(RuntimeError):
                    self.execute(lab, "b", limit=1)
                self.assertFalse(self.artifact(lab, "part_b.json").exists())
            project.assert_not_called()
            client.assert_not_called()

    def test_each_b_rejects_changed_missing_and_differently_scoped_evidence(self) -> None:
        for lab in PARTS:
            path = self.artifact(lab, "part_a.json")
            evidence = self.artifact(lab, "outcome.json")
            for failure in ("changed", "missing", "scope"):
                evidence.write_text('{"observed": true}')
                notebook_parts.write_checkpoint(
                    path, lab=lab, part="a", context=notebook_parts.scope(ENV),
                    evidence=[evidence], state={},
                )
                if failure == "changed":
                    evidence.write_text('{"observed": false}')
                elif failure == "missing":
                    evidence.unlink()
                with self.subTest(lab=lab, failure=failure):
                    driver = self.loaded[PARTS[lab][3]]
                    changed_env = {**ENV, "MARKETPLACE_RESOURCE_SUFFIX": "other"} if failure == "scope" else ENV
                    with patch.object(driver, "ENV", changed_env), self.assertRaises(RuntimeError):
                        self.execute(lab, "b", limit=1)

    def test_author_sources_import_without_notebook_actions(self) -> None:
        with patch.object(foundry_env, "get_project_client") as project, \
                patch.object(foundry_env, "get_openai_client") as client, \
                patch.object(notebook_parts, "read_checkpoint") as checkpoint:
            for folder, a, b, _ in PARTS.values():
                for stem in (a, b):
                    load(ROOT / "labs" / stem.split("_")[0] / f"{stem}.py", f"import_only_{stem}")
            project.assert_not_called()
            client.assert_not_called()
            checkpoint.assert_not_called()

    def test_failed_a_action_cannot_publish_a_completion_checkpoint(self) -> None:
        for lab, (_, _, _, original) in PARTS.items():
            driver = self.loaded[original]
            action = "publish_prompt_agents" if lab == "stretch6" else "build"
            for part in ("a", "b"):
                self.artifact(lab, f"part_{part}.json").write_text('{"old_success": true}')
            with self.subTest(lab=lab), patch.object(driver, action, side_effect=RuntimeError("offline failure")):
                with self.assertRaises(RuntimeError):
                    self.execute(lab, "a")
                self.assertFalse(self.artifact(lab, "part_a.json").exists())
                self.assertFalse(self.artifact(lab, "part_b.json").exists())

    def test_individual_a_cell_rerun_invalidates_prior_a_and_b_success(self) -> None:
        outcomes = {
            "lab4": ("orchestration", "compliance", "classification"),
            "lab5": ("baseline", "tracing"),
            "stretch6": ("published_prompts", "function_turn", "portal"),
            "stretch7": ("batch_package", "offline_batch", "nightly_batch", "deployment"),
        }
        for lab, (_, _, _, original) in PARTS.items():
            namespace = self.execute(lab, "a", limit=1)
            namespace["accepted"] = dict.fromkeys(outcomes[lab], True)
            for part in ("a", "b"):
                self.artifact(lab, f"part_{part}.json").write_text('{"old_success": true}')
            driver = self.loaded[original]
            action = "publish_prompt_agents" if lab == "stretch6" else "build"
            with self.subTest(lab=lab), patch.object(driver, action, side_effect=RuntimeError("rerun failure")):
                with self.assertRaises(RuntimeError):
                    exec(compile(self.cells(lab, "a")[1], "rerun_a_action", "exec"), namespace)
                for part in ("a", "b"):
                    self.assertFalse(self.artifact(lab, f"part_{part}.json").exists())
                with self.assertRaises(AssertionError):
                    exec(compile(self.cells(lab, "a")[-1], "publish_after_failed_a_rerun", "exec"), namespace)
                self.assertFalse(self.artifact(lab, "part_a.json").exists())

    def test_lab4_fresh_kernel_resumes_original_sessions_without_reclassification(self) -> None:
        driver = self.loaded["lab4_hosted_multi_agent"]
        driver.LABS_DIR = self.workspace
        sent = []
        session_packets = {}
        sessions = self.artifact("lab4", "sessions")
        sessions.mkdir()
        process = MagicMock()
        process.start.return_value = process
        process.__enter__.return_value = process

        def post(_base, text, _previous=None):
            turn = json.loads(text)
            sent.append(turn)
            sid = turn["session_id"]
            if "message" in turn:
                lob = "accounts" if turn["scenario"] == "classifier-gate" else {
                    "S1": "marketplace", "S2": "accounts", "S3": "both", "compliance-gate": "marketplace",
                }[turn["scenario"]]
                result = packet(lob, turn["participant_id"])
                session_packets[sid] = result
                (sessions / f"{sid}.json").write_text(json.dumps({"notes": {"status": driver.PENDING, "packet": result}}))
                driver.SERVER_LOG.write_text("compliant=False\nsending marketplace-guide back for one revision")
                return {"status": driver.PENDING, "packet": result}, "response-offline"
            result = copy.deepcopy(session_packets[sid])
            if turn["advisor"].startswith("revise:"):
                result.update(packet_attempts=2, open_questions=["Confirm the IEP dates."])
                session_packets[sid] = result
                (sessions / f"{sid}.json").write_text(json.dumps({
                    "notes": {"status": driver.PENDING, "packet": result, "resume_path": "session_store"},
                }))
                return {"status": driver.PENDING, "packet": result, "resume_path": "session_store"}, "response-offline"
            result.update(advisor_decision="approve", status="approved")
            session_packets[sid] = result
            (sessions / f"{sid}.json").write_text(json.dumps({
                "notes": {"status": "approved", "packet": result, "resume_path": "session_store"},
            }))
            return {"status": "approved", "packet": result, "resume_path": "session_store"}, "response-offline"

        def build(**_kwargs):
            record = {"agent_name": "offline-triage"}
            foundry_env.save_artifact(driver.HOSTED_RECORD, record)
            return record

        self.stack.enter_context(patch.object(driver, "HostedProcess", return_value=process))
        self.stack.enter_context(patch.object(driver, "post_turn", side_effect=post))
        build_mock = self.stack.enter_context(patch.object(driver, "build", side_effect=build))
        self.stack.enter_context(patch.object(driver, "deploy_commands", return_value="true"))
        self.stack.enter_context(patch.object(driver, "record_deployment", return_value={"deployed": {"version": "3"}}))

        def deployed_demo(**kwargs):
            self.assertTrue(kwargs["deployed"])
            final = {**packet("accounts"), "advisor_decision": "approve", "status": "approved"}
            driver.save_packet("S2", final)
            return {"S2": final}
        self.stack.enter_context(patch.object(driver, "demo", side_effect=deployed_demo))
        a = self.execute("lab4", "a")
        self.assertTrue(all("advisor" not in turn for turn in sent))
        count = len(sent)
        tested = a["part_a"]["state"]["tested_sources"]
        for name in ("main.py", "marketplace_specialists.py", "marketplace_workflow.py"):
            self.assertIn(f"shared/hosted-multi-agent-handoff/hosted/{name}", tested)
        changed_sources = {**tested, "shared/hosted-multi-agent-handoff/hosted/marketplace_specialists.py": "classifier-removed"}
        with patch.object(driver, "source_fingerprints", return_value=changed_sources):
            with self.assertRaises(AssertionError):
                exec(compile(self.cells("lab4", "a")[-1], "reject_changed_a_publish_source", "exec"), a)
        self.assertFalse(self.artifact("lab4", "part_a.json").exists())
        exec(compile(self.cells("lab4", "a")[-1], "republish_restored_tested_source", "exec"), a)
        with patch.object(driver, "source_fingerprints", return_value=changed_sources):
            with self.assertRaises(AssertionError):
                self.execute("lab4", "b", limit=1)
        self.assertEqual(len(sent), count)
        live_session = sessions / f"{a['pending']['S2']['session_id']}.json"
        original_session = live_session.read_text()
        live_session.unlink()
        with self.assertRaises(FileNotFoundError):
            self.execute("lab4", "b", limit=1)
        changed = json.loads(original_session)
        changed["notes"]["status"] = "approved"
        live_session.write_text(json.dumps(changed))
        with self.assertRaises(AssertionError):
            self.execute("lab4", "b", limit=1)
        self.assertEqual(len(sent), count)
        live_session.write_text(original_session)
        b = self.execute("lab4", "b")
        self.assertIsNot(a, b)
        self.assertTrue(all("message" not in turn for turn in sent[count:]))
        self.assertEqual(build_mock.call_count, 2)
        self.assertEqual({turn["session_id"] for turn in sent[count:]}, {case["session_id"] for case in a["pending"].values()})
        self.assertTrue(self.artifact("lab4", "part_b.json").is_file())
        after_first_b = len(sent)
        replay = self.execute("lab4", "b")
        self.assertEqual(len(sent), after_first_b)
        self.assertEqual(build_mock.call_count, 2)
        deployment_calls = driver.deploy_commands.call_count
        with patch.object(driver, "source_fingerprints", return_value=changed_sources):
            with self.assertRaises(AssertionError):
                exec(compile(self.cells("lab4", "b")[3], "reject_changed_predeploy_source", "exec"), replay)
        self.assertEqual(driver.deploy_commands.call_count, deployment_calls)
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("lab4", "b")[-1], "publish_after_failed_source_check", "exec"), replay)
        self.assertFalse(self.artifact("lab4", "part_b.json").exists())
        with patch.object(driver, "HostedProcess", side_effect=RuntimeError("revision rerun failure")):
            with self.assertRaises(RuntimeError):
                exec(compile(self.cells("lab4", "b")[1], "failed_revision_rerun", "exec"), replay)
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("lab4", "b")[-1], "publish_after_failed_revision", "exec"), replay)
        self.assertFalse(self.artifact("lab4", "part_b.json").exists())

    def test_lab5_b_reads_exact_scores_without_repeating_evaluation(self) -> None:
        driver = self.loaded["lab5_operate"]
        rows = [{
            "query": f"Question {n}", "response": "A licensed advisor can compare available plans.",
            "context": "marketplace", "citations": ["KB-MKT-001"], "trace_id": f"trace-{n}",
            "scores": {"groundedness": 4.0, "relevance": 4.0, "no_recommendation_result": "pass",
                       "pii_leak_result": "pass", "must_not_result": "pass", "must_include_coverage": 1.0},
        } for n in range(6)]

        def build(**kwargs):
            tracing = {"enabled": kwargs.get("enable_tracing", True), "source": "offline"}
            info = {"target": {"agent_name": "offline-concierge", "mode": "local"}, "tracing": tracing}
            foundry_env.save_artifact(self.artifact("lab5", "operate.json"), info)
            return {"info": info, "hosted": {"agent_name": "offline-concierge"},
                    "knowledge": {}, "tracing": tracing, "judges": {}, "custom": {}}

        def demo(bundle, limit, target_mode):
            selected = rows[:limit]
            summary = driver.summarize(selected)
            if bundle["tracing"]["enabled"]:
                summary["trace_ids"] = [row["trace_id"] for row in selected]
            driver.write_report(selected, summary, bundle)
            return summary

        build_mock = self.stack.enter_context(patch.object(driver, "build", side_effect=build))
        demo_mock = self.stack.enter_context(patch.object(driver, "demo", side_effect=demo))
        for module, key, value in (
            (self.gate, "RESULTS_PATH", self.artifact("lab5", "eval_results.jsonl")),
            (self.gate, "GATE_PATH", self.artifact("lab5", "gate_result.json")),
            (self.gate, "LABS_DIR", self.workspace),
            (self.promotion, "GATE_PATH", self.artifact("lab5", "gate_result.json")),
            (self.promotion, "PROMOTIONS_PATH", self.artifact("lab5", "promotions.jsonl")),
        ):
            self.stack.enter_context(patch.object(module, key, value))
        a = self.execute("lab5", "a")
        original = self.gate.RESULTS_PATH.read_bytes()
        counts = (build_mock.call_count, demo_mock.call_count)
        self.execute("lab5", "b")
        self.assertEqual(counts, (build_mock.call_count, demo_mock.call_count))
        self.assertEqual(self.gate.RESULTS_PATH.read_bytes(), original)
        rehearsal = self.execute("lab5", "b", limit=4)
        self.artifact("lab5", "part_b.json").write_text('{"old_success": true}')
        existing_promotions = self.promotion.PROMOTIONS_PATH.read_bytes()
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("lab5", "b")[4], "unset_release_tag", "exec"), rehearsal)
        self.assertFalse(self.artifact("lab5", "part_b.json").exists())
        self.assertEqual(self.promotion.PROMOTIONS_PATH.read_bytes(), existing_promotions)
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("lab5", "b")[-1], "publish_after_failed_rehearsal", "exec"), rehearsal)
        self.assertFalse(self.artifact("lab5", "part_b.json").exists())
        self.execute("lab5", "b")
        self.assertTrue(json.loads(self.gate.GATE_PATH.read_text())["passed"])
        self.assertFalse(json.loads(self.artifact("lab5", "regression_gate.json").read_text())["passed"])
        self.assertTrue(self.artifact("lab5", "part_b.json").is_file())
        self.execute("lab5", "b")
        self.assertEqual(counts, (build_mock.call_count, demo_mock.call_count))
        self.assertEqual(self.gate.RESULTS_PATH.read_bytes(), original)
        with patch.object(driver, "demo", side_effect=RuntimeError("current trace failed")):
            with self.assertRaises(RuntimeError):
                exec(compile(self.cells("lab5", "a")[2], "failed_trace_rerun", "exec"), a)
        self.assertFalse(a["trace_passed"])
        self.assertFalse(self.artifact("lab5", "trace_evidence.json").exists())
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("lab5", "a")[-1], "publish_after_failed_trace", "exec"), a)
        self.assertFalse(self.artifact("lab5", "part_a.json").exists())
        self.assertFalse(self.artifact("lab5", "part_b.json").exists())

    def test_stretch6_publishes_prompts_in_a_and_only_workflow_in_b(self) -> None:
        driver = self.loaded["stretch6_prompt_agents"]
        project = MagicMock()
        creations = []

        def create_version(agent_name, definition):
            creations.append((agent_name, type(definition).__name__))
            return SimpleNamespace(name=agent_name, version="1", id=f"id-{agent_name}")

        project.agents.create_version.side_effect = create_version
        self.stack.enter_context(patch.object(foundry_env, "get_project_client", return_value=project))
        self.stack.enter_context(patch.object(foundry_env, "get_openai_client", return_value=MagicMock()))
        self.stack.enter_context(patch.object(lab_helpers, "require_artifact", return_value={
            "mcp_endpoint": "https://offline.test/mcp", "connection": {"connection_id": "offline-connection"},
        }))
        self.stack.enter_context(patch.object(driver, "run_concierge_turn", return_value=(
            "Hello Evelyn, a licensed advisor can compare available plans.", [{"name": "get_participant"}],
        )))
        self.execute("stretch6", "a")
        self.assertTrue(all(kind == "PromptAgentDefinition" for _, kind in creations))
        before = len(creations)
        def baseline(info):
            foundry_env.save_artifact(self.artifact("stretch6", "handoff_packets", "S1.json"), {"observed": True})
            return info
        self.stack.enter_context(patch.object(driver, "demo", side_effect=baseline))
        wrong_packet = packet("accounts")
        wrong_packet.pop("packet_attempts")
        wrong_packet["open_questions"] = ["Confirm the marketplace question."]
        self.stack.enter_context(patch.object(driver, "run_case", return_value={
            "errors": [], "actions": [{"action_id": action} for action in ("triage", "accounts", "compliance", "handoff")],
            "messages": [json.dumps(wrong_packet)],
        }))
        hosted_tool = load(ROOT / "shared" / PARTS["stretch6"][0] / "hosted_tool_snippet.py", "hosted_tool_snippet")
        self.stack.enter_context(patch.object(hosted_tool, "load_workflow_reference", return_value={"workflow_name": driver.WORKFLOW}))
        delegation_packet = packet("marketplace", "P-1005")
        delegation_packet.pop("packet_attempts")
        delegation_packet["case_id"] = "hosted-gate-P-1005"
        self.stack.enter_context(patch.object(hosted_tool, "run_triage_workflow", return_value={
            "status": "completed", "packet": delegation_packet,
        }))
        import deployment
        self.stack.enter_context(patch.object(deployment, "bash_deploy_block", return_value="true"))
        main_path = ROOT / "shared/hosted-knowledge-sessions/hosted/main.py"
        read_text = Path.read_text
        self.stack.enter_context(patch.object(
            Path, "read_text",
            lambda path, *args, **kwargs: "def run_triage_workflow(): pass\nFUNCTION_TOOLS = [run_triage_workflow]"
            if path == main_path else read_text(path, *args, **kwargs),
        ))
        self.modules["lab3_hosted_knowledge"] = SimpleNamespace(
            HOSTED_DIR=main_path.parent, AGENT_NAME="offline-concierge",
        )
        self.modules["prepare"] = SimpleNamespace(vendor=lambda: {})
        b = self.execute("stretch6", "b")
        self.assertEqual(creations[before:], [(driver.WORKFLOW, "WorkflowAgentDefinition")])
        self.assertEqual(b["info"]["agents"], b["prompt_info"]["agents"])
        self.assertTrue(self.artifact("stretch6", "part_b.json").is_file())
        with patch.object(hosted_tool, "run_triage_workflow", return_value={"status": "failed"}):
            with self.assertRaises(AssertionError):
                exec(compile(self.cells("stretch6", "b")[3], "failed_delegation_rerun", "exec"), b)
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("stretch6", "b")[-1], "publish_after_failed_delegation", "exec"), b)
        self.assertFalse(self.artifact("stretch6", "part_b.json").exists())

    def test_stretch7_preserves_batch_record_and_skills_config_is_safe(self) -> None:
        driver = self.loaded["stretch7_invocations"]
        # The real build selectively vendors only the current part and merges cumulative records.
        vendors = []
        prepare = SimpleNamespace(vendor=lambda: {"offline": 1})

        def module_for(relative):
            if relative.endswith("prepare.py"):
                vendors.append(relative)
                return prepare
            return self.modules[Path(relative).stem]
        self.stack.enter_context(patch.object(lab_helpers, "load_lab_module", side_effect=module_for))
        with patch.object(driver, "call_invocations", return_value=([], "/invocations")):
            driver.build(protocols=("invocations",))
        self.assertNotIn("responses_skills", json.loads(driver.RECORD.read_text())["agents"])
        self.assertEqual(len(vendors), 1)
        self.assertIn("hosted-invocations", vendors[0])
        original = json.loads(driver.RECORD.read_text())["agents"]["invocations"]
        driver.build(protocols=("responses_skills",))
        combined = json.loads(driver.RECORD.read_text())
        self.assertEqual(combined["agents"]["invocations"], original)
        self.assertIn("hosted-responses-skills", vendors[-1])
        module = load(ROOT / "labs/lab14/lab14_skills_toolbox.py", "split_config")
        self.assertEqual(module.validate_config("", "", "")["SKILL_NAMES"], "")
        for name, url in (("box", ""), ("", "https://example.test/mcp"),
                          ("box", "http://example.test/mcp"), ("box", "https://attendee@example.test/mcp"),
                          ("box", "https://example.test/mcp?key=value"), ("box", "https://example.test/mcp#fragment")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                module.validate_config(name, url, "")
        with self.assertRaises(ValueError):
            module.validate_config("", "", "not-a-local-skill")

    def test_stretch7_each_half_executes_only_its_hosted_protocol(self) -> None:
        driver = self.loaded["stretch7_invocations"]
        batches = []
        builds = []
        state = {"agents": {}, "sample_run": None}
        skills = self.workspace / "skills"
        (skills / "debit-card-faq").mkdir(parents=True)
        (skills / "debit-card-faq" / "SKILL.md").write_text("offline governed skill source")
        self.stack.enter_context(patch.object(driver, "SKILLS_SRC", skills))

        def build(*, protocols, **_kwargs):
            builds.extend(protocols)
            for protocol in protocols:
                state["agents"][protocol] = {"agent_name": f"offline-{protocol}"}
            foundry_env.save_artifact(driver.RECORD, state)
            return copy.deepcopy(state)

        def nightly(*, offline):
            batches.append(offline)
            sample = {"claim_ids": driver.nightly_denial_ids(), "reviews": len(driver.nightly_denial_ids())}
            for claim in sample["claim_ids"]:
                foundry_env.save_artifact(driver.REVIEWS_DIR / f"{claim}.json", {"claim_id": claim})
            state["sample_run"] = sample
            foundry_env.save_artifact(driver.RECORD, state)
            return sample

        def first_skill():
            foundry_env.save_artifact(driver.ARTIFACTS / "skills_transcript.md", "Governed [KB-ACC-001] answer.")
            (driver.ARTIFACTS / "hosted-responses-skills_local.log").write_text("read_skill name=hra-claims")
            return "A licensed advisor can review the [KB-ACC-001] documents."

        def second_skill(*, protocols):
            self.assertEqual(protocols, ("responses_skills",))
            build(protocols=protocols)
            return "Review the card procedures in [KB-ACC-002]."

        self.stack.enter_context(patch.object(driver, "build", side_effect=build))
        self.stack.enter_context(patch.object(driver, "nightly_denials_acceptance_gate", side_effect=nightly))
        self.stack.enter_context(patch.object(driver, "skills_demo", side_effect=first_skill))
        self.stack.enter_context(patch.object(driver, "second_skill_acceptance_gate", side_effect=second_skill))
        self.stack.enter_context(patch.object(driver, "validate_second_skill_source", return_value=skills / "debit-card-faq" / "SKILL.md"))
        import deployment
        commands = []
        def deploy(folder, name, protocol, env, **_kwargs):
            commands.append(protocol)
            return "true"
        self.stack.enter_context(patch.object(deployment, "bash_deploy_block", side_effect=deploy))
        self.execute("stretch7", "a")
        self.assertEqual(builds, ["invocations"])
        self.assertEqual(batches, [True, False])
        self.assertEqual(commands, ["invocations"])
        b = self.execute("stretch7", "b")
        self.assertEqual(builds, ["invocations", "responses_skills", "responses_skills"])
        self.assertEqual(batches, [True, False])
        self.assertEqual(commands, ["invocations", "responses"])
        self.assertTrue(self.artifact("stretch7", "part_b.json").is_file())
        self.execute("stretch7", "b")
        self.assertEqual(batches, [True, False])
        self.assertEqual(commands, ["invocations", "responses", "responses"])
        with patch.object(driver, "second_skill_acceptance_gate", side_effect=RuntimeError("skill rerun failure")):
            with self.assertRaises(RuntimeError):
                exec(compile(self.cells("stretch7", "b")[3], "failed_skill_rerun", "exec"), b)
        with self.assertRaises(AssertionError):
            exec(compile(self.cells("stretch7", "b")[-1], "publish_after_failed_skill", "exec"), b)
        self.assertFalse(self.artifact("stretch7", "part_b.json").exists())


if __name__ == "__main__":
    unittest.main()
