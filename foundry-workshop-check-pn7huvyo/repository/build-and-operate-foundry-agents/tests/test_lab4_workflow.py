import importlib.util
import json
from collections.abc import AsyncIterator
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_framework import (
    Agent,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponse,
    AgentResponseUpdate,
    AgentSession,
    Content,
    Executor,
    Message,
    ResponseStream,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

HOSTED = Path(__file__).resolve().parents[1] / "labs/lab4-hosted-multi-agent-handoff/hosted"
sys.path.insert(0, str(HOSTED))
import marketplace_workflow as triage  # noqa: E402
from marketplace_specialists import HandoffPacket, ReviewVerdict  # noqa: E402


def streaming_agent(name: str, replies: list[str]) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.name = name
    agent.create_session.side_effect = AgentSession
    inputs: list[list[Message]] = []
    agent.inputs = inputs
    remaining = iter(replies)

    def run(messages: list[Message], *, stream: bool, **_kwargs: object) -> ResponseStream[AgentResponseUpdate, AgentResponse]:
        if not stream:
            raise AssertionError("This fixture expects streaming agent calls.")
        inputs.append(list(messages))
        text = next(remaining)
        response = AgentResponse(messages=[Message("assistant", contents=[text])])

        async def updates() -> AsyncIterator[AgentResponseUpdate]:
            midpoint = len(text) // 2
            for chunk in (text[:midpoint], text[midpoint:]):
                yield AgentResponseUpdate(role="assistant", contents=[Content.from_text(chunk)])

        return ResponseStream(updates(), finalizer=lambda _: response)

    agent.run.side_effect = run
    return agent


class PacketWriter(Executor):
    def __init__(self, packet: HandoffPacket) -> None:
        super().__init__(id=triage.HANDOFF)
        self.packet = packet
        self.requests: list[AgentExecutorRequest] = []

    @handler
    async def write(self, request: AgentExecutorRequest, ctx: WorkflowContext[AgentExecutorResponse]) -> None:
        self.requests.append(request)
        revised = self.packet.model_copy(update={"summary": "Revised neutral comparison for the advisor."})
        response = AgentResponse(messages=[Message("assistant", contents=[revised.model_dump_json()])])
        await ctx.send_message(AgentExecutorResponse(
            executor_id=self.id,
            agent_response=response,
            full_conversation=[*request.messages, *response.messages],
        ))


class Lab4WorkflowTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("lab4_hosted_import_regression", HOSTED / "main.py")
        assert spec is not None and spec.loader is not None
        cls.hosted_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.hosted_module)

    def setUp(self) -> None:
        self.packet = HandoffPacket(
            case_id="CASE-S3-offline",
            participant_id="P-1005",
            lob="both",
            summary="Neutral plan and HRA information for the advisor.",
            participant_goals=["Understand plan options and HRA coverage"],
            facts_gathered=[],
            options_discussed=[],
            open_questions=[],
            recommended_next_step_for_advisor="Review the options with the participant.",
            compliance_flags=[],
            created_at="2026-10-01T00:00:00+00:00",
        )
        state = triage.CaseState()
        state.reset(triage.CaseIntake(
            self.packet.case_id, self.packet.participant_id, "S3", "Compare ACA plans and my HRA."
        ), "both", {"participant_id": self.packet.participant_id})
        self.coordinator = triage.AdvisorCoordinator(state)
        self.writer = PacketWriter(self.packet)
        self.workflow = (
            WorkflowBuilder(start_executor=self.coordinator, output_from=[self.coordinator])
            .add_edge(self.coordinator, self.writer)
            .add_edge(self.writer, self.coordinator)
            .build()
        )

    async def pending_review(self) -> triage.RunOutcome:
        events = [event async for event in self.workflow.run(
            triage.ApprovedDraft(self.packet.case_id, "both", self.packet.summary, [], 0),
            stream=True,
        )]
        return triage._collect(events)

    def test_response_handler_registers_runtime_types(self) -> None:
        self.assertIn(AgentExecutorRequest, self.coordinator.output_types)
        self.assertIn(dict, self.coordinator.workflow_output_types)
        self.assertTrue(self.coordinator.is_request_supported(triage.AdvisorReviewRequest, str))

    def test_hosted_entry_point_imports_without_starting_server(self) -> None:
        self.assertIsNone(self.hosted_module.SERVICE)

    def test_hosted_agent_builds_with_pinned_sdk(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(self.hosted_module, "ENDPOINT", "https://offline.example.test/api/projects/offline"), \
                patch.object(self.hosted_module, "SESSION_DIR", Path(directory)), \
                patch.object(self.hosted_module, "SERVICE", None), \
                patch.object(self.hosted_module.marketplace_specialists, "KB_MCP_URL", ""):
            agent = self.hosted_module.build_agent()
            self.assertEqual(agent.name, self.hosted_module.AGENT_NAME)
            self.assertEqual(len(self.hosted_module.SERVICE.agents), 4)

    async def test_router_returns_workflow_packet_without_calling_model(self) -> None:
        result = {"status": "approved", "packet": self.packet.model_dump(mode="json")}
        context = MagicMock(messages=[Message("user", contents=["approve"])])
        call_next = AsyncMock()
        with patch.object(self.hosted_module, "handle_turn", new=AsyncMock(return_value=result)):
            await self.hosted_module.triage_router(context, call_next)
        self.assertEqual(json.loads(context.result.text), result)
        call_next.assert_not_awaited()

    async def test_revision_pauses_again_then_approval_yields_full_packet(self) -> None:
        pending = await self.pending_review()
        assert pending.pending_request_id is not None and pending.pending is not None
        self.assertEqual(pending.pending.packet["packet_attempts"], 1)
        self.assertIsNone(pending.output)

        revised = await triage.resume_case(
            self.workflow, pending.pending_request_id, "revise: keep the comparison neutral"
        )
        assert revised.pending_request_id is not None and revised.pending is not None
        self.assertIsNone(revised.output)
        self.assertEqual(revised.pending.packet["packet_attempts"], 2)
        self.assertIn("keep the comparison neutral", self.writer.requests[-1].messages[0].text)

        approved = await triage.resume_case(self.workflow, revised.pending_request_id, "approve")
        assert approved.output is not None
        self.assertIsNone(approved.pending)
        self.assertEqual(approved.output["status"], "approved")
        self.assertEqual(approved.output["advisor_decision"], "approve")
        self.assertEqual(approved.output["packet_attempts"], 2)
        HandoffPacket.model_validate(approved.output)
        self.assertEqual(len(self.writer.requests), 2)

    async def test_decline_yields_full_packet_without_revision(self) -> None:
        pending = await self.pending_review()
        assert pending.pending_request_id is not None
        declined = await triage.resume_case(
            self.workflow, pending.pending_request_id, "decline: verify eligibility first"
        )
        assert declined.output is not None
        self.assertIsNone(declined.pending)
        self.assertEqual(declined.output["status"], "declined")
        self.assertEqual(declined.output["advisor_decision"], "decline")
        self.assertEqual(declined.output["advisor_note"], "verify eligibility first")
        self.assertEqual(declined.output["packet_attempts"], 1)
        HandoffPacket.model_validate(declined.output)
        self.assertEqual(len(self.writer.requests), 1)

    async def test_full_streaming_service_pauses_revises_and_finishes(self) -> None:
        flagged = ReviewVerdict(
            compliant=False, violations=["Explain the IEP timing"], offending_section=triage.MARKETPLACE,
            guidance="Add neutral initial enrollment education.",
        )
        clean = ReviewVerdict(compliant=True, violations=[], offending_section="none", guidance="none")
        revised_packet = self.packet.model_copy(update={"open_questions": ["When does your IEP begin?"]})
        for decision, status in (("approve", "approved"), ("decline", "declined")):
            with self.subTest(decision=decision):
                agents = {
                    triage.MARKETPLACE: streaming_agent(triage.MARKETPLACE, [
                        "Neutral ACA options. [KB-MKT-001]", "Neutral ACA and IEP education. [KB-MKT-001]",
                    ]),
                    triage.ACCOUNTS: streaming_agent(triage.ACCOUNTS, ["HRA facts. [KB-ACC-001]"]),
                    triage.REVIEWER: streaming_agent(triage.REVIEWER, [
                        flagged.model_dump_json(), clean.model_dump_json(),
                    ]),
                    triage.HANDOFF: streaming_agent(triage.HANDOFF, [
                        self.packet.model_dump_json(), revised_packet.model_dump_json(),
                    ]),
                }
                with tempfile.TemporaryDirectory() as directory, \
                        patch.object(self.hosted_module, "SESSION_DIR", Path(directory)), \
                        patch.object(self.hosted_module.marketplace_specialists, "build_all", return_value=agents), \
                        patch.object(triage, "_collect", wraps=triage._collect) as collect:
                    service = self.hosted_module.TriageService(MagicMock())
                    pending = await service.start("offline", "P-1005", "Compare ACA plans and my HRA.", "S3")
                    self.assertEqual(pending["status"], self.hosted_module.PENDING)
                    self.assertEqual(pending["packet_attempts"], 1)
                    self.assertIn("offline", service.paused)
                    events = collect.call_args.args[0]
                    self.assertFalse(any(event.type == "output" for event in events))
                    self.assertTrue(any(
                        event.type == "intermediate" and isinstance(event.data, AgentResponseUpdate)
                        for event in events
                    ))

                    revised = await service.decide("offline", "revise: add an IEP timing question")
                    self.assertEqual(revised["status"], self.hosted_module.PENDING)
                    self.assertGreaterEqual(revised["packet_attempts"], 2)
                    self.assertTrue(any("IEP" in question.upper() for question in revised["packet"]["open_questions"]))
                    self.assertFalse(any(event.type == "output" for event in collect.call_args.args[0]))

                    final = await service.decide("offline", decision)
                    self.assertEqual(final["status"], status)
                    self.assertEqual(final["packet"]["advisor_decision"], decision)
                    self.assertEqual(final["packet"]["packet_attempts"], 2)
                    HandoffPacket.model_validate(final["packet"])
                    outputs = [event.data for event in collect.call_args.args[0] if event.type == "output"]
                    self.assertEqual(outputs, [final["packet"]])
                    self.assertNotIn("offline", service.paused)
                    self.assertEqual(agents[triage.MARKETPLACE].run.call_count, 2)
                    self.assertEqual(agents[triage.ACCOUNTS].run.call_count, 1)
                    self.assertEqual(agents[triage.REVIEWER].run.call_count, 2)
                    self.assertEqual(agents[triage.HANDOFF].run.call_count, 2)
                    self.assertIn("IEP", agents[triage.HANDOFF].inputs[-1][0].text)


if __name__ == "__main__":
    unittest.main()
