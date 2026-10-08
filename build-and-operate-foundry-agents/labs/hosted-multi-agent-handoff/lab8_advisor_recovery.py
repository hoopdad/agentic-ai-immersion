# %% [markdown]
# # Lab 8: Advisor recovery and deployment
#
# **Prerequisites:** Lab 7.
#
# Start a fresh kernel after Lab 7 and resume its durable pending cases without repeating intake or specialist work.
# Test human revision and restart recovery before deploying the safe package.
# Local revision and deployed smoke tests call Azure models and may incur charges.
#
# This cell loads the completed Lab 7 checkpoint and original definitions without running Lab 7.
# %% Step 8.1 - Load the advisor prerequisites
from pathlib import Path
import json
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/hosted-multi-agent-handoff/lab8_advisor_recovery.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/hosted-multi-agent-handoff/lab8_advisor_recovery.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import foundry_env, notebook_parts

driver = lab_helpers.load_lab_module("hosted-multi-agent-handoff/lab4_hosted_multi_agent.py")


def resume_pending(case: dict, decisions: list[str], send, restart=None) -> tuple[dict, list[str]]:
    paths = []
    reply = case["reply"]
    previous = None  # Lab 7's process is gone: recover by durable session id, not in-memory Responses state.
    if reply.get("status") == "approved":
        if restart:
            restart()
        return reply["packet"], [reply.get("resume_path")]
    for decision in decisions:
        assert reply.get("status") == driver.PENDING, reply
        if restart:
            restart()
        reply, previous = send(json.dumps({
            "session_id": case["session_id"], "advisor": decision,
        }), previous)
        paths.append(reply.get("resume_path"))
    assert reply.get("status") == "approved", reply
    assert all(reply["packet"].get(key) == case["reply"]["packet"].get(key)
               for key in ("case_id", "participant_id", "lob")), "Advisor revision changed the original case identity."
    return reply["packet"], paths


if "__file__" not in globals():
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted = {}
    part_a = notebook_parts.read_checkpoint(
        driver.ARTIFACTS / "part_a.json", lab="lab4", part="a", context=notebook_parts.scope(driver.ENV),
    )
    assert driver.source_fingerprints() == part_a["state"]["tested_sources"], "Hosted/shared source changed since Lab 7 acceptance."
    pending = part_a["state"]["pending"]
    assert set(pending) == {"S1", "S2", "S3"}
    session_snapshot = json.loads((driver.ARTIFACTS / "pending_sessions.json").read_text(encoding="utf-8"))
    for case in pending.values():
        session_id = case["session_id"]
        session = json.loads((driver.ARTIFACTS / "sessions" / f"{session_id}.json").read_text(encoding="utf-8"))
        notes = session.get("notes", {})
        if notes.get("status") == "approved":
            final = notes.get("packet", {})
            original = session_snapshot[session_id]["packet"]
            assert all(final.get(key) == original.get(key) for key in ("case_id", "participant_id", "lob")), (
                "The completed session does not belong to Lab 7's original case."
            )
            driver.assert_packet_contract(final, original["lob"], "approve")
            assert notes.get("resume_path") == "session_store", "The prior approval lacks durable-recovery evidence."
            case["reply"] = {"status": "approved", "packet": final, "resume_path": notes["resume_path"]}
        else:
            assert {"status": notes.get("status"), "packet": notes.get("packet")} == session_snapshot[session_id], (
                "The durable pending session changed since Lab 7."
            )
    hosted_record = json.loads(driver.HOSTED_RECORD.read_text(encoding="utf-8"))
    assert hosted_record.get("agent_name") == part_a["state"]["hosted"]["agent_name"]

# %% [markdown]
# This cell resumes the existing S3 case with an advisor revision and verifies the added enrollment question before approval.
# %% Step 8.2 - Revise and approve the persisted packet
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("revision", None)
    with driver.HostedProcess():
        revised, revision_paths = resume_pending(
            pending["S3"], driver.SCENARIOS["S3"]["auto_decisions"],
            lambda text, previous=None: driver.post_turn(driver.LOCAL_BASE, text, previous),
        )
    driver.assert_packet_contract(revised, "both", "approve")
    assert revised["packet_attempts"] >= 2
    assert any("IEP" in question.upper() or "INITIAL ENROLLMENT" in question.upper()
               for question in revised["open_questions"])
    driver.save_packet("S3", {**revised, "session_id": pending["S3"]["session_id"]})
    accepted["revision"] = True

# %% [markdown]
# This cell restarts the server before approving Lab 7's S2 case and confirms that durable session recovery supplies the packet.
# %% Step 8.3 - Verify restart-safe advisor approval
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("recovery", None)
    server = driver.HostedProcess().start()
    try:
        def restart() -> None:
            server.stop()
            server.start()
        recovered, recovery_paths = resume_pending(
            pending["S2"], ["approve"],
            lambda text, previous=None: driver.post_turn(driver.LOCAL_BASE, text, previous),
            restart=restart,
        )
        completed, _ = resume_pending(
            pending["S1"], ["approve"],
            lambda text, previous=None: driver.post_turn(driver.LOCAL_BASE, text, previous),
        )
    finally:
        server.stop()
    assert "session_store" in recovery_paths, recovery_paths
    driver.assert_packet_contract(recovered, "accounts", "approve")
    driver.assert_packet_contract(completed, "marketplace", "approve")
    driver.save_packet("S2", {**recovered, "session_id": pending["S2"]["session_id"]})
    driver.save_packet("S1", {**completed, "session_id": pending["S1"]["session_id"]})
    accepted["recovery"] = True

# %% [markdown]
# This cell deploys the safe triage package to Azure and displays its version status after local approval checks pass.
# %% Step 8.4 - Deploy the approved triage package
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("deployment", None)
    assert accepted.get("revision") and accepted.get("recovery"), "Complete the current advisor gates before deployment."
    assert driver.source_fingerprints() == part_a["state"]["tested_sources"], "Hosted/shared source changed; rerun Lab 7 before deployment."
    assert revised["advisor_decision"] == recovered["advisor_decision"] == "approve"
    subprocess.run(["bash", "-lc", driver.deploy_commands()], cwd=driver.HOSTED_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", driver.AGENT_NAME], cwd=driver.HOSTED_DIR, check=True)
    accepted["deployment"] = True

# %% [markdown]
# This cell records the active version you inspected and saves Lab 8 only after a deployed case reaches final approval.
# %% Step 8.5 - Verify final deployed approval
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("deployed_approval", None)
    assert all(accepted.get(key) for key in ("revision", "recovery", "deployment")), "Complete every current Lab 8 gate."
    DEPLOYED_VERSION = ""  # Enter the active version shown by the previous cell.
    assert DEPLOYED_VERSION, "Enter the active Foundry version in DEPLOYED_VERSION."
    deployed = driver.demo(scenarios=("S2",), auto=True, deployed=True)
    assert deployed["S2"]["advisor_decision"] == "approve"
    hosted = driver.record_deployment(DEPLOYED_VERSION)
    accepted["deployed_approval"] = True
    part_b = notebook_parts.write_checkpoint(
        driver.ARTIFACTS / "part_b.json", lab="lab4", part="b", context=notebook_parts.scope(driver.ENV),
        state={"hosted": hosted, "revision_paths": revision_paths, "recovery_paths": recovery_paths, "accepted": accepted},
        evidence=[driver.HOSTED_RECORD, *(driver.PACKETS_DIR / f"{key}.json" for key in ("S1", "S2", "S3"))],
    )
