"""Smoke test for healthcare-marketplace-claims-review-invocations (Labs 13-14).

    python test_local.py                    POST one batch to the local InvocationsHostServer (http://localhost:8088)
    python test_local.py --base http://host:8088
    python test_local.py --offline          no server, no model: run claims_review directly and check the packets
Exit code 0 when every claim and deterministic field matches claims_review.py, the denied claim has the complete
KB document list, and no PII or recommendation language leaked; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE.parents[2] if len(HERE.parents) > 2 else HERE, HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import guardrails  # noqa: E402

from claims_review import review_claims  # noqa: E402

CLAIM_IDS = ["CLM-9003", "CLM-9021", "CLM-9001"]
FACT_FIELDS = (
    "claim_id", "participant_id", "hra_account_id", "status", "type", "amount", "submitted",
    "denial_reason_code", "denial_reason_text", "kb_rule", "fix_available", "accepted_proof_of_payment",
    "not_accepted_as_proof", "resubmission_steps", "advisor_action_required", "knowledge_ref", "review",
)


def invocations_path() -> str:
    """Installed azure-ai-agentserver exposes POST /invocations; allow an explicit reverse-proxy override."""
    path = os.environ.get("MARKETPLACE_INVOCATIONS_PATH", "/invocations").strip()
    if not path.startswith("/") or "?" in path or "#" in path:
        raise SystemExit("[invocations-test] MARKETPLACE_INVOCATIONS_PATH must be an absolute URL path")
    return path


def extract_reviews(payload) -> list[dict]:
    """Extract ClaimReviewBatch from the installed host's plain text or a documented wrapper."""
    if isinstance(payload, dict) and isinstance(payload.get("reviews"), list):
        return payload["reviews"]
    if isinstance(payload, dict):
        for key in ("response", "output_text", "text", "output", "message"):
            if key in payload:
                return extract_reviews(payload[key])
        raise ValueError(f"unsupported invocations response object keys: {sorted(payload)}")
    if isinstance(payload, list):
        for item in payload:
            try:
                return extract_reviews(item)
            except ValueError:
                continue
        raise ValueError("invocations response list did not contain a ClaimReviewBatch")
    if not isinstance(payload, str):
        raise ValueError(f"unsupported invocations response type: {type(payload).__name__}")
    text = payload.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    decoder = json.JSONDecoder()
    candidates = [text]
    candidates.extend(text[index:] for index, char in enumerate(text) if char in "[{")
    for candidate in candidates:
        try:
            data, _ = decoder.raw_decode(candidate)
        except ValueError:
            continue
        try:
            return extract_reviews(data)
        except ValueError:
            continue
    raise ValueError(f"invocations response did not contain a ClaimReviewBatch: {text[:240]!r}")


def call_local(base: str, claim_ids: list[str]) -> list[dict]:
    import httpx

    body = {"message": json.dumps({"claim_ids": claim_ids})}
    path = invocations_path()
    response = httpx.post(f"{base.rstrip('/')}{path}", json=body, timeout=180.0)
    response.raise_for_status()
    print(f"[invocations-test] served at {path}")
    payload = response.json() if "application/json" in response.headers.get("content-type", "") else response.text
    return extract_reviews(payload)


def check(reviews: list[dict], claim_ids: list[str]) -> bool:
    from claims_review import hra_rules

    expected = {review["claim_id"]: review for review in review_claims(claim_ids)}
    by_id = {review.get("claim_id"): review for review in reviews}
    failures = []
    if set(by_id) != set(expected):
        failures.append(f"claim ids expected {sorted(expected)}, got {sorted(by_id)}")
    for claim_id, expected_review in expected.items():
        actual = by_id.get(claim_id, {})
        for field in FACT_FIELDS:
            if actual.get(field) != expected_review.get(field):
                failures.append(f"{claim_id}.{field} expected {expected_review.get(field)!r}, got {actual.get(field)!r}")
    denied = by_id.get("CLM-9003", {})
    if denied.get("accepted_proof_of_payment") != hra_rules()["proof_of_payment"]:
        failures.append("CLM-9003 did not copy the complete KB-ACC-001 proof-of-payment list")
    text = json.dumps(reviews)
    leaks = guardrails.redact_pii(text) != text
    recommends = guardrails.contains_recommendation(text)
    if leaks:
        failures.append("PII leak detected")
    if recommends:
        failures.append("recommendation language detected")
    for review in reviews:
        explanation = str(review.get("participant_explanation") or "").strip()
        if explanation:
            print(f"[invocations-test] {review['claim_id']}> {explanation}")
            if "[KB-ACC-001]" not in explanation:
                failures.append(f"{review.get('claim_id')} explanation does not cite [KB-ACC-001]")
            if guardrails.contains_payment_promise(explanation):
                failures.append(f"{review.get('claim_id')} explanation promises an outcome: {explanation!r}")
    print(f"[invocations-test] claims back: {sorted(by_id)}  exact facts: {not failures}  pii leak: {leaks}  recommendation: {recommends}")
    for failure in failures:
        print(f"[invocations-test] FAIL: {failure}")
    return not failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8088")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        reviews = review_claims(CLAIM_IDS) if args.offline else call_local(args.base, CLAIM_IDS)
        ok = check(reviews, CLAIM_IDS)
    except Exception as exc:
        print(f"[invocations-test] FAIL: {type(exc).__name__}: {exc}")
        ok = False
    print(f"[invocations-test] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
