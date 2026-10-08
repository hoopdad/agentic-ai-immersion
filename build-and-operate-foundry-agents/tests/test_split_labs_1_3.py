"""Offline fresh-kernel execution and handoff regressions for the first six notebooks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
LAB1 = ROOT / "labs/foundry-project-models"
sys.path[:0] = [str(ROOT), str(ROOT / "labs"), str(ROOT / "tools"), str(LAB1)]
from common import foundry_env, notebook_parts
import lab_helpers
import project_setup as setup
from py_to_ipynb import build_notebook, validate_cell_descriptions, validate_notebook, validate_step_ids

SUB = "11111111-1111-1111-1111-111111111111"
TENANT = "22222222-2222-2222-2222-222222222222"
ACCOUNT_ID = f"/subscriptions/{SUB}/resourceGroups/approved/providers/Microsoft.CognitiveServices/accounts/foundry"
PROJECT_ID = ACCOUNT_ID + "/projects/healthcare-marketplace-jd-4821"
ENDPOINT = "https://approved.services.ai.azure.com/api/projects/healthcare-marketplace-jd-4821"
CONTEXT = {"subscription_id": SUB, "tenant_id": TENANT, "subscription_name": "approved"}
ACCOUNT = {
    "id": ACCOUNT_ID, "location": "eastus", "kind": "AIServices",
    "properties": {"provisioningState": "Succeeded", "allowProjectManagement": True,
                   "endpoints": {"OpenAI": "https://approved.openai.azure.com/"}},
}
PROJECT = {
    "id": PROJECT_ID, "tags": {"marketplace-resource-suffix": "jd-4821"},
    "properties": {"provisioningState": "Succeeded", "endpoints": {"Foundry": ENDPOINT}},
}
ENV = {
    "PROJECT_RESOURCE_ID": PROJECT_ID, "FOUNDRY_PROJECT_ENDPOINT": ENDPOINT,
    "TENANT_ID": TENANT, "MARKETPLACE_RESOURCE_SUFFIX": "jd-4821",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME": "marketplace-chat-jd-4821",
    "EMBEDDING_MODEL_DEPLOYMENT_NAME": "marketplace-embedding-jd-4821",
    "AZURE_AI_SEARCH_ENDPOINT": "https://approved.search.windows.net",
}
PAIRS = (
    ("foundry-project-models", "lab1_identity_project", "lab1a"),
    ("foundry-project-models", "lab2_models_verify", "lab1b"),
    ("hosted-agent-basics", "lab3_tools_local", "lab2a"),
    ("hosted-agent-basics", "lab4_deploy_invoke", "lab2b"),
    ("hosted-knowledge-sessions", "lab5_knowledge_retrieval", "lab3a"),
    ("hosted-knowledge-sessions", "lab6_sessions_resiliency", "lab3b"),
)


def cells(stem: str) -> list[str]:
    folder, source, _ = next(row for row in PAIRS if row[2] == stem)
    notebook_name = source.split("_")[0]
    nb = json.loads((ROOT / "labs" / folder / f"{notebook_name}_walkthrough.ipynb").read_text())
    return ["".join(cell["source"]) for cell in nb["cells"] if cell["cell_type"] == "code"]


def execute(source: str, namespace: dict, *, artifacts: Path | None = None) -> None:
    if artifacts is not None:
        for lab in ("lab1", "lab2", "lab3"):
            source = source.replace(
                f'ARTIFACTS = WORKSHOP / "labs/artifacts/{lab}"',
                f"ARTIFACTS = Path({str(artifacts / lab)!r})")
    exec(compile(source, "<fresh-kernel-cell>", "exec"), namespace)


class SplitNotebookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = LAB1 / f".split-tests-{uuid.uuid4().hex}"
        self.artifacts = self.scratch / "labs/artifacts"
        self.artifacts.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.scratch)

    def test_generated_described_steps_reset_in_each_half(self) -> None:
        for folder, source, stem in PAIRS:
            with self.subTest(notebook=stem):
                text = (ROOT / "labs" / folder / f"{source}.py").read_text()
                number = source.split("_")[0].removeprefix("lab")
                nb = json.loads((ROOT / "labs" / folder / f"lab{number}_walkthrough.ipynb").read_text())
                self.assertEqual(nb, build_notebook(text, seed=source))
                self.assertEqual(validate_notebook(nb), [])
                self.assertEqual(validate_step_ids(nb, number), [])
                self.assertEqual(validate_cell_descriptions(nb), [])
                self.assertTrue("".join(nb["cells"][0]["source"]).startswith(
                    f"# Lab {number}:"))
                self.assertNotIn("%run", text)
                self.assertNotIn("pickle", text)
                for cell in nb["cells"]:
                    if cell["cell_type"] == "code":
                        self.assertIsNone(cell["execution_count"])
                        self.assertEqual(cell["outputs"], [])

    def lab1_handoff(self) -> dict:
        state = {
            "schema_version": 1, "part": "a", **CONTEXT,
            "resource_group": "approved", "account_name": "foundry",
            "account_resource_id": ACCOUNT_ID, "project_resource_id": PROJECT_ID,
            "resource_suffix": "jd-4821", "project_endpoint": ENDPOINT,
            "azure_openai_endpoint": "https://approved.openai.azure.com/",
        }
        return {
            "schema_version": 1, "lab": "lab1", "part": "a",
            "context": {"subscription_id": SUB, "tenant_id": TENANT,
                        "account_resource_id": ACCOUNT_ID.lower(), "project_resource_id": PROJECT_ID.lower(),
                        "resource_suffix": "jd-4821"},
            "state": state, "evidence": [],
        }

    def test_lab1_fresh_a_to_b_no_project_recreation_and_stale_smoke(self) -> None:
        a, b = cells("lab1a"), cells("lab1b")
        ns_a: dict = {}
        ns_b: dict = {}
        artifacts = self.artifacts / "lab1"
        artifacts.mkdir()
        for name in ("part_a.json", "part_b.json", "project.json"):
            (artifacts / name).write_text("{}")
        models = [
            {"format": "OpenAI", "name": "gpt-5.4-mini", "version": "live",
             "skus": [{"name": "GlobalStandard"}]},
            {"format": "OpenAI", "name": "text-embedding-3-large", "version": "live",
             "skus": [{"name": "Standard"}]},
        ]
        evidence = {"chat": "passed", "embedding": "passed", "embedding_dimensions": 3072}
        with (
            patch.object(setup, "azure_context", return_value=CONTEXT),
            patch.object(setup, "account_inventory", return_value=[]),
            patch.object(setup, "verify_account", return_value=ACCOUNT),
            patch.object(setup, "ensure_project", return_value=PROJECT) as create_project,
            patch.object(setup.AzureCLI, "rest", return_value=PROJECT) as read_project,
            patch.object(setup.AzureCLI, "items", return_value=models),
            patch.object(setup, "ensure_deployment", side_effect=lambda cli, account, name, spec: {"name": name}) as deploy,
            patch.object(setup, "smoke_test", return_value=evidence),
            patch.object(setup, "write_env") as write_env,
            patch.object(foundry_env, "load_env", side_effect=lambda: ns_b["OUTPUT_ENV"]),
            patch("builtins.print"),
        ):
            execute(a[0], ns_a, artifacts=self.artifacts)
            self.assertFalse(any((artifacts / name).exists()
                                 for name in ("part_a.json", "part_b.json", "project.json")))
            ns_a["ARTIFACTS"] = artifacts
            execute(a[1], ns_a)
            ns_a.update(SUBSCRIPTION_ID=SUB, TENANT_ID=TENANT, RESOURCE_GROUP="approved",
                        FOUNDRY_ACCOUNT_NAME="foundry", ATTENDEE_SUFFIX="jd-4821", APPROVE_PROJECT=True)
            for source in a[2:]:
                execute(source, ns_a)
            create_project.assert_called_once()
            deploy.assert_not_called()
            self.assertFalse((artifacts / "project.json").exists())
            handoff = json.loads((artifacts / "part_a.json").read_text())["state"]
            self.assertFalse(set(handoff) & {"access_token", "env", "chat_deployment"})

            for name in ("part_b.json", "project.json"):
                (artifacts / name).write_text("{}")
            execute(b[0], ns_b, artifacts=self.artifacts)
            self.assertTrue((artifacts / "part_a.json").exists())
            self.assertFalse((artifacts / "part_b.json").exists())
            self.assertFalse((artifacts / "project.json").exists())
            ns_b.update(ARTIFACTS=artifacts, ARTIFACT=artifacts / "project.json")
            create_project.assert_called_once()  # B initialization is definitions only.
            execute(b[1], ns_b)
            ns_b.update(SUBSCRIPTION_ID=SUB, TENANT_ID=TENANT, ATTENDEE_SUFFIX="jd-4821")
            execute(b[2], ns_b)
            execute(b[3], ns_b)
            ns_b["APPROVE_PROVISIONING"] = True
            for source in b[4:]:
                execute(source, ns_b)
            create_project.assert_called_once()
            self.assertEqual(deploy.call_count, 2)
            self.assertTrue(all(call.args[0] == "get" for call in read_project.call_args_list))
            checkpoint = json.loads((artifacts / "project.json").read_text())
            self.assertEqual(checkpoint["smoke_tests"], evidence)
            self.assertEqual(checkpoint["project_resource_id"], PROJECT_ID)
            self.assertEqual(checkpoint["chat_deployment"]["name"], ENV["AZURE_AI_MODEL_DEPLOYMENT_NAME"])
            self.assertEqual(set(write_env.call_args.args[1]), setup.PROJECT_ENV_KEYS | {"MARKETPLACE_TODAY"})

            write_env.reset_mock()
            with patch.object(setup, "smoke_test", side_effect=RuntimeError("offline smoke failure")):
                with self.assertRaisesRegex(RuntimeError, "offline smoke failure"):
                    execute(b[5], ns_b)
            self.assertEqual(ns_b["SMOKE_TESTS"], {})
            self.assertIsNone(ns_b["SMOKE_TARGET"])
            self.assertFalse((artifacts / "project.json").exists())
            self.assertFalse((artifacts / "part_b.json").exists())
            with self.assertRaisesRegex(RuntimeError, "exact project"):
                execute(b[6], ns_b)
            write_env.assert_not_called()

            execute(b[5], ns_b)
            ns_b["CHAT_SPEC"]["properties"]["model"]["version"] = "changed"
            with self.assertRaisesRegex(RuntimeError, "exact project"):
                execute(b[6], ns_b)
            write_env.assert_not_called()
            create_project.assert_called_once()

    def test_lab1_handoff_missing_scope_tampering_and_ownership(self) -> None:
        path = self.artifacts / "lab1/part_a.json"
        cli = MagicMock()
        with self.assertRaisesRegex(RuntimeError, "Lab 1"):
            setup.read_project_handoff(path, cli, SUB, TENANT, "jd-4821")
        path.parent.mkdir()
        for invalid in ("not json", "[]"):
            path.write_text(invalid)
            with self.assertRaises(RuntimeError):
                setup.read_project_handoff(path, cli, SUB, TENANT, "jd-4821")
        with patch.object(setup, "azure_context", return_value=CONTEXT), \
                patch.object(setup, "verify_account", return_value=ACCOUNT):
            for change in (
                {"tenant_id": SUB}, {"resource_suffix": "other"},
                {"project_resource_id": PROJECT_ID + "-other"},
                {"account_resource_id": ACCOUNT_ID + "-other"},
                {"project_endpoint": ENDPOINT + "-other"},
            ):
                with self.subTest(change=change):
                    handoff = self.lab1_handoff()
                    handoff["state"].update(change)
                    path.write_text(json.dumps(handoff))
                    cli.rest.return_value = PROJECT
                    with self.assertRaises(RuntimeError):
                        setup.read_project_handoff(path, cli, SUB, TENANT, "jd-4821")
            path.write_text(json.dumps(self.lab1_handoff()))
            cli.rest.return_value = {**PROJECT, "tags": {"marketplace-resource-suffix": "other"}}
            with self.assertRaisesRegex(RuntimeError, "owned"):
                setup.read_project_handoff(path, cli, SUB, TENANT, "jd-4821")
            self.assertTrue(all(call.args[0] == "get" for call in cli.rest.call_args_list))

    def fake_driver(self, lab: str) -> SimpleNamespace:
        artifacts = self.artifacts / lab
        artifacts.mkdir(exist_ok=True)
        hosted_dir = self.scratch / lab / "hosted"
        (hosted_dir / "common").mkdir(parents=True)
        (hosted_dir / "main.py").write_text("# tested hosted source\n")
        hosted_record = artifacts / "hosted.json"
        transcripts = artifacts / "transcripts.md"
        knowledge = {"mcp_endpoint": "https://approved.search.windows.net/knowledgebases/kb/mcp",
                     "search_endpoint": ENV["AZURE_AI_SEARCH_ENDPOINT"]}
        name = "healthcare-marketplace-concierge-hosted-jd-4821"
        hosted = {
            "agent_name": name, "model": ENV["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            "project_endpoint": ENDPOINT, "env_for_container": {"MARKETPLACE_KB_MCP_URL": knowledge["mcp_endpoint"]},
            "session_behavior": {"local": "files", "deployed": "files, no scale proof"},
        }

        def build() -> dict:
            hosted_record.write_text(json.dumps(hosted))
            if lab == "lab3":
                (artifacts / "knowledge.json").write_text(json.dumps(knowledge))
            return hosted

        def demo(*args, **kwargs) -> dict:
            transcripts.write_text("redacted transcript\n")
            return {"continuity_ok": True, "pids": [101, 102]}

        def record_deployment(version: str) -> dict:
            hosted["deployed"] = {"version": version, "status": "active"}
            hosted_record.write_text(json.dumps(hosted))
            return hosted

        driver = SimpleNamespace(
            ARTIFACTS=artifacts, HOSTED_DIR=hosted_dir, HOSTED_RECORD=hosted_record,
            TRANSCRIPTS=transcripts, TRANSCRIPT_PATH=transcripts,
            AGENT_NAME=name, LOCAL_BASE="http://localhost:8088", DEFAULT_PORT=8088,
            build=MagicMock(side_effect=build), demo=MagicMock(side_effect=demo),
            record_deployment=MagicMock(side_effect=record_deployment),
            deploy_commands=MagicMock(return_value="echo reviewed deployment"),
            call_deployed=MagicMock(return_value={"text": "AEP [KB-ACC-001]"}),
            HostedProcess=MagicMock(),
            post_responses=MagicMock(return_value={"text": "Northwind $3,600"}),
            run_scenario=MagicMock(return_value=[{"agent": "facts"}, {"agent": "AEP advisor"}]),
            SCENARIOS={"S1": {}},
            write_transcripts=MagicMock(side_effect=lambda *args: transcripts.write_text("redacted AEP\n")),
            ask=MagicMock(side_effect=[("[KB-ACC-001] premium rule", {}), ("Rule text is not at hand", {})]),
            knowledge_base=SimpleNamespace(build_index=lambda: None, build_knowledge_base=lambda: None),
            broken_store_acceptance_gate=MagicMock(), scale_out_acceptance_gate=MagicMock(),
        )
        driver.HostedProcess.return_value.start.return_value = driver.HostedProcess.return_value
        return driver

    def artifact(self, lab: str, name: str, **kwargs) -> dict:
        return json.loads((self.artifacts / lab / name).read_text())

    def test_labs2_and3_fresh_a_to_b_reuse_resources(self) -> None:
        driver2 = self.fake_driver("lab2")
        driver3 = self.fake_driver("lab3")
        project_dir = self.artifacts / "lab1"
        project_dir.mkdir()
        (project_dir / "project.json").write_text(json.dumps({
            "provisioning_state": "Succeeded", "smoke_tests": {"chat": "passed", "embedding": "passed"},
            "project_resource_id": PROJECT_ID, "project_endpoint": ENDPOINT, "tenant_id": TENANT,
            "resource_suffix": "jd-4821", "chat_deployment": {"name": ENV["AZURE_AI_MODEL_DEPLOYMENT_NAME"]},
            "embedding_deployment": {"name": ENV["EMBEDDING_MODEL_DEPLOYMENT_NAME"]},
        }))
        with (
            patch.object(foundry_env, "load_env", return_value=ENV),
            patch.object(lab_helpers, "load_lab_module", side_effect=lambda path: driver2 if "hosted-agent-basics" in path else driver3),
            patch.object(lab_helpers, "require_artifact", side_effect=self.artifact),
            patch.object(lab_helpers, "artifact_path", side_effect=lambda lab: self.artifacts / lab),
            patch("inspect.getsource", return_value="# inspected real implementation"),
            patch("subprocess.run") as deploy,
            patch("builtins.print"),
        ):
            kernels = {}
            for lab, driver in (("lab2", driver2), ("lab3", driver3)):
                with self.subTest(lab=lab):
                    ns_a: dict = {}
                    for name in ("part_a.json", "part_b.json"):
                        (driver.ARTIFACTS / name).write_text("{}")
                    for index, source in enumerate(cells(lab + "a")):
                        execute(source, ns_a, artifacts=self.artifacts)
                        if index == 0:
                            self.assertFalse((driver.ARTIFACTS / "part_a.json").exists())
                            self.assertFalse((driver.ARTIFACTS / "part_b.json").exists())
                    builds = driver.build.call_count
                    demos = driver.demo.call_count
                    driver.build.reset_mock()
                    driver.demo.reset_mock()
                    driver.HostedProcess.reset_mock()
                    deploy.reset_mock()
                    ns_b: dict = {}
                    b = cells(lab + "b")
                    (driver.ARTIFACTS / "part_b.json").write_text("{}")
                    for source in b[:3]:
                        execute(source, ns_b, artifacts=self.artifacts)
                    self.assertFalse((driver.ARTIFACTS / "part_b.json").exists())
                    driver.build.assert_not_called()
                    driver.demo.assert_not_called()
                    driver.HostedProcess.assert_not_called()
                    deploy.assert_not_called()
                    self.assertGreater(builds, 0)
                    if lab == "lab2":
                        self.assertGreater(demos, 0)
                        execute(b[3], ns_b)
                        execute(b[4].replace('DEPLOYED_VERSION = ""', 'DEPLOYED_VERSION = "7"'), ns_b)
                        execute(b[5], ns_b)
                    else:
                        self.assertEqual(demos, 0)  # A does knowledge, not continuity.
                        for source in b[3:7]:
                            execute(source, ns_b)
                        execute(b[7].replace('DEPLOYED_VERSION = ""', 'DEPLOYED_VERSION = "8"'), ns_b)
                        execute(b[8], ns_b)
                        driver.demo.assert_called_once()
                        self.assertTrue(driver.demo.call_args.kwargs["restart"])
                        driver.broken_store_acceptance_gate.assert_called_once()
                        driver.scale_out_acceptance_gate.assert_not_called()
                    driver.build.assert_not_called()  # B never rebuilds project/Search.
                    self.assertEqual(deploy.call_count, 2)
                    marker = notebook_parts.read_checkpoint(
                        self.artifacts / lab / "part_b.json", lab=lab, part="b", context=notebook_parts.scope(ENV))
                    self.assertEqual(marker["part"], "b")
                    if lab == "lab3":
                        self.assertIn("not proven", marker["state"]["shared_scale"])
                    # B updates hosted.json but cannot make A's immutable evidence stale.
                    notebook_parts.read_checkpoint(
                        self.artifacts / lab / "part_a.json", lab=lab, part="a", context=notebook_parts.scope(ENV))
                    kernels[lab] = (ns_a, ns_b)
            # A failed rerun removes old success before the operation, and publishing
            # cannot recycle successful variables from an earlier invocation.
            for lab, driver, fail_cell, publish_cell in (
                ("lab2", driver2, 4, 5), ("lab3", driver3, 4, 8),
            ):
                ns_a, ns_b = kernels[lab]
                if lab == "lab2":
                    driver.call_deployed.side_effect = RuntimeError("failed acceptance rerun")
                else:
                    driver.broken_store_acceptance_gate.side_effect = RuntimeError("failed acceptance rerun")
                with self.assertRaisesRegex(RuntimeError, "failed acceptance rerun"):
                    source = cells(lab + "b")[fail_cell].replace(
                        'DEPLOYED_VERSION = ""', 'DEPLOYED_VERSION = "9"')
                    execute(source, ns_b)
                self.assertFalse((driver.ARTIFACTS / "part_b.json").exists())
                with self.assertRaisesRegex(RuntimeError, "successfully"):
                    execute(cells(lab + "b")[publish_cell], ns_b)
                if lab == "lab2":
                    driver.post_responses.side_effect = RuntimeError("failed local rerun")
                    source = cells("lab2a")[5]
                else:
                    driver.ask.side_effect = RuntimeError("failed local rerun")
                    source = cells("lab3a")[3]
                with self.assertRaisesRegex(RuntimeError, "failed local rerun"):
                    execute(source, ns_a)
                self.assertFalse((driver.ARTIFACTS / "part_a.json").exists())
                self.assertFalse((driver.ARTIFACTS / "part_b.json").exists())
                with self.assertRaisesRegex(RuntimeError, "successfully"):
                    execute(cells(lab + "a")[-1], ns_a)

    def test_labs2_and3_b_reject_missing_changed_scope_evidence_and_source(self) -> None:
        for lab in ("lab2", "lab3"):
            with self.subTest(lab=lab):
                driver = self.fake_driver(lab)
                driver.build()
                driver.demo()
                b = cells(lab + "b")
                with (
                    patch.object(foundry_env, "load_env", return_value=ENV),
                    patch.object(lab_helpers, "load_lab_module", return_value=driver),
                    patch.object(lab_helpers, "require_artifact", side_effect=self.artifact),
                    patch("subprocess.run") as deploy,
                    patch("builtins.print"),
                ):
                    ns: dict = {}
                    (driver.ARTIFACTS / "part_b.json").write_text("{}")
                    execute(b[0], ns, artifacts=self.artifacts)
                    self.assertFalse((driver.ARTIFACTS / "part_b.json").exists())
                    with self.assertRaisesRegex(RuntimeError, "checkpoint"):
                        execute(b[1], ns)
                    evidence = driver.TRANSCRIPTS if lab == "lab2" else driver.ARTIFACTS / "knowledge.json"
                    original_evidence = evidence.read_text()
                    notebook_parts.write_checkpoint(
                        driver.ARTIFACTS / "part_a.json", lab=lab, part="a",
                        context=notebook_parts.scope({**ENV, "MARKETPLACE_RESOURCE_SUFFIX": "other"}),
                        evidence=[evidence])
                    with self.assertRaisesRegex(RuntimeError, "context"):
                        execute(b[1], ns)
                    notebook_parts.write_checkpoint(
                        driver.ARTIFACTS / "part_a.json", lab=lab, part="a",
                        context=notebook_parts.scope(ENV), evidence=[evidence])
                    evidence.write_text('{"changed": true}')
                    with self.assertRaisesRegex(RuntimeError, "changed"):
                        execute(b[1], ns)
                    evidence.write_text(original_evidence)
                    notebook_parts.write_checkpoint(
                        driver.ARTIFACTS / "part_a.json", lab=lab, part="a",
                        context=notebook_parts.scope(ENV), evidence=[evidence],
                        state={"agent_name": driver.AGENT_NAME, "hosted_source_sha256": "changed",
                               "local_tools": "passed", "instruction_boundary": "passed",
                               "citations": "passed", "knowledge_boundary": "passed"})
                    with self.assertRaises(RuntimeError):
                        execute(b[1], ns)
                    deploy.assert_not_called()

    def test_lab3_shared_scale_configuration_runs_the_gate(self) -> None:
        driver = self.fake_driver("lab3")
        namespace = {"ENV": {**ENV, "MARKETPLACE_BLOB_STORAGE_URL": "https://approved.blob.core.windows.net"},
                     "lab3": driver, "ARTIFACTS": driver.ARTIFACTS,
                     "knowledge": {"mcp_endpoint": "https://approved.test/mcp"}}
        execute(cells("lab3b")[5], namespace)
        driver.scale_out_acceptance_gate.assert_called_once_with(namespace["knowledge"])
        self.assertEqual(namespace["shared_scale"], "passed")

    def test_original_driver_imports_do_not_provision_or_demo(self) -> None:
        identity = MagicMock()
        indexes = MagicMock()
        knowledge = MagicMock()
        with patch.dict(sys.modules, {
            "azure": MagicMock(), "azure.identity": identity,
            "azure.search": MagicMock(), "azure.search.documents": MagicMock(),
            "azure.search.documents.indexes": indexes, "knowledge_base": knowledge,
        }), patch.object(foundry_env, "load_env", return_value=ENV), \
                patch("subprocess.Popen") as process, patch("subprocess.run") as command:
            for folder, source in (
                ("hosted-agent-basics", "lab2_hosted_basics"),
                ("hosted-knowledge-sessions", "lab3_hosted_knowledge"),
            ):
                spec = importlib.util.spec_from_file_location(
                    source + "_split_regression", ROOT / "labs" / folder / (source + ".py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertTrue(callable(module.build))
                self.assertTrue(callable(module.demo))
            identity.AzureCliCredential.assert_not_called()
            indexes.SearchIndexClient.assert_not_called()
            knowledge.build_index.assert_not_called()
            process.assert_not_called()
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
