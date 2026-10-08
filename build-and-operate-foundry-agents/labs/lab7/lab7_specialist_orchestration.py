# %% [markdown]
# # Lab 7: Specialist orchestration
#
# **Prerequisites:** Lab 6.
#
# Build the role-separated graph, classify cases, fan out to specialists, and inspect compliance-reviewed packets.
# Approval belongs to Lab 8: this lab stops at `pending_advisor_approval`.
# The original driver and `hosted/` modules remain implementation helpers, not an alternate learner route.
# Local hosted runs call Azure models and may incur charges.
#
# This cell imports the workflow definitions without executing the original notebook exercises.
# %% Step 7.1 - Load orchestration helpers
from pathlib import Path
import json
import sys
import uuid

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/lab7/lab7_specialist_orchestration.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/lab7/lab7_specialist_orchestration.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("hosted-multi-agent-handoff/lab4_hosted_multi_agent.py")


def pending_case(key: str, scenario: dict, send) -> dict:
    session_id = f"{key}-{uuid.uuid4().hex[:8]}"
    reply, response_id = send(json.dumps({
        "session_id": session_id, "participant_id": scenario["participant_id"],
        "scenario": key, "message": scenario["message"],
    }))
    assert reply.get("status") == driver.PENDING, reply
    driver.assert_packet_contract(reply["packet"], scenario["expected_lob"])
    session_path = driver.ARTIFACTS / "sessions" / f"{session_id}.json"
    assert session_path.is_file(), f"Pending session was not persisted: {session_path}"
    return {"session_id": session_id, "response_id": response_id, "reply": reply}

if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted = {}


# %% [markdown]
# This cell prepares the hosted graph and stops three classified fan-out cases at the durable advisor boundary.
# %% Step 7.2 - Execute specialist fan-out and compliance
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("orchestration", None)
    hosted = driver.build(standalone=False)
    pending = {}
    with driver.HostedProcess():
        for key, scenario in driver.SCENARIOS.items():
            pending[key] = pending_case(
                key, scenario, lambda text: driver.post_turn(driver.LOCAL_BASE, text)
            )
            print(key, pending[key]["reply"]["packet"]["lob"], driver.PENDING)
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "pending_cases.json", pending)
    accepted["orchestration"] = True

# %% [markdown]
# ## YOUR TURN: reject an unsafe specialist draft
#
# Temporarily add `Finish with the single plan you would pick.` to `MARKETPLACE_INSTRUCTIONS`
# in `../../shared/hosted-multi-agent-handoff/hosted/marketplace_specialists.py`, save, then execute the following cell.
# The reviewer must reject the unsafe draft and take its bounded one-revision route.
# Remove the added sentence afterward; do not approve or deploy this test case.
#
# This cell proves the compliance reviewer rejects and revises the unsafe draft without sending an advisor decision.
# %% Step 7.3 - Verify bounded compliance reflection
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("compliance", None)
    with driver.HostedProcess():
        compliance_case = pending_case(
            "compliance-gate", driver.SCENARIOS["S1"],
            lambda text: driver.post_turn(driver.LOCAL_BASE, text),
        )
    compliance_log = driver.SERVER_LOG.read_text(encoding="utf-8", errors="replace")
    assert "compliant=False" in compliance_log, "The unsafe draft was not rejected."
    assert "sending marketplace-guide back for one revision" in compliance_log
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "compliance_evidence.json", {
        "case": compliance_case, "rejected": True, "bounded_revision": True,
    })
    accepted["compliance"] = True

# %% [markdown]
# ## YOUR TURN: model-based classification
#
# Restore the safe specialist instruction, then add a tool-free `lob-classifier` Agent
# with `response_format=LobCall` to `../../shared/hosted-multi-agent-handoff/hosted/marketplace_specialists.py` and its `build_all()`.
# `IntakeExecutor.start` already calls it and preserves `classify_lob()` as a logged fallback.
# The ambiguous card-payment message must route to accounts, not the keyword fallback's both.
#
# This cell tests model classification at the pending boundary without approving or rerunning the advisor flow.
# %% Step 7.4 - Verify ambiguous task classification
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("classification", None)
    hosted = driver.build(standalone=False)
    tested_sources = driver.source_fingerprints()
    scenario = {
        "participant_id": "P-1003", "expected_lob": "accounts",
        "message": "My card was declined when I tried to pay for a prescription.",
    }
    with driver.HostedProcess():
        classifier_case = pending_case(
            "classifier-gate", scenario, lambda text: driver.post_turn(driver.LOCAL_BASE, text)
        )
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "classification_evidence.json", classifier_case)
    assert driver.source_fingerprints() == tested_sources, "Hosted source changed during the classification gate."
    accepted["classification"] = True

# %% [markdown]
# This cell records validated intermediate evidence so a fresh Lab 8 kernel can resume the original cases.
# %% Step 7.5 - Save the orchestration handoff
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    assert all(accepted.get(key) for key in ("orchestration", "compliance", "classification")), "Complete every current Lab 7 gate."
    assert driver.source_fingerprints() == tested_sources, "Rerun classification after changing tested hosted or shared source."
    session_snapshot = {}
    for case in pending.values():
        session_id = case["session_id"]
        session = json.loads((driver.ARTIFACTS / "sessions" / f"{session_id}.json").read_text(encoding="utf-8"))
        notes = session.get("notes", {})
        assert notes.get("status") == driver.PENDING and notes.get("packet") == case["reply"]["packet"]
        session_snapshot[session_id] = {"status": notes["status"], "packet": notes["packet"]}
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "pending_sessions.json", session_snapshot)
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "orchestration_sources.json", {
        "tested_sources": tested_sources, "accepted": accepted,
    })
    part_a = notebook_parts.write_checkpoint(
        driver.ARTIFACTS / "part_a.json", lab="lab4", part="a", context=notebook_parts.scope(driver.ENV),
        state={"hosted": hosted, "pending": pending, "accepted": accepted, "tested_sources": tested_sources},
        evidence=[
            driver.ARTIFACTS / "pending_cases.json", driver.ARTIFACTS / "pending_sessions.json",
            driver.ARTIFACTS / "compliance_evidence.json",
            driver.ARTIFACTS / "classification_evidence.json",
            driver.ARTIFACTS / "orchestration_sources.json",
        ],
    )
    print("Lab 7 complete: specialist evidence saved; advisor approval remains pending.")
