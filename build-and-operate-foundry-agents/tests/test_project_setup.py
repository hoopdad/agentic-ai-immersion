"""Offline coverage of the attendee-scoped first notebook (no Azure calls)."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "shared/foundry-project-models"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB))
import project_setup as setup

SUB = "11111111-1111-1111-1111-111111111111"
TENANT = "22222222-2222-2222-2222-222222222222"
ACCOUNT_ID = f"/subscriptions/{SUB}/resourceGroups/approved/providers/Microsoft.CognitiveServices/accounts/foundry"
PROJECT_ID = ACCOUNT_ID + "/projects/healthcare-marketplace-jd-4821"
CURRENT = {"id": SUB, "tenantId": TENANT, "state": "Enabled", "name": "approved"}
ACCOUNT = {"id": ACCOUNT_ID, "name": "foundry", "kind": "AIServices", "location": "eastus",
           "properties": {"allowProjectManagement": True, "provisioningState": "Succeeded",
                          "endpoints": {"OpenAI": "https://approved.openai.azure.com/"}}}
MODEL = {"format": "OpenAI", "name": "gpt-chat", "version": "live-version",
         "skus": [{"name": "GlobalStandard"}]}
SPEC = {"sku": {"name": "GlobalStandard", "capacity": 10},
        "properties": {"model": {"format": "OpenAI", "name": "gpt-chat", "version": "live-version"}}}


class FakeCLI:
    def __init__(self, runs: list | None = None, reads: list | None = None, items: list | None = None):
        self.runs = iter(runs or [])
        self.reads = iter(reads or [])
        self.listed = items or []
        self.calls: list[tuple] = []

    def run(self, *args: str) -> object:
        self.calls.append(args)
        result = next(self.runs)
        if isinstance(result, Exception):
            raise result
        return result

    def rest(self, method: str, resource_id: str, body: dict | None = None) -> dict:
        self.calls.append((method, resource_id, body))
        return {} if method == "put" else next(self.reads)

    def items(self, resource_id: str) -> list:
        self.calls.append(("items", resource_id))
        return self.listed


class ProjectSetupTests(unittest.TestCase):
    def test_reuses_credentials_without_login_or_switching(self) -> None:
        cli = FakeCLI(runs=[CURRENT, {"accessToken": "not-persisted"}])
        self.assertEqual(setup.azure_context(cli, SUB, TENANT)["subscription_id"], SUB)
        self.assertFalse(any("login" in c or "set" in c for c in cli.calls))

    def test_context_mismatch_aborts_before_any_write(self) -> None:
        for sub, tenant in (("33333333-3333-3333-3333-333333333333", TENANT),
                            (SUB, "33333333-3333-3333-3333-333333333333")):
            with self.subTest(sub=sub, tenant=tenant):
                cli = FakeCLI(runs=[CURRENT])
                with self.assertRaises(RuntimeError):
                    setup.azure_context(cli, sub, tenant)
                self.assertEqual(len(cli.calls), 1)

    def test_login_only_if_unavailable_and_reverify_context(self) -> None:
        cli = FakeCLI(runs=[RuntimeError("no login"), {}, CURRENT, {}])
        setup.azure_context(cli, SUB, TENANT)
        self.assertIn(("login", "--use-device-code", "--tenant", TENANT), cli.calls)
        cli = FakeCLI(runs=[CURRENT, RuntimeError("expired"), {}, {**CURRENT, "id": TENANT}])
        with self.assertRaisesRegex(RuntimeError, "changed Azure context"):
            setup.azure_context(cli, SUB, TENANT)

    def test_subprocess_has_no_shell_and_login_prompt_is_visible(self) -> None:
        with patch.object(setup.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout='{"value": []}')) as run:
            setup.AzureCLI().rest("get", ACCOUNT_ID)
            self.assertIn(f"https://management.azure.com{ACCOUNT_ID}?api-version=2025-06-01", run.call_args.args[0])
            self.assertNotIn("shell", run.call_args.kwargs)
            setup.AzureCLI().run("login", "--use-device-code")
            self.assertNotIn("capture_output", run.call_args.kwargs)

    def test_subprocess_failure_does_not_leak_response(self) -> None:
        with patch.object(setup.subprocess, "run", return_value=SimpleNamespace(
            returncode=1, stdout="token-secret", stderr="token-secret")):
            with self.assertRaises(RuntimeError) as error:
                setup.AzureCLI().run("account", "show")
            self.assertNotIn("token-secret", str(error.exception))

    def test_existing_account_required_and_scoped(self) -> None:
        context = {"subscription_id": SUB}
        cli = FakeCLI(reads=[ACCOUNT])
        self.assertEqual(setup.verify_account(cli, context, "approved", "foundry"), ACCOUNT)
        for account in ({**ACCOUNT, "kind": "OpenAI"},
                        {**ACCOUNT, "properties": {"provisioningState": "Succeeded"}},
                        {**ACCOUNT, "id": ACCOUNT_ID.replace(SUB, TENANT)}):
            with self.assertRaises(RuntimeError):
                setup.verify_account(FakeCLI(reads=[account]), context, "approved", "foundry")
        with self.assertRaises(ValueError):
            setup.verify_account(cli, context, "../bad", "foundry")

    def test_versions_are_selected_only_from_live_inventory(self) -> None:
        self.assertEqual(setup.choose_model([MODEL], "gpt-chat", "", "GlobalStandard", 10), SPEC)
        other = {**MODEL, "version": "another"}
        with self.assertRaises(ValueError):
            setup.choose_model([MODEL, other], "gpt-chat", "", "GlobalStandard", 10)
        default = {**other, "isDefaultVersion": True}
        self.assertEqual(setup.choose_model([MODEL, default], "gpt-chat", "", "GlobalStandard", 10)
                         ["properties"]["model"]["version"], "another")
        for version, sku, capacity in (("stale", "GlobalStandard", 10),
                                       ("", "unsupported", 10), ("", "GlobalStandard", 0)):
            with self.assertRaises(ValueError):
                setup.choose_model([MODEL], "gpt-chat", version, sku, capacity)

    def test_capacity_is_checked_against_advertised_limits(self) -> None:
        model = {**MODEL, "skus": [{"name": "GlobalStandard", "capacity": {
            "minimum": 10, "maximum": 50, "step": 10}}]}
        for capacity in (1, 11, 60):
            with self.assertRaises(ValueError):
                setup.choose_model([model], "gpt-chat", "", "GlobalStandard", capacity)

    def test_zero_maximum_and_nonpositive_steps_are_rejected(self) -> None:
        for limits in ({"maximum": 0}, {"step": 0}, {"step": -1}):
            with self.subTest(limits=limits):
                model = {**MODEL, "skus": [{"name": "GlobalStandard", "capacity": limits}]}
                with self.assertRaises(ValueError):
                    setup.choose_model([model], "gpt-chat", "", "GlobalStandard", 10)
        model = {**MODEL, "skus": [{"name": "GlobalStandard", "capacity": {
            "minimum": None, "maximum": None, "step": None}}]}
        self.assertEqual(setup.choose_model([model], "gpt-chat", "", "GlobalStandard", 10), SPEC)

    def test_project_creation_tags_attendee_and_polls(self) -> None:
        project = {"id": PROJECT_ID, "properties": {"provisioningState": "Succeeded"}}
        cli = FakeCLI(reads=[project])
        self.assertEqual(setup.ensure_project(cli, ACCOUNT, "jd-4821"), project)
        put = next(c for c in cli.calls if c[0] == "put")
        self.assertEqual(put[1], PROJECT_ID)
        self.assertEqual(put[2]["identity"]["type"], "SystemAssigned")
        self.assertEqual(put[2]["tags"]["marketplace-resource-suffix"], "jd-4821")
        self.assertFalse(any(c[0] == "put" and c[1] == ACCOUNT_ID for c in cli.calls))

    def test_unowned_existing_project_is_never_overwritten(self) -> None:
        cli = FakeCLI(items=[{"name": "healthcare-marketplace-jd-4821"}])
        with self.assertRaisesRegex(RuntimeError, "not owned"):
            setup.ensure_project(cli, ACCOUNT, "jd-4821")
        self.assertFalse(any(c[0] == "put" for c in cli.calls))

    def test_deployments_reuse_compatible_and_reject_every_mismatch(self) -> None:
        deployment = {**SPEC, "id": ACCOUNT_ID + "/deployments/marketplace-chat-jd-4821",
                      "name": "marketplace-chat-jd-4821",
                      "properties": {**SPEC["properties"], "provisioningState": "Succeeded"}}
        cli = FakeCLI(reads=[deployment], items=[deployment])
        setup.ensure_deployment(cli, ACCOUNT, deployment["name"], SPEC)
        self.assertFalse(any(c[0] == "put" for c in cli.calls))
        for incompatible in (
            {**deployment, "sku": {"name": "Standard", "capacity": 10}},
            {**deployment, "sku": {"name": "GlobalStandard", "capacity": 1}},
            {**deployment, "properties": {"model": {**SPEC["properties"]["model"], "version": "old"}}},
        ):
            cli = FakeCLI(items=[incompatible])
            with self.assertRaisesRegex(RuntimeError, "incompatible"):
                setup.ensure_deployment(cli, ACCOUNT, deployment["name"], SPEC)
            self.assertFalse(any(c[0] == "put" for c in cli.calls))

    def test_new_deployment_waits_and_confirms_model(self) -> None:
        name = "marketplace-chat-jd-4821"
        deployment = {"id": ACCOUNT_ID + "/deployments/" + name, **SPEC,
                      "properties": {**SPEC["properties"], "provisioningState": "Succeeded"}}
        cli = FakeCLI(reads=[{"properties": {"provisioningState": "Creating"}}, deployment])
        with patch.object(setup.time, "sleep"):
            setup.ensure_deployment(cli, ACCOUNT, name, SPEC)
        self.assertTrue(any(c[0] == "put" for c in cli.calls))
        cli = FakeCLI(reads=[{**deployment, "sku": {"name": "Standard"}}])
        with self.assertRaisesRegex(RuntimeError, "incompatible"):
            setup.ensure_deployment(cli, ACCOUNT, name, SPEC)

    def test_poll_failure_and_timeout(self) -> None:
        with self.assertRaises(RuntimeError):
            setup.poll_resource(FakeCLI(reads=[{"properties": {"provisioningState": "Failed"}}]), PROJECT_ID)
        with self.assertRaises(TimeoutError):
            setup.poll_resource(FakeCLI(reads=[{"properties": {"provisioningState": "Creating"}}]), PROJECT_ID, timeout=0)

    def test_endpoints_are_returned_not_guessed(self) -> None:
        project = {"id": PROJECT_ID, "properties": {"endpoints": {
            "AI Foundry API": "https://approved.services.ai.azure.com/api/projects/healthcare-marketplace-jd-4821"}}}
        endpoint, openai = setup.endpoints(ACCOUNT, project)
        self.assertIn("/api/projects/healthcare-marketplace-jd-4821", endpoint)
        self.assertEqual(openai, "https://approved.openai.azure.com/")
        with self.assertRaises(RuntimeError):
            setup.endpoints(ACCOUNT, {"id": PROJECT_ID, "properties": {"endpoints": {}}})
        account = {**ACCOUNT, "properties": {**ACCOUNT["properties"], "endpoints": {
            **ACCOUNT["properties"]["endpoints"], "AI Foundry API": "https://approved.services.ai.azure.com/"}}}
        self.assertEqual(setup.endpoints(account, {"id": PROJECT_ID})[0], endpoint)

    def test_both_model_smoke_responses_required(self) -> None:
        chat = {"choices": [{"message": {"content": "Hello!"}}]}
        vector = {"data": [{"embedding": [0.1] * 3072}]}
        cli = FakeCLI(runs=[chat, vector])
        with patch("builtins.print"):
            evidence = setup.smoke_test(cli, "https://approved.openai.azure.com/", "chat", "embedding")
        self.assertEqual(evidence["embedding_dimensions"], 3072)
        self.assertTrue(all(c[4] == "https://cognitiveservices.azure.com" for c in cli.calls))
        self.assertEqual(json.loads(cli.calls[0][-1])["model"], "chat")
        for responses in ([{"choices": []}], [chat, {"data": [{"embedding": [0.1]}]}]):
            with self.assertRaises(RuntimeError):
                setup.smoke_test(FakeCLI(runs=responses), "https://approved.openai.azure.com/", "chat", "embedding")

    def test_env_preserves_unrelated_values_and_removes_output_duplicates(self) -> None:
        # Scratch files stay in the owned project directory, never system temporary directories.
        path = LAB / f".env-test-{uuid.uuid4().hex}"
        before = "# Keep comment\nUNRELATED=untouched\nAZURE_AI_SEARCH_ENDPOINT=https://approved.search.windows.net\n"
        try:
            path.write_text(before + "export TENANT_ID=old\nTENANT_ID=duplicate\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch.object(setup.os, "open", wraps=os.open) as open_file:
                setup.write_env(path, {"TENANT_ID": TENANT, "FOUNDRY_MODEL": "chat-jd-4821"})
                self.assertEqual(os.environ["TENANT_ID"], TENANT)
            open_file.assert_called_once_with(
                path.with_name(path.name + ".project-setup-new"),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
            )
            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith(before))
            self.assertEqual(content.count("TENANT_ID="), 1)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(path.with_name(path.name + ".project-setup-new").exists())
            with self.assertRaises(ValueError):
                setup.write_env(path, {"TOKEN": "secret"})
            with self.assertRaises(ValueError):
                setup.write_env(path, {"TENANT_ID": "bad\nINJECT=1"})
        finally:
            path.unlink(missing_ok=True)

    def test_approved_optional_config_persists_without_endpoint_credentials(self) -> None:
        path = LAB / f".env-test-{uuid.uuid4().hex}"
        values = {
            "AZURE_AI_SEARCH_ENDPOINT": "https://approved.search.windows.net",
            "MARKETPLACE_BLOB_STORAGE_URL": "https://approved.blob.core.windows.net",
            "MARKETPLACE_BLOB_STORAGE_CONTAINER": "marketplace-history",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": f"InstrumentationKey={TENANT};IngestionEndpoint=https://eastus.in.applicationinsights.azure.com/",
            "MARKETPLACE_TODAY": "2026-10-06",
        }
        try:
            with patch.dict(os.environ, {}, clear=True):
                setup.write_env(path, values)
                self.assertEqual({key: os.environ[key] for key in values}, values)
            self.assertTrue(all(f'{key}="{value}"' in path.read_text() for key, value in values.items()))
            for key, value in (
                ("MARKETPLACE_BLOB_STORAGE_URL", "https://approved.blob.core.windows.net/?sig=secret"),
                ("AZURE_AI_SEARCH_ENDPOINT", "******approved.search.windows.net"),
                ("MARKETPLACE_TODAY", "not-a-date"),
                ("AZURE_CLIENT_SECRET", "secret"),
            ):
                with self.assertRaises(ValueError):
                    setup.write_env(path, {key: value})
        finally:
            path.unlink(missing_ok=True)

    def test_notebook_is_generated_described_and_not_executed(self) -> None:
        spec = importlib.util.spec_from_file_location("converter", ROOT / "tools/py_to_ipynb.py")
        converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(converter)
        for source, name in (
            ("lab1_identity_project.py", "lab1_walkthrough.ipynb"),
            ("lab2_models_verify.py", "lab2_walkthrough.ipynb"),
        ):
            with self.subTest(source=source):
                folder = ROOT / "labs" / source.split("_")[0]
                text = (folder / source).read_text(encoding="utf-8")
                notebook = json.loads((folder / name).read_text(encoding="utf-8"))
                self.assertEqual(notebook, converter.build_notebook(text, seed=Path(source).stem))
                self.assertEqual(converter.validate_notebook(notebook), [])
                self.assertEqual(converter.validate_step_ids(notebook, Path(source).stem.split("_")[0][3:]), [])
                for index, cell in enumerate(notebook["cells"]):
                    if cell["cell_type"] == "code":
                        self.assertGreater(index, 0)
                        self.assertEqual(notebook["cells"][index - 1]["cell_type"], "markdown")
                        self.assertIsNone(cell["execution_count"])
                        self.assertEqual(cell["outputs"], [])
                self.assertNotIn("if __name__", text)

    def test_original_driver_handoff_and_stale_smoke_regressions_offline(self) -> None:
        spec = importlib.util.spec_from_file_location("converter", ROOT / "tools/py_to_ipynb.py")
        converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(converter)
        source = LAB / "lab1_project_models.py"
        notebook = converter.build_notebook(source.read_text(encoding="utf-8"), seed=source.stem)
        cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
        namespace: dict = {}
        project = {"id": PROJECT_ID, "properties": {"endpoints": {
            "AI Foundry API": "https://approved.services.ai.azure.com/api/projects/healthcare-marketplace-jd-4821"}}}
        models = [{**MODEL, "name": "gpt-5.4-mini"}, {**MODEL, "name": "text-embedding-3-large",
                  "skus": [{"name": "Standard"}]}]
        evidence = {"chat": "passed", "embedding": "passed", "embedding_dimensions": 3072}
        with (
            patch.object(setup.AzureCLI, "run", side_effect=AssertionError("No cloud calls in tests")),
            patch.object(setup.AzureCLI, "items", return_value=models),
            patch.object(setup, "azure_context", return_value={
                "subscription_id": SUB, "tenant_id": TENANT, "subscription_name": "approved"}),
            patch.object(setup, "account_inventory", return_value=[]),
            patch.object(setup, "verify_account", return_value=ACCOUNT),
            patch.object(setup, "ensure_project", return_value=project) as provision_project,
            patch.object(setup, "ensure_deployment", side_effect=lambda cli, account, name, spec: {"name": name}),
            patch.object(setup, "smoke_test", return_value=evidence),
            patch.object(setup, "write_env") as write_env,
            patch("common.foundry_env.load_env", side_effect=lambda: namespace["OUTPUT_ENV"]),
            patch("common.foundry_env.save_artifact") as save_artifact,
            patch("builtins.print"),
        ):
            exec(compile(cells[0], "<notebook>", "exec"), namespace)
            self.assertEqual(namespace["ARTIFACT"], ROOT / "labs/artifacts/lab1/project.json")
            namespace["ARTIFACT"] = LAB / f".checkpoint-test-{uuid.uuid4().hex}.json"
            exec(compile(cells[1], "<notebook>", "exec"), namespace)
            namespace.update(SUBSCRIPTION_ID=SUB, TENANT_ID=TENANT, RESOURCE_GROUP="approved",
                             FOUNDRY_ACCOUNT_NAME="foundry", ATTENDEE_SUFFIX="jd-4821",
                             AZURE_AI_SEARCH_ENDPOINT="https://approved.search.windows.net",
                             MARKETPLACE_BLOB_STORAGE_URL="https://approved.blob.core.windows.net",
                             MARKETPLACE_BLOB_STORAGE_CONTAINER="marketplace-history",
                             APPLICATIONINSIGHTS_CONNECTION_STRING=f"InstrumentationKey={TENANT}")
            for cell in cells[2:5]:
                exec(compile(cell, "<notebook>", "exec"), namespace)
            self.assertFalse(namespace["APPROVE_PROVISIONING"])
            namespace["APPROVE_PROVISIONING"] = True
            for cell in cells[5:]:
                exec(compile(cell, "<notebook>", "exec"), namespace)
            approved_values = write_env.call_args.args[1].copy()
            namespace.update(AZURE_AI_SEARCH_ENDPOINT="", MARKETPLACE_BLOB_STORAGE_URL="",
                             MARKETPLACE_BLOB_STORAGE_CONTAINER="", APPLICATIONINSIGHTS_CONNECTION_STRING="")
            exec(compile(cells[-1], "<notebook>", "exec"), namespace)
            self.assertEqual(set(write_env.call_args.args[1]), setup.PROJECT_ENV_KEYS | {"MARKETPLACE_TODAY"})
            checkpoint = json.loads(json.dumps(save_artifact.call_args.args[1]))
            output_path = write_env.call_args.args[0]

            # A failed smoke rerun for the same target invalidates prior success and its checkpoint.
            write_env.reset_mock()
            save_artifact.reset_mock()
            namespace["ARTIFACT"].write_text("{}", encoding="utf-8")
            with patch.object(setup, "smoke_test", side_effect=RuntimeError("offline smoke failure")):
                with self.assertRaisesRegex(RuntimeError, "offline smoke failure"):
                    exec(compile(cells[6], "<notebook>", "exec"), namespace)
            self.assertEqual(namespace["SMOKE_TESTS"], {})
            self.assertIsNone(namespace["SMOKE_TARGET"])
            self.assertFalse(namespace["ARTIFACT"].exists())
            with self.assertRaisesRegex(RuntimeError, "exact project"):
                exec(compile(cells[7], "<notebook>", "exec"), namespace)
            write_env.assert_not_called()
            save_artifact.assert_not_called()

            # After success, reprovision another target, fail its smoke, then attempt publishing.
            exec(compile(cells[6], "<notebook>", "exec"), namespace)
            exec(compile(cells[7], "<notebook>", "exec"), namespace)
            namespace["ARTIFACT"].write_text("{}", encoding="utf-8")
            provision_project.return_value = {
                "id": PROJECT_ID.replace("jd-4821", "ab-4821"),
                "properties": {"endpoints": {"AI Foundry API":
                    "https://approved.services.ai.azure.com/api/projects/healthcare-marketplace-ab-4821"}},
            }
            namespace.update(SUFFIX="ab-4821", CHAT_NAME="marketplace-chat-ab-4821",
                             EMBEDDING_NAME="marketplace-embedding-ab-4821")
            write_env.reset_mock()
            save_artifact.reset_mock()
            exec(compile(cells[5], "<notebook>", "exec"), namespace)
            self.assertEqual(namespace["SMOKE_TESTS"], {})
            self.assertIsNone(namespace["SMOKE_TARGET"])
            self.assertFalse(namespace["ARTIFACT"].exists())
            with patch.object(setup, "smoke_test", side_effect=RuntimeError("new target smoke failure")):
                with self.assertRaisesRegex(RuntimeError, "new target smoke failure"):
                    exec(compile(cells[6], "<notebook>", "exec"), namespace)
            with self.assertRaisesRegex(RuntimeError, "exact project"):
                exec(compile(cells[7], "<notebook>", "exec"), namespace)
            write_env.assert_not_called()
            save_artifact.assert_not_called()

            # Success cannot be reused after editing a deployment spec in place.
            exec(compile(cells[6], "<notebook>", "exec"), namespace)
            namespace["CHAT_SPEC"]["properties"]["model"]["version"] = "edited-version"
            with self.assertRaisesRegex(RuntimeError, "exact project"):
                exec(compile(cells[7], "<notebook>", "exec"), namespace)
            write_env.assert_not_called()
            save_artifact.assert_not_called()
            self.assertFalse(namespace["ARTIFACT"].exists())
        self.assertEqual(set(checkpoint), {
            "schema_version", "verified_at", "subscription_id", "tenant_id", "account_resource_id",
            "project_resource_id", "project_endpoint", "azure_openai_endpoint", "resource_suffix",
            "chat_deployment", "embedding_deployment", "provisioning_state", "smoke_tests"})
        self.assertEqual(checkpoint["project_resource_id"], PROJECT_ID)
        self.assertEqual(checkpoint["provisioning_state"], "Succeeded")
        self.assertEqual(checkpoint["chat_deployment"]["properties"]["model"]["version"], "live-version")
        self.assertEqual(checkpoint["embedding_deployment"]["properties"]["model"]["name"], "text-embedding-3-large")
        self.assertEqual(checkpoint["smoke_tests"], evidence)
        self.assertEqual(set(approved_values), setup.ENV_KEYS)
        self.assertEqual(approved_values["MARKETPLACE_TODAY"], "2026-10-06")
        self.assertFalse(set(checkpoint) & setup.OPTIONAL_ENV_KEYS)
        self.assertEqual(output_path, ROOT.parent / ".env")


if __name__ == "__main__":
    unittest.main()
