"""Real MAF graph execution with offline agent responses; no Azure calls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import triage_workflow as workflow
import stretch6_prompt_agents as prompts
import hosted_tool_snippet as hosted


def valid_packet(**overrides):
    packet = {
        "case_id": "S1-offline", "participant_id": "P-1001", "lob": "marketplace",
        "summary": "The participant wants neutral plan education.",
        "participant_goals": ["Understand plan costs."],
        "facts_gathered": [{"fact": "AEP applies.", "source": "get_enrollment_window"}],
        "options_discussed": ["Neutral plan features"],
        "open_questions": ["Confirm the doctor network with the carrier."],
        "recommended_next_step_for_advisor": "Review the participant's questions.",
        "compliance_flags": [], "created_at": "2026-10-06T12:00:00+00:00",
    }
    return {**packet, **overrides}


HEADER = "TRIAGE CASE S1-offline\ncase_id: S1-offline\nparticipant_id: P-1001\nparticipant_message: Compare plan costs.\nfacts: AEP applies."


def offline_agents(route="marketplace", packet=None):
    replies = {
        "triage": f"ROUTE: {route}\nINTENT: Neutral education.",
        "marketplace": "Marketplace education [KB-MKT-002].",
        "accounts": "Accounts education [KB-ACC-001].",
        "compliance": "COMPLIANCE REVIEW\nverdict: pass\nrevised_reply: Neutral education for an advisor.",
        "handoff": json.dumps(packet or valid_packet(lob=route)),
    }
    return {role: SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(text=text)))
            for role, text in replies.items()}


class GraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_graph_runs_all_routes_once_with_one_final_packet(self):
        for route, expected in (
            ("marketplace", ["triage", "marketplace", "compliance", "handoff"]),
            ("accounts", ["triage", "accounts", "compliance", "handoff"]),
            ("both", ["triage", "marketplace", "accounts", "compliance", "handoff"]),
        ):
            with self.subTest(route=route):
                agents = offline_agents(route)
                run = await workflow.run_workflow(workflow.build_workflow(agents), HEADER)
                self.assertEqual([action["action_id"] for action in run["actions"]], expected)
                self.assertEqual(run["packet"]["lob"], route)
                for role, agent in agents.items():
                    self.assertEqual(agent.run.await_count, int(role in expected))
                handoff_input = agents["handoff"].run.call_args.args[0]
                self.assertIn(HEADER, handoff_input)
                self.assertIn("COMPLIANCE REVIEW", handoff_input)
                self.assertIn("Marketplace education" if route != "accounts" else "NO_MARKETPLACE_QUESTION", handoff_input)
                self.assertIn("Accounts education" if route != "marketplace" else "NO_ACCOUNTS_QUESTION", handoff_input)

    async def test_bad_route_stops_before_specialists(self):
        agents = offline_agents("unknown")
        with self.assertRaisesRegex(Exception, "ROUTE"):
            await workflow.run_workflow(workflow.build_workflow(agents), HEADER)
        agents["marketplace"].run.assert_not_awaited()
        agents["accounts"].run.assert_not_awaited()
        agents["handoff"].run.assert_not_awaited()

    async def test_failed_agent_does_not_emit_a_success_packet(self):
        agents = offline_agents()
        agents["compliance"].run.side_effect = RuntimeError("offline service failure")
        with self.assertRaisesRegex(Exception, "offline service failure"):
            await workflow.run_workflow(workflow.build_workflow(agents), HEADER)
        agents["handoff"].run.assert_not_awaited()

    async def test_packet_validation_prevents_final_output(self):
        for packet in (
            valid_packet(case_id="changed"),
            valid_packet(participant_id="P-9999"),
            valid_packet(lob="accounts"),
            valid_packet(options_discussed="not a list"),
            valid_packet(summary="Call 801-555-0100"),
            valid_packet(unexpected=True),
        ):
            with self.subTest(packet=packet), self.assertRaisesRegex(Exception, "packet rejected"):
                await workflow.run_workflow(workflow.build_workflow(offline_agents(packet=packet)), HEADER)

    async def test_each_run_has_fresh_case_state(self):
        for participant_id in ("P-1001", "P-1005"):
            agents = offline_agents(packet=valid_packet(participant_id=participant_id))
            run = await workflow.run_workflow(
                workflow.build_workflow(agents), HEADER.replace("P-1001", participant_id),
            )
            self.assertEqual(run["packet"]["participant_id"], participant_id)

    async def test_pinned_prompt_versions_and_local_tools_are_reused_without_publication(self):
        info = {
            "runtime": "microsoft-agent-framework", "graph_sha256": workflow.SOURCE_SHA256,
            "roles": {role: f"prompt-{role}" for role in workflow.ROLES},
            "agents": {f"prompt-{role}": {"agent_version": str(index + 1)}
                       for index, role in enumerate(workflow.ROLES)},
        }
        agents = offline_agents()
        credential = MagicMock()
        credential.__aenter__ = AsyncMock(return_value=credential)
        credential.__aexit__ = AsyncMock()
        project = MagicMock()
        project.__aenter__ = AsyncMock(return_value=project)
        project.__aexit__ = AsyncMock()
        contexts = []

        def connect(**kwargs):
            context = MagicMock()
            role = kwargs["agent_name"].removeprefix("prompt-")
            context.__aenter__ = AsyncMock(return_value=agents[role])
            context.__aexit__ = AsyncMock()
            contexts.append(context)
            return context

        with (
            patch.object(workflow, "DefaultAzureCredential", return_value=credential),
            patch.object(workflow, "AIProjectClient", return_value=project),
            patch.object(workflow, "FoundryAgent", side_effect=connect) as foundry_agent,
        ):
            run = await workflow.run_case(info, HEADER, "https://offline.test/project")
        self.assertEqual(run["packet"]["case_id"], "S1-offline")
        project.agents.create_version.assert_not_called()
        for call in foundry_agent.call_args_list:
            name = call.kwargs["agent_name"]
            self.assertEqual(call.kwargs["agent_version"], info["agents"][name]["agent_version"])
            self.assertEqual(call.kwargs["default_options"], {"store": False})
        calls = {call.kwargs["agent_name"]: call.kwargs for call in foundry_agent.call_args_list}
        self.assertEqual(
            {tool.__name__ for tool in calls["prompt-marketplace"]["tools"]},
            {"search_plans", "compare_plans", "get_enrollment_window"},
        )
        self.assertEqual(
            {tool.__name__ for tool in calls["prompt-accounts"]["tools"]},
            {"get_hra_account", "get_claim_status", "list_eligible_expenses"},
        )
        for context in contexts:
            context.__aexit__.assert_awaited_once()
        project.__aexit__.assert_awaited_once()
        credential.__aexit__.assert_awaited_once()

    async def test_legacy_workflow_reference_fails_before_cloud_access(self):
        with patch.object(workflow, "DefaultAzureCredential") as credential, self.assertRaisesRegex(ValueError, "legacy"):
            await workflow.run_case({"workflow_name": "old-yaml-workflow"}, HEADER, "https://offline.test")
        credential.assert_not_called()

    async def test_changed_graph_rejects_stale_references_before_cloud_access(self):
        info = {
            "runtime": "microsoft-agent-framework", "graph_sha256": "old-source",
            "roles": {role: f"prompt-{role}" for role in workflow.ROLES},
        }
        with patch.object(workflow, "DefaultAzureCredential") as credential, self.assertRaisesRegex(ValueError, "graph changed"):
            await workflow.run_case(info, HEADER, "https://offline.test")
        credential.assert_not_called()
        info["graph_sha256"] = workflow.SOURCE_SHA256
        with patch.object(Path, "read_bytes", return_value=b"edited after import"), \
                patch.object(workflow, "DefaultAzureCredential") as credential, \
                self.assertRaisesRegex(ValueError, "graph changed"):
            await workflow.run_case(info, HEADER, "https://offline.test")
        credential.assert_not_called()


class DefinitionTests(unittest.TestCase):
    def test_marketplace_case_excludes_unrequested_account_facts(self):
        _, header = prompts.case_header(prompts.S1)
        self.assertIn("routing_hint: marketplace", header)
        self.assertNotIn('"hra_account"', header)
        self.assertNotIn('"claims"', header)
        self.assertIn("hra_account", prompts.gather_facts("P-1001", include_accounts=True))

    def test_wrong_hint_is_preserved_for_the_routing_exercise(self):
        _, header = prompts.case_header({**prompts.S1, "routing_hint": "accounts"})
        self.assertIn("routing_hint: accounts", header)

    def test_prepare_workflow_preserves_prompt_references_without_azure_calls(self):
        info = {"agents": {name: {"agent_version": "3"} for name in prompts.SPECS}}
        with patch.object(prompts.foundry_env, "save_artifact"), patch.object(prompts.foundry_env, "get_project_client") as project:
            prepared = prompts.prepare_workflow(info)
        self.assertEqual(prepared["agents"], info["agents"])
        self.assertEqual(prepared["runtime"], "microsoft-agent-framework")
        self.assertNotIn("workflow_name", prepared)
        project.assert_not_called()

    def test_hosted_tool_registration_accepts_list_item_or_append(self):
        self.assertTrue(prompts.function_tool_is_registered("FUNCTION_TOOLS = [run_triage_workflow]", "run_triage_workflow"))
        self.assertTrue(prompts.function_tool_is_registered("FUNCTION_TOOLS.append(run_triage_workflow)", "run_triage_workflow"))
        self.assertFalse(prompts.function_tool_is_registered("FUNCTION_TOOLS = [other_tool]", "run_triage_workflow"))

    def test_duplicate_or_missing_case_identity_is_rejected(self):
        for header in ("participant_id: P-1001", HEADER + "\ncase_id: other"):
            with self.assertRaises(ValueError):
                workflow.case_from_header(header)

    def test_fenced_packet_is_accepted(self):
        packet = valid_packet()
        self.assertEqual(workflow.extract_packet([f"```json\n{json.dumps(packet)}\n```"]), packet)


class HostedToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_packaged_references_returns_explicit_unavailable(self):
        with patch.object(hosted, "__file__", str(HERE / "missing-package/main.py")), patch.object(hosted, "run_case") as run:
            result = await hosted.run_triage_workflow(HEADER)
        self.assertEqual(result["status"], "unavailable")
        run.assert_not_called()

    async def test_pasted_tool_runs_with_only_flat_package_files(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            text = (HERE / "hosted_tool_snippet.py").read_text()
            block = text.split("# ---- paste from here into hosted/main.py ----\n")[1].split("# ---- paste until here ----")[0]
            main = package / "main.py"
            main.write_text(
                "import json\nimport os\nfrom pathlib import Path\nfrom typing import Annotated\n"
                "from agent_framework import tool\nfrom pydantic import Field\n" + block,
            )
            (package / "triage_agents.json").write_text(json.dumps({"runtime": "microsoft-agent-framework", "roles": {}}))
            spec = importlib.util.spec_from_file_location("flat_maf_main", main)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.object(module, "run_case", new=AsyncMock(return_value={
                "packet": valid_packet(), "actions": [{"action_id": "handoff"}],
            })) as run, patch.dict("os.environ", {"FOUNDRY_PROJECT_ENDPOINT": "https://offline.test"}):
                result = await module.run_triage_workflow(HEADER)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["runtime"], "microsoft-agent-framework")
        run.assert_awaited_once_with(
            {"runtime": "microsoft-agent-framework", "roles": {}}, HEADER, "https://offline.test",
        )

    async def test_runtime_failure_is_not_returned_as_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "triage_agents.json").write_text("{}")
            with patch.object(hosted, "__file__", str(path / "main.py")), \
                    patch.object(hosted, "run_case", new=AsyncMock(side_effect=RuntimeError("agent failed"))), \
                    patch.dict("os.environ", {"FOUNDRY_PROJECT_ENDPOINT": "https://offline.test"}), \
                    self.assertRaisesRegex(RuntimeError, "agent failed"):
                await hosted.run_triage_workflow(HEADER)


if __name__ == "__main__":
    unittest.main()
