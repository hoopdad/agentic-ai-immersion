from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


stretch5 = load_module("stretch5_prompt_agents_offline", "stretch5_prompt_agents.py")
hosted = load_module("hosted_tool_snippet_offline", "hosted_tool_snippet.py")


def valid_packet(**overrides):
    packet = {
        "case_id": "S1-20260930-P-1001",
        "participant_id": "P-1001",
        "lob": "marketplace",
        "summary": "The participant wants neutral plan education and enrollment timing.",
        "participant_goals": ["Compare plan costs neutrally."],
        "facts_gathered": [{"fact": "AEP applies.", "source": "get_enrollment_window"}],
        "options_discussed": ["ACA Silver and ACA Gold features"],
        "open_questions": ["Confirm the cardiologist network with the carrier."],
        "recommended_next_step_for_advisor": "Review the neutral comparison with the participant.",
        "compliance_flags": [],
        "created_at": "2026-09-30T12:00:00+00:00",
    }
    packet.update(overrides)
    return packet


class WorkflowRenderingTests(unittest.TestCase):
    def test_rendered_workflow_has_expected_agents_and_order(self):
        text = stretch5.render_workflow()
        parsed = stretch5.parse_workflow(text)
        actions = parsed["trigger"]["actions"]
        ids = [action["id"] for action in actions]
        self.assertLess(ids.index("triage"), ids.index("route_marketplace"))
        self.assertLess(ids.index("route_marketplace"), ids.index("compliance"))
        self.assertLess(ids.index("compliance"), ids.index("handoff"))
        self.assertIn(f"name: {stretch5.MARKETPLACE}", text)
        self.assertNotIn("{marketplace}", text)

    def test_notebook_publishes_agents_before_first_exercise(self):
        source = (HERE / "stretch5_prompt_agents.py").read_text(encoding="utf-8")
        first_exercise = source.index("## YOUR TURN")
        publish_cell = source.index('if "__file__" not in globals():\n    _info = build()\n    demo(_info)')
        self.assertLess(publish_cell, first_exercise)

    def test_marketplace_case_does_not_include_unrequested_account_facts(self):
        _case_id, header = stretch5.case_header(stretch5.S1)
        self.assertIn("routing_hint: marketplace", header)
        self.assertNotIn('"hra_account"', header)
        self.assertNotIn('"claims"', header)

    def test_account_case_includes_requested_account_facts(self):
        facts = stretch5.gather_facts("P-1001", include_accounts=True)
        self.assertIn("hra_account", facts)
        self.assertIn("claims", facts)

    def test_broken_router_scenario_overrides_the_routing_hint(self):
        _case_id, header = stretch5.case_header({**stretch5.S1, "routing_hint": "accounts"})
        self.assertIn("routing_hint: accounts", header)
        self.assertNotIn("routing_hint: marketplace", header)

    def test_hosted_tool_registration_accepts_list_item_or_append(self):
        in_list = "FUNCTION_TOOLS = [first_tool, run_triage_workflow]"
        appended = "FUNCTION_TOOLS = [first_tool]\nFUNCTION_TOOLS.append(run_triage_workflow)"
        missing = "FUNCTION_TOOLS = [first_tool]"
        self.assertTrue(stretch5.function_tool_is_registered(in_list, "run_triage_workflow"))
        self.assertTrue(stretch5.function_tool_is_registered(appended, "run_triage_workflow"))
        self.assertFalse(stretch5.function_tool_is_registered(missing, "run_triage_workflow"))


class PacketTests(unittest.TestCase):
    def test_extracts_fenced_packet_from_last_message(self):
        packet = valid_packet()
        messages = ["not JSON", f"```json\n{json.dumps(packet)}\n```"]
        self.assertEqual(stretch5.extract_packet(messages), packet)
        self.assertEqual(hosted._extract_packet(messages[-1]), packet)

    def test_validation_rejects_structure_safety_and_stable_field_changes(self):
        packet = valid_packet(
            participant_id="P-9999",
            facts_gathered=[{"fact": "Call 801-555-0100", "source": "participant statement", "extra": "no"}],
            options_discussed="Plan A",
            unexpected=True,
        )
        problems = stretch5.validate_packet(packet, expected={"participant_id": "P-1001", "lob": "marketplace"})
        self.assertTrue(any("unexpected fields" in problem for problem in problems))
        self.assertTrue(any("options_discussed must be a list" in problem for problem in problems))
        self.assertTrue(any("facts_gathered[0]" in problem for problem in problems))
        self.assertTrue(any("PII pattern" in problem for problem in problems))
        self.assertTrue(any("participant_id must remain" in problem for problem in problems))


class ReferenceLoadingTests(unittest.TestCase):
    def test_environment_reference_wins(self):
        reference = hosted.load_workflow_reference(
            {"MARKETPLACE_WORKFLOW_AGENT_NAME": "env-workflow", "MARKETPLACE_WORKFLOW_AGENT_VERSION": "7"},
            [],
        )
        self.assertEqual(reference["workflow_name"], "env-workflow")
        self.assertEqual(reference["source"], "environment")

    def test_invalid_file_is_skipped_before_valid_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid = Path(temp) / "invalid.json"
            valid = Path(temp) / "agents.json"
            invalid.write_text("{", encoding="utf-8")
            valid.write_text(json.dumps({"workflow_name": "artifact-workflow", "workflow_version": "3"}), encoding="utf-8")
            reference = hosted.load_workflow_reference({}, [invalid, valid])
        self.assertEqual(reference["workflow_name"], "artifact-workflow")
        self.assertEqual(reference["workflow_version"], "3")


class HostedUnavailableTests(unittest.TestCase):
    def test_unavailable_reference_returns_explicit_status_without_client_call(self):
        with patch.object(hosted, "WORKFLOW", None), patch.object(hosted, "openai_client") as client:
            result = hosted.run_triage_workflow("case")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("not available", result["error"])
        client.assert_not_called()


class OrderingTests(unittest.TestCase):
    class Item:
        def __init__(self, item_type, **data):
            self.type = item_type
            self._data = {"type": item_type, **data}
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self):
            return self._data

    def test_mocked_stream_deduplicates_actions_and_validates_order(self):
        events = []
        for action_id in stretch5.EXPECTED_S1_ACTIONS:
            item = self.Item("workflow_action", action_id=action_id, kind="InvokeAzureAgent", status="in_progress")
            events.append(SimpleNamespace(type="response.output_item.added", item=item))
            done = self.Item("workflow_action", action_id=action_id, kind="InvokeAzureAgent", status="completed")
            events.append(SimpleNamespace(type="response.output_item.done", item=done))
        packet = valid_packet()
        message = self.Item("message", content=[SimpleNamespace(text=json.dumps(packet))])
        events.append(SimpleNamespace(type="response.output_item.done", item=message))
        conversations = SimpleNamespace(
            create=lambda: SimpleNamespace(id="conversation-1"),
            delete=lambda **_kwargs: None,
        )
        responses = SimpleNamespace(create=lambda **_kwargs: iter(events))
        run = stretch5.run_case(SimpleNamespace(conversations=conversations, responses=responses), "workflow", "header")
        self.assertEqual([action["action_id"] for action in run["actions"]], list(stretch5.EXPECTED_S1_ACTIONS))
        self.assertEqual(stretch5.validate_action_order(run["actions"], stretch5.EXPECTED_S1_ACTIONS), [])
        self.assertEqual(run["errors"], [])

    def test_ordering_reports_missing_and_forbidden_actions(self):
        actions = [{"action_id": "triage"}, {"action_id": "accounts"}, {"action_id": "handoff"}]
        problems = stretch5.validate_action_order(actions, stretch5.EXPECTED_S1_ACTIONS, forbidden=("accounts",))
        self.assertTrue(any("marketplace" in problem for problem in problems))
        self.assertTrue(any("unexpected workflow action accounts" in problem for problem in problems))

    def test_demo_raises_when_workflow_reports_an_error(self):
        info = {"workflow_name": "workflow", "workflow_version": "1"}
        failed_run = {"conversation_id": "conversation-1", "actions": [], "messages": [], "errors": ["workflow failed"]}
        with (
            patch.object(stretch5.foundry_env, "get_openai_client", return_value=object()),
            patch.object(stretch5, "case_header", return_value=("S1-20260930-P-1001", "header")),
            patch.object(stretch5, "run_case", return_value=failed_run),
            patch.object(stretch5.helpers, "artifact_path", return_value=Path("agents.json")),
            patch.object(stretch5.foundry_env, "save_artifact"),
            self.assertRaisesRegex(RuntimeError, "workflow failed"),
        ):
            stretch5.demo(info)


if __name__ == "__main__":
    unittest.main()
