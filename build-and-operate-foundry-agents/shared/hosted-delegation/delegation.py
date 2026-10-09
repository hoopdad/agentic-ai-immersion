"""One-shot authenticated remote pending-case delegation; never replay a request automatically."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import quote, urlsplit

MAX_TIMEOUT = 120
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
TRACE_PATTERN = re.compile(r"00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]")


def validate_target(target: dict) -> dict:
    required = ("agent_name", "version", "project_endpoint", "protocol_endpoint")
    if any(not isinstance(target.get(key), str) or not target[key].strip() for key in required):
        raise ValueError("Lab 8 must publish a populated triage_reference with version and endpoint.")
    parsed = urlsplit(target["project_endpoint"])
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment \
            or parsed.username or parsed.password:
        raise ValueError("Use a non-secret HTTPS Foundry project endpoint.")
    expected = target["project_endpoint"].rstrip("/") + "/agents/" + quote(target["agent_name"], safe="") + "/endpoint/protocols/openai"
    if target["protocol_endpoint"].rstrip("/") != expected:
        raise ValueError("Lab 8 protocol endpoint does not match its project and agent name.")
    if "pending_advisor_approval" not in target.get("capabilities", []):
        raise ValueError("Lab 8 must demonstrate pending_advisor_approval.")
    return dict(target)


def validate_request(request: dict) -> dict:
    allowed = {"operation", "case_id", "session_id", "participant_id", "message", "traceparent"}
    if set(request) - allowed or request.get("operation") != "pending_case":
        raise ValueError("Only a one-shot pending_case is allowed; never forward an advisor decision.")
    for key in ("case_id", "session_id", "participant_id"):
        if not isinstance(request.get(key), str) or not ID_PATTERN.fullmatch(request[key]):
            raise ValueError(f"Provide an explicit safe {key}.")
    if not isinstance(request.get("message"), str) or not 1 <= len(request["message"]) <= 4000:
        raise ValueError("Provide a bounded participant message.")
    traceparent = request.get("traceparent", "")
    if not TRACE_PATTERN.fullmatch(traceparent) or traceparent.split("-")[1] == "0" * 32 \
            or traceparent.split("-")[2] == "0" * 16:
        raise ValueError("Provide a valid nonzero W3C traceparent.")
    return dict(request)


def require_pinned_selector(details: Any, version: str) -> None:
    """Name endpoints are safe only while their server-side selector pins the accepted version."""
    endpoint = details.agent_endpoint
    if endpoint is None or endpoint.version_selector is None:
        raise RuntimeError("Endpoint has no pinned selector; explicitly pin the accepted version before Lab 12.")
    rules = endpoint.version_selector.version_selection_rules or []
    if len(rules) != 1 or rules[0].type != "FixedRatio" \
            or str(rules[0].agent_version) != version or rules[0].traffic_percentage != 100:
        raise RuntimeError("Endpoint is not pinned to the Lab 8 version; explicitly pin it before Lab 12.")


def validate_pending(payload: dict, request: dict, target: dict) -> dict:
    if payload.get("status") != "pending_advisor_approval" or payload.get("advisor_decision"):
        raise RuntimeError("Remote service did not return pending advisor approval; never manufacture approval.")
    packet = payload.get("packet")
    if not isinstance(packet, dict) or packet.get("case_id") != request["case_id"] or packet.get("advisor_decision"):
        raise RuntimeError("Remote pending packet is missing, mismatched or already decided.")
    for key in ("case_id", "session_id", "participant_id", "traceparent"):
        if payload.get(key) != request[key]:
            raise RuntimeError(f"Remote {key} does not match this delegated request.")
    if str(payload.get("deployed_version")) != target["version"]:
        raise RuntimeError("Remote version changed; rerun Lab 8 and the affected Lab 12 gates.")
    if payload.get("trace_id") != request["traceparent"].split("-")[1]:
        raise RuntimeError("Remote trace does not match the delegated W3C trace context.")
    return payload


async def invoke_pending(client: Any, target: dict, request: dict, *, timeout: float = 90) -> dict:
    """Bound the complete turn; transport errors remain visible and automatic retries are disabled."""
    target, request = validate_target(target), validate_request(request)
    if not 0 < timeout <= MAX_TIMEOUT:
        raise ValueError(f"Timeout must be in (0, {MAX_TIMEOUT}] seconds.")
    async with asyncio.timeout(timeout):
        response = await client.with_options(max_retries=0, timeout=timeout).responses.create(
            input=json.dumps(request), store=False,
            extra_headers={"traceparent": request["traceparent"]},
        )
    if response.status != "completed":
        raise RuntimeError(f"Delegation Responses failed: {response.status}; inspect before any deliberate retry.")
    payload = json.loads(response.output_text)
    if not isinstance(payload, dict):
        raise RuntimeError("Remote pending-case response must be a JSON object.")
    return validate_pending(payload, request, target)


async def delegate_pending(target: dict, request: dict, *, timeout: float = 90) -> dict:
    """Use the hosted caller's managed identity (local developer identity only in notebook checks)."""
    from azure.ai.projects.aio import AIProjectClient
    from azure.identity.aio import DefaultAzureCredential

    target, request = validate_target(target), validate_request(request)
    if not 0 < timeout <= MAX_TIMEOUT:
        raise ValueError(f"Timeout must be in (0, {MAX_TIMEOUT}] seconds.")
    async with asyncio.timeout(timeout):
        async with DefaultAzureCredential() as credential, AIProjectClient(
            endpoint=target["project_endpoint"], credential=credential, allow_preview=True,
        ) as project:
            details = await project.agents.get(target["agent_name"])
            require_pinned_selector(details, target["version"])
            async with project.get_openai_client(agent_name=target["agent_name"], max_retries=0, timeout=timeout) as client:
                result = await invoke_pending(client, target, request, timeout=timeout)
            require_pinned_selector(await project.agents.get(target["agent_name"]), target["version"])
            return result
