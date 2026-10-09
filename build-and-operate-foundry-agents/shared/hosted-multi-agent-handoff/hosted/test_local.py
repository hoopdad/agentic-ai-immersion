"""Smoke test for healthcare-marketplace-triage-hosted (Labs 7-8).

    python test_local.py                         three turns against the local server: S3, revise, then approve
    python test_local.py --base http://host:8088 another local or tunneled host
    python test_local.py --direct                no HTTP: import main.py and run the case in-process (needs .env)
    python test_local.py --deployed              the version deployed with azd, by name from 3-day-labs/artifacts/lab4/hosted.json
    python test_local.py --offline               no model, no server: checks the pure parts (classifier, decision parsing)
Exit code 0 when packet routing, advisor decisions, compliance fields and safety checks pass; 1 otherwise.
Labs 9-10's pipeline runs this after a deployment.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE.parents[2] if len(HERE.parents) > 2 else HERE, HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import guardrails, model_resilience  # noqa: E402

AGENT_NAME = "healthcare-marketplace-triage-hosted"
HOSTED_RECORD = HERE.parents[2] / "3-day-labs" / "artifacts" / "lab4" / "hosted.json"
CASE = {"participant_id": "P-1003", "scenario": "S2",
        "message": "My claim CLM-9003 was denied and I do not understand why. What do I need to send to get it paid?"}
LIVE_CASE = {
    "participant_id": "P-1005",
    "scenario": "S3",
    "expected_lob": "both",
    "message": (
        "I have my sponsor's HRA and I need an ACA plan for next year. What is my HRA balance, "
        "what ACA plans are there in my county, and what happens when I turn 65 next year? "
        "Which one should I pick?"
    ),
}


def output_text(payload: dict) -> str:
    if payload.get("output_text"):
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts)


def parse_reply(text: str) -> dict:
    text = (text or "").strip()
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1]):
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return {"status": "unparsed", "raw": text}


def call_local(base: str, text: str, previous_response_id: str | None = None) -> tuple[dict, str | None]:
    import httpx

    # VERIFY: POST /responses body shape and previous_response_id handling (same note as Labs 3-4 test_local.py)
    body: dict = {"input": text, "stream": False}
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    response = httpx.post(f"{base.rstrip('/')}/responses", json=body, timeout=300.0)
    response.raise_for_status()
    payload = response.json()
    model_resilience.ensure_response_succeeded(payload, "hosted-test")
    return parse_reply(output_text(payload)), payload.get("id")


def call_deployed(agent_name: str, text: str, previous_response_id: str | None = None) -> tuple[dict, str | None]:
    from common import foundry_env

    client = foundry_env.get_openai_client(agent_name=agent_name)
    kwargs = {"previous_response_id": previous_response_id} if previous_response_id else {}
    response = client.responses.create(input=text, **kwargs)
    return parse_reply(response.output_text), getattr(response, "id", None)


def check_packet(packet: dict, *, expected_lob: str, decision: str | None = None) -> bool:
    required = {
        "case_id", "participant_id", "lob", "summary", "participant_goals", "facts_gathered",
        "options_discussed", "open_questions", "recommended_next_step_for_advisor",
        "compliance_flags", "created_at", "packet_attempts",
    }
    missing = sorted(required - packet.keys())
    participant_text = " ".join(packet.get("options_discussed", []) + [packet.get("summary", "")])
    serialized = json.dumps(packet, default=str)
    recommends = guardrails.contains_recommendation(participant_text)
    leaks = guardrails.redact_pii(serialized) != serialized
    citations_ok = all(
        isinstance(fact, dict) and str(fact.get("fact", "")).strip() and str(fact.get("source", "")).strip()
        for fact in packet.get("facts_gathered", [])
    )
    decision_ok = True
    if decision is not None:
        expected_status = "approved" if decision == "approve" else "declined"
        decision_ok = packet.get("advisor_decision") == decision and packet.get("status") == expected_status
    ok = (
        not missing
        and packet.get("lob") == expected_lob
        and isinstance(packet.get("compliance_flags"), list)
        and not recommends
        and not leaks
        and citations_ok
        and decision_ok
    )
    print(
        f"[triage-test] packet missing={missing} lob={packet.get('lob')} recommendation={recommends} "
        f"pii={leaks} citations={citations_ok} decision={packet.get('advisor_decision')} "
        f"flags={packet.get('compliance_flags')}"
    )
    return ok


def offline_checks() -> bool:
    from marketplace_workflow import classify_lob, finalize_packet, minimized_profile, parse_decision
    from marketplace_specialists import HandoffPacket, LobCall, ReviewVerdict, parse_structured

    checks = {
        "classify accounts": classify_lob(CASE["message"]) == "accounts",
        "classify marketplace": classify_lob("Compare ACA plans in my county.") == "marketplace",
        "classify both": classify_lob("Which ACA plan is in my county and what is my HRA balance?") == "both",
        "keyword ambiguity documented": classify_lob(
            "My card was declined when I tried to pay for a prescription."
        ) == "both",
        "parse revise": parse_decision("revise: add the IEP dates") == ("revise", "add the IEP dates"),
        "parse approve": parse_decision("APPROVE") == ("approve", ""),
        "invalid decision is guarded revision": parse_decision("maybe") == ("revise", "maybe"),
        "decline status": finalize_packet({"case_id": "x"}, "decline", "duplicate")["status"] == "declined",
        "approve status": finalize_packet({"case_id": "x"}, "approve", "")["status"] == "approved",
        "recommendation detected": guardrails.contains_recommendation("You should choose the Contoso HMO."),
        "neutral comparison allowed": not guardrails.contains_recommendation("The Contoso HMO has a $0 premium."),
        "pii detected": guardrails.redact_pii("email me at learner@example.com") != "email me at learner@example.com",
        "profile minimizes pii": "date_of_birth" not in minimized_profile(
            {"participant_id": "P-1", "date_of_birth": "1960-01-01", "preferences": {}}
        ),
    }
    verdict = ReviewVerdict(
        compliant=False,
        violations=["recommendation"],
        offending_section="marketplace-guide",
        guidance="remove the recommendation",
    )
    checks["review verdict round trip"] = (
        parse_structured(verdict.model_dump_json(), None, ReviewVerdict) == verdict
    )
    lob_call = LobCall(lob="accounts", reason="The debit card payment failed.")
    checks["classifier output round trip"] = (
        parse_structured(lob_call.model_dump_json(), None, LobCall) == lob_call
    )
    packet = HandoffPacket(
        case_id="CASE-offline",
        participant_id="P-1005",
        lob="both",
        summary="The participant asked for a neutral plan comparison and HRA facts.",
        participant_goals=["compare options"],
        facts_gathered=[{"fact": "The account has a balance.", "source": "get_hra_account"}],
        options_discussed=["The ACA Silver option has the listed premium."],
        open_questions=["Which enrollment window applies?"],
        recommended_next_step_for_advisor="Review the neutral comparison with the participant.",
        compliance_flags=[],
        created_at="2026-09-30T12:00:00+00:00",
    ).model_dump(mode="json")
    packet["packet_attempts"] = 1
    checks["safe packet contract"] = check_packet(packet, expected_lob="both")

    for name, passed in checks.items():
        print(f"[triage-test] offline {name}: {'ok' if passed else 'FAIL'}")
    return all(checks.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8088")
    parser.add_argument("--deployed", action="store_true")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.offline:
        ok = offline_checks()
        print(f"[triage-test] {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    session_id = f"test-{uuid.uuid4().hex[:8]}"
    if args.direct:
        import main as hosted_main

        result = hosted_main.run_case_direct_sync(
            session_id,
            LIVE_CASE["participant_id"],
            LIVE_CASE["message"],
            ["revise: add the IEP dates to open_questions", "approve"],
        )
        packet = result.get("packet", {})
        ok = (
            result.get("status") == "approved"
            and packet.get("packet_attempts", 0) >= 2
            and check_packet(packet, expected_lob=LIVE_CASE["expected_lob"], decision="approve")
        )
        print(f"[triage-test] direct result: {result.get('status')}\n[triage-test] {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    agent_name = AGENT_NAME
    if args.deployed and HOSTED_RECORD.exists():
        agent_name = json.loads(HOSTED_RECORD.read_text(encoding="utf-8")).get("agent_name", agent_name)
    call = (lambda text, prev=None: call_deployed(agent_name, text, prev)) if args.deployed else (lambda text, prev=None: call_local(args.base, text, prev))

    envelope = json.dumps({"session_id": session_id, **LIVE_CASE})
    print(f"[triage-test] turn 1 (case)> {envelope}")
    reply, response_id = call(envelope)
    print(f"[triage-test] status={reply.get('status')} case={reply.get('case_id')} attempts={reply.get('packet_attempts')}")
    first_packet = reply.get("packet", {})
    ok = (
        reply.get("status") == "pending_advisor_approval"
        and first_packet.get("packet_attempts") == 1
        and check_packet(first_packet, expected_lob=LIVE_CASE["expected_lob"])
    )

    decision = json.dumps({"session_id": session_id, "advisor": "revise: add the IEP dates to open_questions"})
    print(f"[triage-test] turn 2 (advisor)> {decision}")
    reply, response_id = call(decision, response_id)
    print(f"[triage-test] status={reply.get('status')} attempts={reply.get('packet_attempts')} resume_path={reply.get('resume_path')}")
    revised_packet = reply.get("packet", {})
    ok = (
        ok
        and reply.get("status") == "pending_advisor_approval"
        and revised_packet.get("packet_attempts", 0) >= 2
        and check_packet(revised_packet, expected_lob=LIVE_CASE["expected_lob"])
    )

    decision = json.dumps({"session_id": session_id, "advisor": "approve"})
    print(f"[triage-test] turn 3 (advisor)> {decision}")
    reply, _ = call(decision, response_id)
    print(f"[triage-test] status={reply.get('status')} resume_path={reply.get('resume_path')}")
    ok = (
        ok
        and reply.get("status") == "approved"
        and check_packet(reply.get("packet", {}), expected_lob=LIVE_CASE["expected_lob"], decision="approve")
    )
    print(f"[triage-test] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
