# %% [markdown]
# # Lab 4B: Advisor recovery and deployment
#
# Start a fresh kernel after Lab 4A and resume its durable pending cases without repeating intake or specialist work.
# Test human revision and restart recovery before deploying the safe package.
# Local revision and deployed smoke tests call Azure models and may incur charges.
#
# This cell loads the completed Lab 4A checkpoint and original definitions without running Lab 4A.
# %% Step 4.1 - Load the advisor prerequisites
from pathlib import Path
import json
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/lab4-hosted-multi-agent-handoff/lab4b_advisor_recovery.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/lab4-hosted-multi-agent-handoff/lab4b_advisor_recovery.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import foundry_env, notebook_parts

driver = lab_helpers.load_lab_module("lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py")


def resume_pending(case: dict, decisions: list[str], send, restart=None) -> tuple[dict, list[str]]:
    paths = []
    reply = case["reply"]
    previous = None  # A's process is gone: recover by durable session id, not in-memory Responses state.
    for decision in decisions:
        assert reply.get("status") == driver.PENDING, reply
        if restart:
            restart()
        reply, previous = send(json.dumps({
            "session_id": case["session_id"], "advisor": decision,
        }), previous)
        paths.append(reply.get("resume_path"))
    assert reply.get("status") == "approved", reply
    return reply["packet"], paths


if "__file__" not in globals():
    part_a = notebook_parts.read_checkpoint(
        driver.ARTIFACTS / "part_a.json", lab="lab4", part="a", context=notebook_parts.scope(driver.ENV),
    )
    pending = part_a["state"]["pending"]
    assert set(pending) == {"S1", "S2", "S3"}

# %% [markdown]
# This cell resumes the existing S3 case with an advisor revision and verifies the added enrollment question before approval.
# %% Step 4.2 - Revise and approve the persisted packet
if "__file__" not in globals():
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

# %% [markdown]
# This cell restarts the server before approving A's S2 case and confirms that durable session recovery supplies the packet.
# %% Step 4.3 - Verify restart-safe advisor approval
if "__file__" not in globals():
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

# %% [markdown]
# This cell deploys the safe triage package to Azure and displays its version status after local approval checks pass.
# %% Step 4.4 - Deploy the approved triage package
if "__file__" not in globals():
    assert revised["advisor_decision"] == recovered["advisor_decision"] == "approve"
    subprocess.run(["bash", "-lc", driver.deploy_commands()], cwd=driver.HOSTED_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", driver.AGENT_NAME], cwd=driver.HOSTED_DIR, check=True)

# %% [markdown]
# This cell records the active version you inspected and saves Lab 4B only after a deployed case reaches final approval.
# %% Step 4.5 - Verify final deployed approval
if "__file__" not in globals():
    DEPLOYED_VERSION = ""  # Enter the active version shown by the previous cell.
    assert DEPLOYED_VERSION, "Enter the active Foundry version in DEPLOYED_VERSION."
    deployed = driver.demo(scenarios=("S2",), auto=True, deployed=True)
    assert deployed["S2"]["advisor_decision"] == "approve"
    hosted = driver.record_deployment(DEPLOYED_VERSION)
    part_b = notebook_parts.write_checkpoint(
        driver.ARTIFACTS / "part_b.json", lab="lab4", part="b", context=notebook_parts.scope(driver.ENV),
        state={"hosted": hosted, "revision_paths": revision_paths, "recovery_paths": recovery_paths},
        evidence=[driver.HOSTED_RECORD, *(driver.PACKETS_DIR / f"{key}.json" for key in ("S1", "S2", "S3"))],
    )
