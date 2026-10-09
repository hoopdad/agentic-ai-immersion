"""Offline checks of the real optional boundary; no credential acquisition or cloud writes."""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "3-day-labs"))
sys.path.insert(0, str(ROOT / "shared/hosted-delegation"))
from common import foundry_env, notebook_parts
import lab_helpers
import delegation

ENV = {
    "PROJECT_RESOURCE_ID": "/subscriptions/offline/resourceGroups/workshop/providers/Microsoft.CognitiveServices/accounts/offline/projects/test",
    "FOUNDRY_PROJECT_ENDPOINT": "https://offline.services.ai.azure.com/api/projects/test",
    "MARKETPLACE_RESOURCE_SUFFIX": "offline",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME": "chat",
    "EMBEDDING_MODEL_DEPLOYMENT_NAME": "embed",
}
TARGET = {
    "agent_name": "triage-offline", "version": "8",
    "project_endpoint": ENV["FOUNDRY_PROJECT_ENDPOINT"],
    "protocol_endpoint": ENV["FOUNDRY_PROJECT_ENDPOINT"] + "/agents/triage-offline/endpoint/protocols/openai",
    "capabilities": ["pending_advisor_approval"],
}
REQUEST = {
    "operation": "pending_case", "case_id": "CASE-offline", "session_id": "caller-offline",
    "participant_id": "P-1005", "message": "Which plan should I choose?",
    "traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01",
}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def pending() -> dict:
    return {**REQUEST, "status": "pending_advisor_approval", "deployed_version": "8",
            "trace_id": REQUEST["traceparent"].split("-")[1], "packet": {"case_id": REQUEST["case_id"]}}


class DelegationTests(unittest.IsolatedAsyncioTestCase):
    def client(self, payload: dict | None = None):
        client = MagicMock()
        client.with_options.return_value = client
        client.responses.create = AsyncMock(return_value=SimpleNamespace(
            status="completed", output_text=json.dumps(payload or pending()),
        ))
        return client

    async def test_pending_request_is_correlated_and_never_automatically_retried(self):
        client = self.client()
        result = await delegation.invoke_pending(client, TARGET, REQUEST, timeout=1)
        self.assertEqual(result["status"], "pending_advisor_approval")
        client.with_options.assert_called_once_with(max_retries=0, timeout=1)
        call = client.responses.create.call_args.kwargs
        self.assertEqual(json.loads(call["input"]), REQUEST)
        self.assertEqual(call["extra_headers"]["traceparent"], REQUEST["traceparent"])
        self.assertFalse(call["store"])

    async def test_auth_and_transport_errors_are_visible_without_replay(self):
        for error in (PermissionError("403 no callee access"), ConnectionError("network unavailable")):
            client = self.client()
            client.responses.create.side_effect = error
            with self.subTest(error=error), self.assertRaises(type(error)):
                await delegation.invoke_pending(client, TARGET, REQUEST, timeout=1)
            self.assertEqual(client.responses.create.await_count, 1)

    async def test_timeout_is_bounded_and_does_not_replay(self):
        client = self.client()
        async def never_completes(**kwargs):
            await asyncio.sleep(2)
        client.responses.create.side_effect = never_completes
        with self.assertRaises(TimeoutError):
            await delegation.invoke_pending(client, TARGET, REQUEST, timeout=0.01)
        self.assertEqual(client.responses.create.await_count, 1)

    async def test_unsafe_request_fails_before_network(self):
        client = self.client()
        for request in ({**REQUEST, "advisor_decision": "approve"}, {**REQUEST, "operation": "resume"},
                        {**REQUEST, "traceparent": "00-" + "0" * 32 + "-" + "2" * 16 + "-01"}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                await delegation.invoke_pending(client, TARGET, request)
        client.responses.create.assert_not_called()

    async def test_remote_failed_approved_or_wrong_version_is_not_pending_success(self):
        for changes in ({"status": "approved"}, {"advisor_decision": "approve"},
                        {"deployed_version": "9"}, {"session_id": "other"}, {"case_id": "other"}, {"trace_id": "other"}):
            client = self.client({**pending(), **changes})
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                await delegation.invoke_pending(client, TARGET, REQUEST)
        client = self.client()
        client.responses.create.return_value.status = "failed"
        with self.assertRaisesRegex(RuntimeError, "failed"):
            await delegation.invoke_pending(client, TARGET, REQUEST)

    def test_latest_or_stale_selector_cannot_invoke_an_accepted_version(self):
        rule = SimpleNamespace(type="FixedRatio", agent_version="8", traffic_percentage=100)
        details = SimpleNamespace(agent_endpoint=SimpleNamespace(version_selector=SimpleNamespace(version_selection_rules=[rule])))
        delegation.require_pinned_selector(details, "8")
        for field, value in (("agent_version", "9"), ("traffic_percentage", 50), ("type", "Latest")):
            old = getattr(rule, field)
            setattr(rule, field, value)
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "pinned"):
                delegation.require_pinned_selector(details, "8")
            setattr(rule, field, old)

    async def test_real_sdk_middleware_returns_pending_json_for_stream_and_nonstream(self):
        from agent_framework import AgentContext, Content, Message
        module = load(ROOT / "shared/hosted-delegation/hosted/main.py", "delegation_host_regression")
        for streaming in (False, True):
            context = AgentContext(agent=MagicMock(), messages=[Message(role="user", contents=[Content.from_text(json.dumps(REQUEST))])], stream=streaming)
            next_call = AsyncMock()
            with patch.object(module, "delegate_pending", new=AsyncMock(return_value=pending())), \
                    patch.object(module, "target_from_environment", return_value=TARGET), \
                    patch.dict(os.environ, {"FOUNDRY_AGENT_VERSION": "12"}):
                await module.DelegationBoundary().process(context, next_call)
                result = await context.result.get_final_response() if streaming else context.result
            next_call.assert_not_called()
            payload = json.loads(result.text)
            self.assertEqual(payload["caller_version"], "12")
            self.assertEqual(payload["status"], "pending_advisor_approval")
        normal = AgentContext(agent=MagicMock(), messages=[Message(role="user", contents=[Content.from_text("Explain HRA rules")])])
        await module.DelegationBoundary().process(normal, next_call)
        next_call.assert_awaited_once()

    async def test_caller_injects_actual_delegation_span_into_the_remote_request(self):
        from opentelemetry.sdk.trace import TracerProvider
        provider = TracerProvider()
        tracer = provider.get_tracer("delegation-test")
        module = load(ROOT / "shared/hosted-delegation/hosted/main.py", "delegation_trace_regression")
        sent = []
        async def remote(target, request, **kwargs):
            sent.append(request)
            return {**pending(), "traceparent": request["traceparent"]}
        with patch.object(module.trace, "get_tracer", return_value=tracer), \
                patch.object(module, "delegate_pending", side_effect=remote), \
                patch.object(module, "target_from_environment", return_value=TARGET):
            result = await module.delegate_request(json.dumps(REQUEST))
        self.assertEqual(sent[0]["traceparent"].split("-")[1], REQUEST["traceparent"].split("-")[1])
        self.assertNotEqual(sent[0]["traceparent"].split("-")[2], REQUEST["traceparent"].split("-")[2])
        self.assertEqual(result["remote_traceparent"], sent[0]["traceparent"])
        self.assertEqual(result["traceparent"], REQUEST["traceparent"])
        provider.shutdown()

    async def test_model_cannot_invent_delegation_arguments_or_replay_a_binding(self):
        module = load(ROOT / "shared/hosted-delegation/hosted/main.py", "delegation_bound_regression")
        with patch.object(module, "delegate_pending", new=AsyncMock()) as remote:
            with self.assertRaisesRegex(RuntimeError, "explicit pending_case"):
                await module.delegate_bound_request()
        remote.assert_not_called()
        self.assertEqual(module.delegate_triage.parameters()["properties"], {})

    def test_candidate_bootstrap_retains_core_tools_policy_and_registers_boundary(self):
        state_dir = ROOT / (".candidate-boot-test-" + uuid.uuid4().hex)
        package = state_dir / "package"
        (package / "common").mkdir(parents=True)
        accepted_file = package / "common" / "accepted_concierge.py"
        accepted_file.write_text(
            "from agent_framework import tool\n"
            "@tool\n"
            "def get_sponsor(sponsor_id: str) -> dict:\n"
            "    \"\"\"Retrieve the accepted sponsor fixture.\"\"\"\n"
            "    return {'sponsor_id': sponsor_id}\n"
            "HANDOFF_POLICY = 'Accepted policy stays intact.'\n", encoding="utf-8", newline="\n",
        )
        self.addCleanup(shutil.rmtree, state_dir, True)
        with patch.dict(os.environ, {
            **ENV, "MARKETPLACE_DELEGATION_AGENT_NAME": "candidate-offline",
            "MARKETPLACE_SESSION_DIR": str(state_dir),
        }):
            core = load(ROOT / "shared/hosted-knowledge-sessions/hosted/main.py", "candidate_core_boot_test")
        module = load(ROOT / "shared/hosted-delegation/hosted/main.py", "candidate_boot_test")
        accepted = load(accepted_file, "candidate_accepted_boot_test")
        sponsor = accepted.get_sponsor
        with patch.dict(sys.modules, {"core_product": core, "common.accepted_concierge": accepted}), \
                patch.dict(os.environ, {"MARKETPLACE_DELEGATION_AGENT_NAME": "candidate-offline"}), \
                patch.object(core, "HERE", package), \
                patch.object(module, "Agent") as constructor, \
                patch.object(core, "DefaultAzureCredential"), patch.object(core, "FoundryChatClient"), \
                patch.object(core, "knowledge_tool", return_value=None), \
                patch.object(core, "build_message_store", return_value=None):
            module.build_agent()
        kwargs = constructor.call_args.kwargs
        self.assertEqual(kwargs["name"], "candidate-offline")
        self.assertIn(sponsor, kwargs["tools"])
        self.assertIn(module.delegate_triage, kwargs["tools"])
        self.assertIn("Accepted policy stays intact.", kwargs["instructions"])
        self.assertTrue(kwargs["instructions"].endswith(core.guardrails.COMPLIANCE_INSTRUCTIONS))
        self.assertIsInstance(kwargs["middleware"][0], module.DelegationBoundary)

    async def test_async_entra_client_checks_selector_before_any_stateful_turn(self):
        project = MagicMock()
        project.__aenter__ = AsyncMock(return_value=project)
        project.__aexit__ = AsyncMock(return_value=False)
        credential = MagicMock()
        credential.__aenter__ = AsyncMock(return_value=credential)
        credential.__aexit__ = AsyncMock(return_value=False)
        rule = SimpleNamespace(type="FixedRatio", agent_version="9", traffic_percentage=100)
        details = SimpleNamespace(agent_endpoint=SimpleNamespace(version_selector=SimpleNamespace(version_selection_rules=[rule])))
        project.agents.get = AsyncMock(return_value=details)
        with patch("azure.ai.projects.aio.AIProjectClient", return_value=project) as factory, \
                patch("azure.identity.aio.DefaultAzureCredential", return_value=credential), \
                self.assertRaisesRegex(RuntimeError, "pinned"):
            await delegation.delegate_pending(TARGET, REQUEST, timeout=1)
        factory.assert_called_once_with(endpoint=TARGET["project_endpoint"], credential=credential, allow_preview=True)
        project.get_openai_client.assert_not_called()
        project.agents.get.assert_awaited_once_with(TARGET["agent_name"])

    async def test_selector_change_after_completed_turn_is_visible_without_replay(self):
        project = MagicMock()
        project.__aenter__ = AsyncMock(return_value=project)
        project.__aexit__ = AsyncMock(return_value=False)
        credential = MagicMock()
        credential.__aenter__ = AsyncMock(return_value=credential)
        credential.__aexit__ = AsyncMock(return_value=False)
        def details(version):
            rule = SimpleNamespace(type="FixedRatio", agent_version=version, traffic_percentage=100)
            return SimpleNamespace(agent_endpoint=SimpleNamespace(version_selector=SimpleNamespace(version_selection_rules=[rule])))
        project.agents.get = AsyncMock(side_effect=[details("8"), details("9")])
        client = self.client()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        project.get_openai_client.return_value = client
        with patch("azure.ai.projects.aio.AIProjectClient", return_value=project), \
                patch("azure.identity.aio.DefaultAzureCredential", return_value=credential), \
                self.assertRaisesRegex(RuntimeError, "pinned"):
            await delegation.delegate_pending(TARGET, REQUEST, timeout=1)
        self.assertEqual(client.responses.create.await_count, 1)
        self.assertEqual(project.agents.get.await_count, 2)


class OptionalNotebookTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / (".optional-test-" + uuid.uuid4().hex)
        self.workspace.mkdir()
        self.addCleanup(shutil.rmtree, self.workspace)
        self.artifacts = self.workspace / "artifacts"

    def artifact(self, lab, *names):
        path = self.artifacts / lab
        path.mkdir(parents=True, exist_ok=True)
        return path.joinpath(*names)

    def first_cell(self, lab):
        source = next((ROOT / "3-day-labs" / f"lab{lab:02}").glob("*.py"))
        converter = load(ROOT / "tools/py_to_ipynb.py", "optional_converter")
        nb = converter.build_notebook(source.read_text(), seed=source.stem)
        return "".join(next(c["source"] for c in nb["cells"] if c["cell_type"] == "code"))

    def execute(self, code):
        value = eval(compile(code, "optional_cell", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT), {"__name__": "__main__"})
        if asyncio.iscoroutine(value):
            asyncio.run(value)

    def test_lab12_requires_both_predecessors_before_deployment_or_authentication(self):
        for missing in ("lab4", "lab5"):
            def read(path, *, lab, part, context):
                if lab == missing:
                    raise RuntimeError("Run " + ("Lab 8" if lab == "lab4" else "Lab 9"))
                return {"state": {"triage_reference": TARGET}}
            with self.subTest(missing=missing), patch.dict(os.environ, ENV), \
                    patch.object(foundry_env, "load_env", return_value=ENV), \
                    patch.object(lab_helpers, "artifact_path", side_effect=self.artifact), \
                    patch.object(lab_helpers, "load_lab_module", return_value=MagicMock()), \
                    patch.object(notebook_parts, "read_checkpoint", side_effect=read), \
                    patch("subprocess.run") as deploy, self.assertRaisesRegex(RuntimeError, "Lab [89]"):
                self.execute(self.first_cell(12))
            deploy.assert_not_called()

    def test_lab11_and13_require_lab4_evidence_in_fresh_kernel(self):
        driver = SimpleNamespace(ENV=ENV, ARTIFACTS=self.artifact("stretch7"))
        for lab in (11, 13):
            with self.subTest(lab=lab), patch.object(lab_helpers, "load_lab_module", return_value=driver), \
                    patch.object(lab_helpers, "artifact_path", side_effect=self.artifact), \
                    patch.object(notebook_parts, "read_checkpoint", side_effect=RuntimeError("Run Lab 4")) as read, \
                    self.assertRaisesRegex(RuntimeError, "Lab 4"):
                self.execute(self.first_cell(lab))
            self.assertEqual(read.call_args.kwargs["lab"], "lab2")
            self.assertEqual(read.call_args.kwargs["part"], "b")

    def test_delegation_checkpoint_changed_version_evidence_is_stale_and_legacy_is_rejected(self):
        target = self.artifact("hosted_delegation", "target.json")
        target.write_text(json.dumps(TARGET))
        checkpoint = self.artifact("hosted_delegation", "part_a.json")
        notebook_parts.write_checkpoint(checkpoint, lab="hosted_delegation", part="a",
                                        context=notebook_parts.scope(ENV), evidence=[target])
        target.write_text(json.dumps({**TARGET, "version": "9"}))
        with self.assertRaisesRegex(RuntimeError, "Lab 12"):
            notebook_parts.read_checkpoint(checkpoint, lab="hosted_delegation", part="a", context=notebook_parts.scope(ENV))
        with self.assertRaisesRegex(RuntimeError, "obsolete.*Lab 12"):
            notebook_parts.read_checkpoint(self.artifact("stretch6", "part_b.json"), lab="stretch6", part="b", context=notebook_parts.scope(ENV))

    def test_candidate_preparation_preserves_accepted_module_and_never_mutates_core(self):
        module = load(ROOT / "shared/hosted-delegation/hosted/prepare.py", "candidate_prepare_test")
        core = self.workspace / "core"
        (core / "common").mkdir(parents=True)
        (core / "main.py").write_text("CORE = True\n")
        (core / "common/accepted_concierge.py").write_text("ACCEPTED = True\n")
        for name in ("common", "data"):
            (self.workspace / name).mkdir()
            (self.workspace / name / "fixture.py").write_text("fixture = True\n")
        candidate = self.workspace / "candidate" / "hosted"
        candidate.mkdir(parents=True)
        (candidate.parent / "delegation.py").write_text("BOUNDARY = True\n")
        before = {p: p.read_bytes() for p in core.rglob("*") if p.is_file()}
        with patch.object(module, "CORE", core), patch.object(module, "ROOT", self.workspace), patch.object(module, "HERE", candidate):
            module.vendor()
        self.assertEqual((candidate / "common/accepted_concierge.py").read_text(), "ACCEPTED = True\n")
        self.assertEqual((candidate / "core_product.py").read_text(), "CORE = True\n")
        self.assertEqual(before, {p: p.read_bytes() for p in core.rglob("*") if p.is_file()})

    def test_candidate_vendors_exact_lab5_generated_accepted_behavior(self):
        import hashlib
        transfer = load(ROOT / "shared/hosted-knowledge-sessions/hosted/prepare.py", "accepted_transfer_candidate_test")
        candidate_prepare = load(ROOT / "shared/hosted-delegation/hosted/prepare.py", "actual_transfer_candidate_prepare")
        source = self.workspace / "accepted_basics.py"
        source.write_text(
            "from typing import Annotated\nfrom pydantic import Field\nfrom agent_framework import tool\n"
            "from common import marketplace_data\n"
            "PID = Annotated[str, Field(description='Sponsor identifier')]\n"
            "@tool\n"
            "def get_sponsor(sponsor_id: PID) -> dict:\n"
            "    \"\"\"Retrieve the accepted sponsor.\"\"\"\n"
            "    return marketplace_data.get_sponsor(sponsor_id)\n"
            "ROLE_INSTRUCTIONS = '1. Verify facts.\\n3. Enrollment requests require a licensed advisor.\\n4. Keep responses short.'\n",
            encoding="utf-8", newline="\n",
        )
        core = self.workspace / "accepted_core"
        core.mkdir()
        (core / "main.py").write_text("CORE = True\n")
        with patch.object(transfer, "HERE", core):
            accepted = transfer.transfer_accepted_behavior(source, hashlib.sha256(source.read_bytes()).hexdigest())
        original = (core / "common" / "accepted_concierge.py").read_bytes()
        for name in ("common", "data"):
            (self.workspace / name).mkdir()
            (self.workspace / name / "fixture.py").write_text("fixture = True\n")
        candidate = self.workspace / "candidate" / "hosted"
        candidate.mkdir(parents=True)
        (candidate.parent / "delegation.py").write_text("BOUNDARY = True\n")
        with patch.object(candidate_prepare, "CORE", core), patch.object(candidate_prepare, "ROOT", self.workspace), \
                patch.object(candidate_prepare, "HERE", candidate):
            candidate_prepare.vendor()
        copied = candidate / "common" / "accepted_concierge.py"
        self.assertEqual(copied.read_bytes(), original)
        self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), accepted["transfer_sha256"])
        product = load(copied, "generated_candidate_behavior_test")
        self.assertEqual(product.HANDOFF_POLICY, accepted["handoff_policy"])
        self.assertEqual(product.get_sponsor.name, "get_sponsor")


class PromptComparisonTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_prompt_version_one_pinned_name_endpoint_turn_and_no_tools(self):
        with patch.object(foundry_env, "load_env", return_value=ENV):
            module = load(ROOT / "shared/prompt-agents-and-workflows/stretch6_prompt_agents.py", "minimal_prompt_test")
        project = MagicMock()
        project.__aenter__ = AsyncMock(return_value=project)
        project.__aexit__ = AsyncMock(return_value=False)
        project.agents.create_version = AsyncMock(return_value=SimpleNamespace(version="11", id="prompt-id"))
        project.agents.update_details = AsyncMock()
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.responses.create = AsyncMock(return_value=SimpleNamespace(
            status="completed", output_text="A licensed advisor can help. Contact the advisor.", id="response-11",
        ))
        project.get_openai_client.return_value = client
        credential = MagicMock()
        credential.__aenter__ = AsyncMock(return_value=credential)
        credential.__aexit__ = AsyncMock(return_value=False)
        with patch("azure.ai.projects.aio.AIProjectClient", return_value=project), \
                patch("azure.identity.aio.DefaultAzureCredential", return_value=credential):
            result = await module.publish_and_invoke(ENV, "Who helps me choose a plan?")
        project.agents.create_version.assert_awaited_once()
        definition = project.agents.create_version.call_args.kwargs["definition"]
        self.assertEqual(definition.kind, "prompt")
        self.assertFalse(definition.tools)
        self.assertTrue(definition.instructions.endswith(module.guardrails.COMPLIANCE_INSTRUCTIONS))
        selector = project.agents.update_details.call_args.kwargs["agent_endpoint"].version_selector
        self.assertEqual(selector.version_selection_rules[0].agent_version, "11")
        self.assertEqual(selector.version_selection_rules[0].traffic_percentage, 100)
        project.get_openai_client.assert_called_once_with(agent_name=result["agent_name"], max_retries=0, timeout=60)
        client.responses.create.assert_awaited_once_with(input="Who helps me choose a plan?", store=False)
        self.assertTrue(result["terminal"])

    def test_hosted_delegation_has_no_prompt_graph_dependency(self):
        products = (
            "hosted-agent-basics/hosted", "hosted-knowledge-sessions/hosted",
            "hosted-multi-agent-handoff/hosted", "hosted-delegation",
            "invocations-toolbox-skills/hosted-invocations",
            "invocations-toolbox-skills/hosted-responses-skills",
        )
        forbidden = {
            "PromptAgentDefinition", "FoundryAgent", "triage_workflow", "triage_agents",
            "stretch6_prompt_agents", "prompt-agents-and-workflows", "publish_prompt_agents",
            "publish_and_invoke", "agent_reference",
        }
        for product in products:
            for path in (ROOT / "shared" / product).rglob("*.py"):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name):
                        names = {node.id}
                    elif isinstance(node, ast.Attribute):
                        names = {node.attr}
                    elif isinstance(node, ast.Import):
                        names = {item.name.split(".")[0] for item in node.names}
                    elif isinstance(node, ast.ImportFrom):
                        names = {*(node.module or "").split("."), *(item.name for item in node.names)}
                    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                        names = {name for name in forbidden if name in node.value}
                    else:
                        continue
                    with self.subTest(path=path, line=getattr(node, "lineno", None)):
                        self.assertFalse(names & forbidden, f"Hosted runtime depends on terminal prompts: {names & forbidden}")
        notebook = (ROOT / "3-day-labs/lab12/lab12_workflows_delegation.py").read_text()
        self.assertNotIn('artifact_path("stretch6"', notebook)
        self.assertNotIn("publish_prompt", notebook)


if __name__ == "__main__":
    unittest.main()
