"""Independent concierge candidate: reuse the accepted knowledge product, add one delegation boundary."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextvars import ContextVar
from functools import partial
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from delegation import delegate_pending, validate_request, validate_target
from agent_framework import Agent, AgentContext, AgentMiddleware, AgentResponse, AgentResponseUpdate, Content, Message, ResponseStream, tool
from agent_framework_foundry_hosting import ResponsesHostServer
from opentelemetry import context as otel_context, propagate, trace

BOUND_REQUEST: ContextVar[str | None] = ContextVar("pending_case_request", default=None)


def target_from_environment() -> dict:
    return validate_target(json.loads(os.environ["MARKETPLACE_TRIAGE_REFERENCE"]))


async def delegate_request(request_json: str) -> dict:
    """Execute only a validated explicit envelope; this helper is not a model tool."""
    request = validate_request(json.loads(request_json))
    parent = propagate.extract({"traceparent": request["traceparent"]})
    token = otel_context.attach(parent)
    try:
        with trace.get_tracer(__name__).start_as_current_span("hosted.pending_case.delegate") as span:
            span.set_attribute("workshop.case_id", request["case_id"])
            span.set_attribute("workshop.session_id", request["session_id"])
            carrier = {}
            propagate.inject(carrier)
            outbound = {**request, "traceparent": carrier.get("traceparent", request["traceparent"])}
            result = await delegate_pending(
                target_from_environment(), outbound,
                timeout=float(os.environ.get("MARKETPLACE_DELEGATION_TIMEOUT", "90")),
            )
            return {**result, "remote_traceparent": result["traceparent"], "traceparent": request["traceparent"]}
    finally:
        otel_context.detach(token)


async def delegate_bound_request() -> dict:
    """Relay the application-bound envelope without accepting model-generated arguments."""
    request_json = BOUND_REQUEST.get()
    if request_json is None:
        raise RuntimeError("Delegation requires an explicit pending_case envelope; the model cannot invent a case or session.")
    return await delegate_request(request_json)


delegate_triage = tool(approval_mode="never_require")(delegate_bound_request)


class DelegationBoundary(AgentMiddleware):
    """Explicit machine envelopes bypass model paraphrasing; ordinary knowledge turns keep the core agent."""

    async def process(self, context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        text = context.messages[-1].text if context.messages else ""
        if not text.lstrip().startswith("{"):
            await call_next()
            return
        request = json.loads(text)
        if not isinstance(request, dict) or "operation" not in request:
            await call_next()
            return
        validate_request(request)
        token = BOUND_REQUEST.set(text)
        try:
            result = await delegate_bound_request()
        finally:
            BOUND_REQUEST.reset(token)
        result["caller_version"] = os.environ.get("FOUNDRY_AGENT_VERSION", "")
        output = json.dumps(result)
        response = AgentResponse(messages=[Message(role="assistant", contents=[Content.from_text(output)])])
        if context.stream:
            async def updates() -> AsyncIterator[AgentResponseUpdate]:
                yield AgentResponseUpdate(contents=[Content.from_text(output)], role="assistant")
            context.result = ResponseStream(updates(), finalizer=lambda _: response)
        else:
            context.result = response


def build_agent() -> Agent:
    import core_product

    core_product.FUNCTION_TOOLS = [*core_product.FUNCTION_TOOLS, delegate_triage]
    core_product.ROLE_INSTRUCTIONS += "\nOnly delegate explicit pending_case envelopes; never decide, resume or replay an advisor case.\n"
    core_product.AGENT_NAME = os.environ["MARKETPLACE_DELEGATION_AGENT_NAME"]
    core_product.Agent = partial(Agent, middleware=[DelegationBoundary()])
    return core_product.build_agent()


if __name__ == "__main__":
    import core_product

    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or not core_product.configure_tracing():
        raise RuntimeError("Lab 12 requires configured telemetry; do not run without correlated traces.")
    ResponsesHostServer(build_agent()).run()
