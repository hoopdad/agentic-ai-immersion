# %% [markdown]
# # Lab 7: Build and host a multi-agent team
#
# **Prerequisites:** Lab 4's accepted deployed Responses checkpoint.
# **Recommended route:** one-day Labs 1 -> 4 -> 7 (capstone).
# Turn one hosted agent into a separate code-defined specialist team: parallel work,
# structured merge, compliance review, a human approval boundary and Foundry hosting.
# MAF supplies orchestration; Foundry supplies container hosting and versioned invocation.
# Use synthetic data and local knowledge tools; no Search, Lab 6 or Prompt Agents required.
# Edit the isolated product under `../products/hosted-multi-agent-handoff/hosted/`.
# Acceptance requires a changed classifier, explicit decisions and fixed-version invocation.
# No restart exercise, distributed recovery, production advisor authorization or evaluation claim.
# Model calls and deployment incur charges. Stop owned processes; use a fresh kernel.
#
# This cell imports the workflow definitions without executing the original notebook exercises.
# %% Step 7.1 - Load orchestration helpers
from pathlib import Path
import json
import sys
import uuid

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/1-day-labs/lab07/lab07_specialist_orchestration.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/1-day-labs/lab07/lab07_specialist_orchestration.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "1-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
import one_day_parts as notebook_parts

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
    prerequisite = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab2", "part_b.json"), lab="lab2", part="b",
        context=notebook_parts.scope(driver.ENV))
    assert prerequisite["state"].get("deployed_inference") == "passed", "Complete Lab 4 deployed inference."
    import inspect
    workflow_source = (driver.HOSTED_DIR / "marketplace_workflow.py").read_text(encoding="utf-8")
    print(workflow_source)
    print("intake -> marketplace + accounts -> merge -> compliance -> human review")
    print(inspect.getsource(driver.deployed_turn))



# %% [markdown]
# This cell prepares the hosted graph and stops three classified fan-out cases at the durable advisor boundary.
# %% Step 7.2 - Execute specialist fan-out and compliance
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("orchestration", None)
    hosted = driver.build(standalone=True)
    pending = {}
    with driver.HostedProcess():
        for key, scenario in driver.SCENARIOS.items():
            pending[key] = pending_case(
                key, scenario, lambda text: driver.post_turn(driver.LOCAL_BASE, text)
            )
            print(key, pending[key]["reply"]["packet"]["lob"], driver.PENDING)
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "pending_cases.json", pending)
    print(driver.SERVER_LOG.read_text(encoding="utf-8", errors="replace"))
    accepted["orchestration"] = True

# %% [markdown]
# ## YOUR TURN: model-based classification
#
# Add a tool-free `lob-classifier` Agent
# with `response_format=LobCall` to `../products/hosted-multi-agent-handoff/hosted/marketplace_specialists.py` and its `build_all()`.
# `IntakeExecutor.start` already calls it and preserves `classify_lob()` as a logged fallback.
# The ambiguous card-payment message must route to accounts, not the keyword fallback's both.
#
# This cell tests model classification at the pending boundary without approving or rerunning the advisor flow.
# %% Step 7.3 - Verify ambiguous task classification
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("classification", None)
    hosted = driver.build(standalone=True)
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

# Short-only cell source appended by sync_one_day_labs.py, not a standalone driver.
# %% [markdown]
# ## YOUR TURN: inspect and approve your team's packet
#
# MAF runs the fan-out, merge, compliance review and `request_info` boundary.
# Foundry hosts the Python workflow behind the Responses protocol; these are
# code-defined specialists inside one hosted service, not separate Prompt Agents.
# Read `advisor_prompt` and the packet below before entering a decision.
# This is a synthetic advisor simulation, not production authorization.
# Unresolved compliance flags are visible to the reviewer and must not be hidden.
#
# This cell runs a new mixed case using your changed classifier and stops for explicit human review.
# %% Step 7.4 - Review the team's mixed-case result
(driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
accepted.pop("approval", None)
assert accepted.get("classification"), "Pass the current classifier exercise first."
assert driver.source_fingerprints() == tested_sources, "Source changed; rerun the local team and classifier."
team_server = driver.HostedProcess().start()
try:
    review_case = pending_case("team-review", driver.SCENARIOS["S3"],
                               lambda text: driver.post_turn(driver.LOCAL_BASE, text))
    print(review_case["reply"]["advisor_prompt"])
    print(json.dumps(review_case["reply"]["packet"], indent=2))
except BaseException:
    team_server.stop()
    raise

# %% [markdown]
# Enter `approve` only after reviewing the synthetic packet. This sends one explicit
# decision, never an automatic approval or a retry loop. Rerun the preceding cell
# for a new review after a failure. Always stop this notebook's server afterward.
#
# This cell resumes the pending MAF workflow with the learner's explicit decision and saves its final packet.
# %% Step 7.5 - Approve the reviewed local packet
(driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
accepted.pop("approval", None)
ADVISOR_DECISION = ""  # Enter approve after reviewing the packet above.
try:
    assert ADVISOR_DECISION == "approve", "Review the packet and explicitly enter approve."
    assert driver.source_fingerprints() == tested_sources, "Source changed during review; rerun local acceptance."
    final, _ = driver.post_turn(driver.LOCAL_BASE, json.dumps({
        "session_id": review_case["session_id"], "advisor": ADVISOR_DECISION,
    }), review_case["response_id"])
    driver.assert_packet_contract(final["packet"], "both", "approve")
    assert final["status"] == "approved"
    assert final["packet"]["case_id"] == review_case["reply"]["packet"]["case_id"]
    driver.save_packet("team-local", final["packet"])
    accepted["approval"] = True
    print(json.dumps(final["packet"], indent=2))
finally:
    team_server.stop()

# %% [markdown]
# Review the deployment command and its paid Azure scope. Deploy only after the
# local team, classifier change and explicit approval succeed. This packages the
# same edited source, with synthetic local knowledge, not Search or a Lab 6 service.
#
# This cell deploys the accepted multi-agent team as a separate Foundry hosted service.
# %% Step 7.6 - Host your team in Foundry
import subprocess
(driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
accepted.pop("deployment", None)
assert all(accepted.get(key) for key in ("orchestration", "classification", "approval"))
assert driver.source_fingerprints() == tested_sources, "Source changed; rerun local acceptance before deployment."
commands = driver.deploy_commands()
print(commands)
subprocess.run(["bash", "-lc", commands], cwd=driver.HOSTED_DIR, check=True)
subprocess.run(["azd", "ai", "agent", "show", driver.AGENT_NAME], cwd=driver.HOSTED_DIR, check=True)
accepted["deployment"] = True

# %% [markdown]
# Wait for active status, pin 100% of traffic to that version in Foundry and enter
# it below. This cell validates routing; it never changes it. Observe that the
# hosted team stops at pending approval before any human decision.
# File-backed pending state is single-instance, not distributed resume.
#
# This cell invokes the pinned hosted team and records the observed pending packet for explicit review.
# %% Step 7.7 - Invoke your hosted team
(driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
accepted.pop("deployed_approval", None)
DEPLOYED_VERSION = ""  # Enter the active version inspected in Foundry.
assert accepted.get("deployment") and DEPLOYED_VERSION, "Deploy and inspect an active version first."
assert driver.source_fingerprints() == tested_sources, "Source changed; repeat local and deployed acceptance."
driver.require_pinned_version(DEPLOYED_VERSION)
deployed_session = f"team-hosted-{uuid.uuid4().hex[:8]}"
deployed_reply, deployed_response = driver.deployed_turn(json.dumps({
    "session_id": deployed_session, "participant_id": "P-1005",
    "scenario": "team-hosted", "message": driver.SCENARIOS["S3"]["message"],
}), expected_version=DEPLOYED_VERSION)
assert deployed_reply["status"] == driver.PENDING, deployed_reply
driver.assert_packet_contract(deployed_reply["packet"], "both")
print(deployed_reply["advisor_prompt"])
print(json.dumps(deployed_reply["packet"], indent=2))

# %% [markdown]
# Review the hosted packet, then explicitly enter `approve`. No advisor decision
# is forwarded from your earlier local case. Do not retry a sent decision:
# re-inspect state or start a new case if the response is uncertain.
# A schema and safety check are evidence, not production compliance certification.
#
# This cell sends one human-approved hosted decision and publishes the capstone evidence only after fixed-version acceptance.
# %% Step 7.8 - Finish and record the hosted team
(driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
accepted.pop("deployed_approval", None)
DEPLOYED_ADVISOR_DECISION = ""  # Enter approve only after reviewing the hosted packet.
assert DEPLOYED_ADVISOR_DECISION == "approve", "Review the hosted packet and explicitly enter approve."
assert all(accepted.get(key) for key in ("orchestration", "classification", "approval", "deployment")), (
    "Complete this kernel's local team, classifier, approval and deployment gates first."
)
assert driver.source_fingerprints() == tested_sources, "Source changed; repeat local and deployed acceptance."
driver.require_pinned_version(DEPLOYED_VERSION)
deployed_final, _ = driver.deployed_turn(json.dumps({
    "session_id": deployed_session, "advisor": DEPLOYED_ADVISOR_DECISION,
}), deployed_response, expected_version=DEPLOYED_VERSION)
assert deployed_final["status"] == "approved", deployed_final
driver.assert_packet_contract(deployed_final["packet"], "both", "approve")
assert deployed_final["packet"]["case_id"] == deployed_reply["packet"]["case_id"]
driver.require_pinned_version(DEPLOYED_VERSION)
hosted = driver.record_deployment(DEPLOYED_VERSION)
driver.save_packet("team-deployed", deployed_final["packet"])
driver.foundry_env.save_artifact(driver.ARTIFACTS / "team_acceptance.json", {
    "tested_sources": tested_sources, "version": DEPLOYED_VERSION,
    "pending": deployed_reply, "final": deployed_final,
    "human_decision": DEPLOYED_ADVISOR_DECISION,
})
accepted["deployed_approval"] = True
notebook_parts.write_checkpoint(
    driver.ARTIFACTS / "part_a.json", lab="lab4", part="a", context=notebook_parts.scope(driver.ENV),
    state={"track": "one-day-team", "accepted": accepted, "tested_sources": tested_sources,
           "hosted": hosted, "deployed_version": DEPLOYED_VERSION},
    evidence=[driver.HOSTED_RECORD, driver.ARTIFACTS / "team_acceptance.json",
              driver.ARTIFACTS / "classification_evidence.json",
              driver.PACKETS_DIR / "team-local.json", driver.PACKETS_DIR / "team-deployed.json"],
)
print("You built, changed, reviewed and hosted a multi-agent team. One-day capstone complete.")
