# %% [markdown]
# # Labs 7-8: Hosted multi-agent handoff
#
# **Technology focus.** This lab uses Microsoft Foundry (Hosted triage; HTTP turns) and Microsoft Agent Framework
# (`WorkflowBuilder`; `request_info`).
#
# **A role-separated workflow inside the container, with bounded review and simulated advisor approval across HTTP turns.**
#
# |  | Details |
# | --- | --- |
# | Goal | Run the Healthcare Marketplace triage workflow (intake → marketplace guide + accounts assistant → compliance review → advisor handoff) inside a hosted agent, then approve, revise, or decline the packet on the next client turn. Run S1, S2, and S3 locally before optionally deploying `healthcare-marketplace-triage-hosted`. |
# | Inputs | `labs/artifacts/lab3/hosted.json` or `knowledge.json`; root `.env` |
# | Outputs | `labs/artifacts/lab4/handoff_packets/S1.json`, `S2.json`, `S3.json`, `labs/artifacts/lab4/hosted.json`, and `hosted_local.log` |
# | Time | 60 min (teach 10, demo 10, do 35, checkpoint 5) |
#
# **How to run.** Execute this notebook's cells in order, pausing for the requested source edits.
# The acceptance cells send simulated advisor decisions automatically; deployment is a separate explicit cell.
#
# **Where this runs.** This notebook (workstation) vendors `common/` and `data/` into `hosted/`, starts
# `hosted/main.py` locally on port 8088 and plays two roles against it: the participant (turn 1, a case envelope)
# and the licensed advisor (turn 2+, `approve` / `revise: ...` / `decline: ...`). `hosted/main.py` is the product:
# inside it an Agent Framework `WorkflowBuilder` graph runs four specialist agents and pauses at `request_info`;
# Foundry runs that container after you execute the deployment cell.
#
# **Lab path and prerequisites.**
#
# - **Required for the cumulative path:** Complete the Labs 5-6 notebook first.
# - **Local workflow boundary:** The acceptance cells can use local knowledge when Labs 5-6 artifacts are absent;
#   this does not reproduce the cumulative deployed-agent path.
# - **From Labs 3-4:** This lab reuses the local server lifecycle, port 8088, Responses endpoint, source packaging,
#   and explicit `azd` deployment pattern first introduced in Labs 3-4.
# - **Optional:** Cloud deployment is an extension; restart continuity is exercised by an ordinary notebook cell.
#
# **Checkpoint artifact.** `labs/artifacts/lab4/handoff_packets/S1.json`, `S2.json`, `S3.json` (final packets with
# `advisor_decision`) and `labs/artifacts/lab4/hosted.json`. Labs 9-10 evaluate and operate the Lab 6 concierge; the evaluation
# may record this workflow agent's metadata, but does not require or evaluate these handoff packets.
#
# %% [markdown]
# ## Before the first run
#
# Continue with the dev container, root `.env`, Azure sign-in, and `/usr/local/bin/python` kernel used in Labs 1
# and 2. If you have not completed that setup, follow the workshop `SETUP.md` first.
#
# %% [markdown]
# This cell loads shared helpers and configures the triage agent and handoff artifact paths.
#
# %% Step 4.1 - Imports and paths
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SOURCE_PATH = (
    Path(__file__).resolve()
    if "__file__" in globals()
    else next(
        parent / "build-and-operate-foundry-agents/labs/hosted-multi-agent-handoff/lab4_hosted_multi_agent.py"
        for parent in (Path.cwd(), *Path.cwd().parents)
        if (parent / "build-and-operate-foundry-agents/labs/hosted-multi-agent-handoff/lab4_hosted_multi_agent.py").is_file()
    )
)
LAB_DIR = SOURCE_PATH.parent
ROOT = LAB_DIR.parents[1]  # workshop root (common/ and data/ live here)
LABS_DIR = ROOT / "labs"
for folder in (ROOT, LABS_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import (
    foundry_env,
    guardrails,
    marketplace_data,
    model_resilience,
    resource_names,
)  # noqa: E402

import lab_helpers  # noqa: E402

LAB = "lab4"
ENV = foundry_env.load_env()
AGENT_NAME = resource_names.name(resource_names.HOSTED_TRIAGE, ENV)
HOSTED_DIR = LAB_DIR / "hosted"
ARTIFACTS = lab_helpers.artifact_path(LAB)
PACKETS_DIR = ARTIFACTS / "handoff_packets"
HOSTED_RECORD = ARTIFACTS / "hosted.json"
SERVER_LOG = ARTIFACTS / "hosted_local.log"
PORT = int(os.environ.get("MARKETPLACE_HOSTED_PORT", "8088"))
LOCAL_BASE = f"http://localhost:{PORT}"
PENDING = "pending_advisor_approval"


def log(message: str) -> None:
    print(f"[{LAB}] {message}", flush=True)


def source_fingerprints() -> dict[str, str]:
    """Bind orchestration acceptance to the hosted product and shared runtime sources."""
    paths = [
        *(HOSTED_DIR / name for name in (
            "main.py", "marketplace_specialists.py", "marketplace_workflow.py", "prepare.py", "requirements.txt",
        )),
        *(ROOT / "common" / f"{name}.py" for name in (
            "guardrails", "marketplace_data", "model_resilience", "session_store",
        )),
        SOURCE_PATH,
    ]
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def require_previous_lab(standalone: bool = False) -> dict:
    """Labs 5-6 deployed healthcare-marketplace-concierge-hosted v2 with the knowledge base. Labs 7-8 reads its record for continuity."""
    for name in ("hosted.json", "knowledge.json"):
        path = lab_helpers.artifact_path("lab3", name)
        if path.exists():
            return foundry_env.load_artifact(path)
    if standalone:
        log(
            "artifacts/lab3 missing; continuing with local knowledge search, not the cumulative deployment"
        )
        return {}
    return lab_helpers.require_artifact("lab3", "hosted.json", 3, LAB)


# %% [markdown]
# This cell defines the triage cases and the advisor decisions used in the acceptance exercises.
# %% Step 4.2 - Define scenarios and advisor decisions
SCENARIOS: dict[str, dict] = {
    "S1": {
        "participant_id": "P-1001",
        "title": "AEP shopper",
        "expected_lob": "marketplace",
        "message": "I am on MA-CONTOSO-HMO-01. Is there a plan with a lower drug cost for my atorvastatin where I can "
        "keep my cardiologist, Dr. Osei? And when could I switch?",
        "auto_decisions": ["approve"],
    },
    "S2": {
        "participant_id": "P-1003",
        "title": "Denied claim",
        "expected_lob": "accounts",
        "message": "My claim CLM-9003 was denied and I do not understand why. What do I need to send to get it paid?",
        "auto_decisions": ["approve"],
    },
    "S3": {
        "participant_id": "P-1005",
        "title": "Pre-Medicare, both LOBs",
        "expected_lob": "both",
        "message": "I have my sponsor's HRA and I need an ACA plan for next year. What is my HRA balance, what ACA plans "
        "are there in my county, and what happens when I turn 65 next year? Which one should I pick?",
        "auto_decisions": [
            "revise: add the IEP dates for turning 65 to open_questions",
            "approve",
        ],
    },
}


# %% [markdown]
# This cell defines package preparation and handoff records without deploying to Azure.
# %% Step 4.3 - Build the multi-agent package
def build(*, vendor: bool = True, standalone: bool = True) -> dict:
    env = foundry_env.load_env()
    resource_names.suffix(env, required=True)
    previous = require_previous_lab(standalone=standalone)
    counts: dict[str, int] = {}
    if vendor:
        prepare = lab_helpers.load_lab_module(f"{LAB_DIR.name}/hosted/prepare.py")
        counts = prepare.vendor()
    existing = (
        json.loads(HOSTED_RECORD.read_text(encoding="utf-8"))
        if HOSTED_RECORD.exists()
        else {}
    )
    record = {
        "lab": LAB,
        "agent_name": AGENT_NAME,
        "protocol": "responses",
        "model": lab_helpers.pick_model(env),
        "runtime": "python_3_14",
        "entry_point": "main.py",
        "hosted_dir": str(HOSTED_DIR.relative_to(ROOT)),
        "local_endpoint": f"{LOCAL_BASE}/responses",
        "project_endpoint": env.get("FOUNDRY_PROJECT_ENDPOINT", ""),
        "workflow": {
            "executors": [
                "intake",
                "marketplace-guide",
                "accounts-assistant",
                "merge",
                "compliance-reviewer",
                "compliance-gate",
                "advisor-coordinator",
                "advisor-handoff",
            ],
            "human_in_the_loop": "request_info paused per session; resumed by the advisor's next HTTP turn",
        },
        "knowledge": (
            "mcp " + env["MARKETPLACE_KB_MCP_URL"]
            if env.get("MARKETPLACE_KB_MCP_URL")
            else "local search over data/knowledge"
        ),
        "session_store": "file",
        "previous_lab": (
            {
                "agent_name": previous.get("agent_name"),
                "deployed": previous.get("deployed"),
            }
            if previous
            else None
        ),
        "vendored": counts or existing.get("vendored", {}),
        "deployed": existing.get("deployed")
        or {"version": None, "status": "not deployed", "recorded_at": None},
        "built_at": lab_helpers.now_iso(),
    }
    foundry_env.save_artifact(HOSTED_RECORD, record)
    log(
        f"wrote {HOSTED_RECORD.relative_to(LABS_DIR)} (agent {AGENT_NAME}, knowledge: {record['knowledge']}, sessions: {record['session_store']})"
    )
    return record


# %% [markdown]
# This cell defines the local workflow server and ensures its processes can be stopped reliably.
# %% Step 4.4 - Define the local hosted server
class HostedProcess:
    def __init__(
        self,
        hosted_dir: Path = HOSTED_DIR,
        port: int = PORT,
        log_path: Path = SERVER_LOG,
    ):
        self.hosted_dir, self.port, self.log_path = hosted_dir, port, log_path
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        self.starts = 0

    def log_tail(self, lines: int = 30) -> str:
        if not self.log_path.is_file():
            return "(log file was not created)"
        return "\n".join(
            self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[
                -lines:
            ]
        )

    def start(self, timeout: float = 120.0) -> "HostedProcess":
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError(
                f"hosted/main.py is already running with pid {self.process.pid}"
            )
        env = {
            **os.environ,
            **foundry_env.load_env(),
            "MARKETPLACE_HOSTED_PORT": str(self.port),
            "PYTHONUNBUFFERED": "1",
        }
        env.setdefault(
            "MARKETPLACE_SESSION_DIR", str(ARTIFACTS / "sessions")
        )  # session map visible next to the packets
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open(
            "w" if self.starts == 0 else "a", encoding="utf-8"
        )
        self.log_handle.write(
            f"\n[{LAB}] process start {self.starts + 1} at "
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        )
        self.log_handle.flush()
        try:
            self.process = subprocess.Popen(
                [sys.executable, str(self.hosted_dir / "main.py")],
                cwd=str(self.hosted_dir),
                env=env,
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
            )
            self.starts += 1
            log(
                f"started hosted/main.py (pid {self.process.pid}) on port {self.port}; log -> {self.log_path.relative_to(LABS_DIR)}"
            )
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.process.poll() is not None:
                    code = self.process.returncode
                    raise RuntimeError(
                        f"[{LAB}] hosted/main.py exited early (code {code}). "
                        f"Log: {self.log_path}\n--- log tail ---\n{self.log_tail()}"
                    )
                with socket.socket() as probe:
                    probe.settimeout(1.0)
                    if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                        log("server is accepting connections")
                        return self
                time.sleep(1.0)
            raise RuntimeError(
                f"[{LAB}] server did not open port {self.port} within {timeout:.0f}s. "
                f"Log: {self.log_path}\n--- log tail ---\n{self.log_tail()}"
            )
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        process = self.process
        if process is not None:
            pid = process.pid
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            log(f"stopped hosted/main.py (pid {pid}, exit {process.returncode})")
        if self.log_handle is not None:
            self.log_handle.close()
        self.process = None
        self.log_handle = None

    def __enter__(self) -> "HostedProcess":
        return self.start()

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.stop()


# %% [markdown]
# This cell defines local and deployed workflow requests with explicit error handling.
# %% Step 4.5 - Call the triage workflow
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
    for candidate in (text, text[text.find("{") : text.rfind("}") + 1]):
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return {"status": "unparsed", "raw": text}


def post_turn(
    base: str, text: str, previous_response_id: str | None = None
) -> tuple[dict, str | None]:
    import httpx

    # VERIFY: POST /responses body and previous_response_id handling (see Labs 3-4 post_responses)
    body: dict = {"input": text, "stream": False}
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    response = httpx.post(f"{base.rstrip('/')}/responses", json=body, timeout=600.0)
    response.raise_for_status()
    payload = response.json()
    model_resilience.ensure_response_succeeded(payload, LAB)
    return parse_reply(output_text(payload)), payload.get("id")


def deployed_turn(
    text: str, previous_response_id: str | None = None
) -> tuple[dict, str | None]:
    client = foundry_env.get_openai_client(agent_name=AGENT_NAME)
    kwargs = (
        {"previous_response_id": previous_response_id} if previous_response_id else {}
    )
    response = client.responses.create(input=text, **kwargs)
    return parse_reply(response.output_text), getattr(response, "id", None)


# %% [markdown]
# This cell defines the handoff runner, advisor approval loop, and packet-contract checks.
# %% Step 4.6 - Define the handoff demo
def interactive_decider(reply: dict) -> str:
    print(
        f"\n[{LAB}] ----- ADVISOR REVIEW ({reply.get('case_id')}) -----\n{reply.get('advisor_prompt')}"
    )
    while True:
        answer = input(f"[{LAB}] advisor> ").strip()
        if answer:
            return answer


def save_packet(key: str, packet: dict) -> Path:
    path = PACKETS_DIR / f"{key}.json"
    foundry_env.save_artifact(path, packet)
    log(
        f"wrote {path.relative_to(LABS_DIR)} (decision {packet.get('advisor_decision')}, status {packet.get('status')}, "
        f"flags {len(packet.get('compliance_flags', []))}, facts {len(packet.get('facts_gathered', []))}, attempts {packet.get('packet_attempts')})"
    )
    return path


def assert_packet_contract(
    packet: dict, expected_lob: str, decision: str | None = None
) -> None:
    required = {
        "case_id",
        "participant_id",
        "lob",
        "summary",
        "participant_goals",
        "facts_gathered",
        "options_discussed",
        "open_questions",
        "recommended_next_step_for_advisor",
        "compliance_flags",
        "created_at",
        "packet_attempts",
    }
    missing = sorted(required - packet.keys())
    assert not missing, f"packet is missing required fields: {missing}"
    assert (
        packet["lob"] == expected_lob
    ), f"expected lob={expected_lob}, got {packet['lob']}"
    assert isinstance(
        packet["compliance_flags"], list
    ), "compliance_flags must be a list"
    packet_text = json.dumps(packet, default=str)
    assert not guardrails.contains_recommendation(
        " ".join(packet.get("options_discussed", []) + [packet.get("summary", "")])
    ), "packet contains recommendation language"
    assert (
        guardrails.redact_pii(packet_text) == packet_text
    ), "packet contains unredacted PII"
    if decision is not None:
        assert (
            packet.get("advisor_decision") == decision
        ), f"expected advisor_decision={decision}, got {packet.get('advisor_decision')}"
        expected_status = "approved" if decision == "approve" else "declined"
        assert (
            packet.get("status") == expected_status
        ), f"expected status={expected_status}, got {packet.get('status')}"


def run_scenario(
    key: str,
    send,
    *,
    auto: bool,
    restart: Callable[[], None] | None = None,
    trace: dict | None = None,
) -> dict:
    scenario = SCENARIOS[key]
    session_id = f"{key}-{uuid.uuid4().hex[:8]}"
    log(
        f"=== {key} {scenario['title']} ({scenario['participant_id']}) session {session_id} ==="
    )
    envelope = json.dumps(
        {
            "session_id": session_id,
            "participant_id": scenario["participant_id"],
            "scenario": key,
            "message": scenario["message"],
        }
    )
    print(f"[{LAB}] participant> {scenario['message']}")
    reply, response_id = send(envelope)
    decisions = list(scenario["auto_decisions"])
    if trace is not None:
        trace.update(
            {
                "session_id": session_id,
                "statuses": [],
                "resume_paths": [],
                "packet_attempts": [],
                "decisions": [],
            }
        )
    for _ in range(6):
        if trace is not None:
            trace["statuses"].append(reply.get("status"))
            trace["resume_paths"].append(reply.get("resume_path"))
            trace["packet_attempts"].append(
                reply.get("packet_attempts")
                or reply.get("packet", {}).get("packet_attempts")
            )
        if reply.get("status") != PENDING:
            break
        packet = reply.get("packet", {})
        assert_packet_contract(packet, scenario["expected_lob"])
        print(
            f"[{LAB}] {AGENT_NAME}> status={reply['status']} lob={packet.get('lob')} attempts={packet.get('packet_attempts')} "
            f"flags={packet.get('compliance_flags')} resume_path={reply.get('resume_path')}"
        )
        if restart:
            restart()  # the point of the exercise: the packet survives the process
        decision = (
            decisions.pop(0)
            if auto and decisions
            else ("approve" if auto else interactive_decider(reply))
        )
        if trace is not None:
            trace["decisions"].append(decision)
        print(f"[{LAB}] advisor> {decision}")
        reply, response_id = send(
            json.dumps({"session_id": session_id, "advisor": decision}), response_id
        )
    if reply.get("status") in {"approved", "declined"}:
        final = reply["packet"]
        decision = final.get("advisor_decision")
        assert_packet_contract(final, scenario["expected_lob"], decision)
        final["session_id"] = session_id
        save_packet(key, final)
        return final
    raise SystemExit(f"[{LAB}] {key} did not finish: {json.dumps(reply)[:400]}")


def demo(
    base: str | None = None,
    *,
    scenarios: tuple[str, ...] = ("S1", "S2", "S3"),
    auto: bool = False,
    deployed: bool = False,
    restart_between_turns: bool = False,
) -> dict[str, dict]:
    server: HostedProcess | None = None
    restart = None
    if deployed:
        send = deployed_turn
    else:
        if base is None:
            server = HostedProcess().start()
            base = LOCAL_BASE
            if restart_between_turns:

                def restart() -> None:
                    log(
                        "restarting the server between the participant turn and the advisor turn"
                    )
                    server.stop()
                    server.start()

        send = lambda text, prev=None: post_turn(base, text, prev)  # noqa: E731
    results = {}
    try:
        for key in scenarios:
            results[key] = run_scenario(key, send, auto=auto, restart=restart)
    finally:
        if server:
            server.stop()
    return results


# %% [markdown]
# This cell defines validated deployment preparation and version recording without creating cloud resources.
# %% Step 4.7 - Prepare source deployment
def deploy_commands(env: dict | None = None) -> str:
    """Return the quoted command for the explicit deployment cell."""
    from deployment import bash_deploy_block

    env = foundry_env.load_env() if env is None else env
    settings = {
        key: os.environ[key]
        for key in (
            "MARKETPLACE_KB_MCP_URL",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
        )
        if os.environ.get(key)
    }
    return bash_deploy_block(HOSTED_DIR, AGENT_NAME, "responses", env, settings)


def record_deployment(version: str, status: str = "active") -> dict:
    record = build(vendor=False, standalone=True)
    record["deployed"] = {
        "version": str(version),
        "status": status,
        "recorded_at": lab_helpers.now_iso(),
    }
    foundry_env.save_artifact(HOSTED_RECORD, record)
    log(f"recorded deployed version {version} ({status})")
    return record


# %% [markdown]
# ## YOUR TURN (10 min): revise instead of approve

# 1. Complete the cells above this section in order.
# 3. Run the next code cell.
#     - This run is automatic. Do not enter an advisor response.
#     - The client sends the S3 participant message, then `revise: add the IEP dates for turning 65 to open_questions`, then `approve`.
#     - The printed `advisor>` lines record automated client turns; they are not input prompts.
# 4. Confirm that the gate passes:
#     - `packet_attempts` is at least `2`.
#     - `open_questions` contains an IEP or Initial Enrollment Period question.

# If you changed `.env`, restart the notebook kernel first, then run all cells above this section again.

# This cell requests a revision and then approval, proving the handoff packet retains the added IEP question.
# %% Step 4.8 - Test the revision path
if "__file__" not in globals():
    build(standalone=True)
    revise_trace = {}
    with HostedProcess():
        revised_packet = run_scenario(
            "S3",
            lambda text, prev=None: post_turn(LOCAL_BASE, text, prev),
            auto=True,
            trace=revise_trace,
        )
    assert (
        revised_packet["packet_attempts"] >= 2
    ), "The revised packet did not increment packet_attempts."
    assert any(
        "IEP" in question.upper() or "INITIAL ENROLLMENT" in question.upper()
        for question in revised_packet["open_questions"]
    ), "The revised packet did not add the IEP question."

# %% [markdown]
# ## YOUR TURN (10 min): lose the process, keep the case

# 1. Complete the cells above this section in order.
# 3. Run the next code cell.
#     - This run is automatic. Do not enter an advisor response.
#     - The client sends the S2 participant message, stops and restarts the local server, then sends `approve`.
#     - The printed `advisor> approve` line records that automated client turn; it is not an input prompt.
# 4. Confirm that the gate passes:
#     - The resumed turn reports `resume_path=session_store`.
#     - A session JSON file exists under `artifacts/lab4/sessions/`.
#     - The final packet has `advisor_decision` set to `approve`.

# If you changed `.env`, restart the notebook kernel first, then run all cells above this section again.
# This cell restarts the local server between participant intake and advisor approval to verify session recovery.
# %% Step 4.9 - Test restart-safe sessions
if "__file__" not in globals():
    build(standalone=True)
    restart_trace = {}
    restart_server = HostedProcess().start()
    try:

        def restart_for_gate() -> None:
            restart_server.stop()
            restart_server.start()

        restarted_packet = run_scenario(
            "S2",
            lambda text, prev=None: post_turn(LOCAL_BASE, text, prev),
            auto=True,
            restart=restart_for_gate,
            trace=restart_trace,
        )
    finally:
        restart_server.stop()
    assert (
        "session_store" in restart_trace["resume_paths"]
    ), "The restarted turn did not use the session store."
    session_file = ARTIFACTS / "sessions" / f"{restart_trace['session_id']}.json"
    assert (
        session_file.is_file()
    ), f"The pending/final session record was not persisted at {session_file}."
    assert restarted_packet["advisor_decision"] == "approve"

# %% [markdown]
# ## YOUR TURN (5 min): make the compliance reviewer reject unsafe drafts

# 1. Open `hosted/marketplace_specialists.py`.
# 2. Add this sentence to `MARKETPLACE_INSTRUCTIONS`:
#     `Finish with the single plan you would pick.`
# 3. Save the file.
# 4. Complete the cells above this section in order.
# 6. Run the next code cell.
# 7. Confirm that the gate passes:
#     - The reviewer first reports `compliant=False`.
#     - The workflow sends `marketplace-guide` back for one revision.
#     - The final S1 packet is approved and passes the safety checks.
# 8. Remove the sentence you added and save the file.

# If you changed `.env`, restart the notebook kernel first, then run all cells above this section again.

# This cell tests your deliberately unsafe local draft and requires the compliance reviewer to reject and revise it.
# %% Step 4.10 - Test compliance review
if "__file__" not in globals():
    build(standalone=True)
    reviewer_server = HostedProcess().start()
    try:
        reviewer_packet = run_scenario(
            "S1",
            lambda text, prev=None: post_turn(LOCAL_BASE, text, prev),
            auto=True,
        )
    finally:
        reviewer_server.stop()
    reviewer_log = SERVER_LOG.read_text(encoding="utf-8", errors="replace")
    assert (
        "compliant=False" in reviewer_log
    ), "The reviewer did not reject the intentionally unsafe draft."
    assert (
        "sending marketplace-guide back for one revision" in reviewer_log
    ), "The one-revision route did not run."
    assert_packet_contract(reviewer_packet, "marketplace", "approve")

# %% [markdown]
# ## YOUR TURN (10 min): replace keyword routing with model classification

# 1. Open `hosted/marketplace_specialists.py`.
# 2. Add a builder for a `lob-classifier` agent:
#     - Return an `Agent`.
#     - Use `response_format=LobCall`.
#     - Provide short classification instructions and the shared compliance instructions.
#     - Do not add tools.
# 3. Add the new agent to `build_all()`.
# 4. Open `hosted/marketplace_workflow.py`.
# 5. Inspect `IntakeExecutor.start`: it already calls the optional `lob-classifier` before routing to specialists.
#    `build_workflow()` already passes `agents.get("lob-classifier")` to this executor; adding the agent to `build_all()` enables it.
# 6. Preserve the existing keyword fallback; no new fallback function is needed.
#     - Keep `classify_lob()` and the initial `lob = classify_lob(intake.message, participant)` assignment.
#     - A valid model response is parsed as `LobCall`, then `lob = classified.lob` replaces the keyword result.
#     - If the model call raises an exception or its response cannot be parsed as `LobCall`, keep the original keyword result.
#       The existing fallback branches log the failure; do not remove those messages.
#     - If no `lob-classifier` agent is configured, the keyword result is used directly.
# 7. Save both files.
# 8. Complete the cells above this section in order.
# 10. Run the next code cell.
# 11. Confirm that the ambiguous message
#      `My card was declined when I tried to pay for a prescription.`
#      is routed to `accounts`, not `both`.
# 12. Confirm that the advisor approval completes successfully.
#     Step 4.11 sends `approve` automatically; do not type an advisor response.
#     The notebook shows the triage result and prints `PASS Step 4.11` only after routing and approval checks succeed.
#
# For this message, the keyword fallback returns `both`: "my card" matches accounts and "prescription" matches marketplace.
# The model must identify the card-payment issue as `accounts`. This is task routing under an acceptance criterion,
# not model right-sizing or a token-cost comparison. Falling back keeps intake available, but does not pass this
# exercise's routing assertion.

# If you changed `.env`, restart the notebook kernel first, then run all cells above this section again.

# This cell verifies your model classifier routes the ambiguous card issue to accounts and completes advisor approval.
# %% Step 4.11 - Test triage classification
if "__file__" not in globals():
    build(standalone=True)
    classifier_session = f"classifier-{uuid.uuid4().hex[:8]}"
    classifier_message = "My card was declined when I tried to pay for a prescription."
    log(f"Step 4.11 participant> {classifier_message}")
    with HostedProcess():
        classifier_reply, classifier_response_id = post_turn(
            LOCAL_BASE,
            json.dumps(
                {
                    "session_id": classifier_session,
                    "participant_id": "P-1003",
                    "scenario": "classifier-gate",
                    "message": classifier_message,
                }
            ),
        )
        assert classifier_reply["status"] == PENDING, (
            f"Expected pending advisor approval, got {classifier_reply['status']}."
        )
        log(
            f"Step 4.11 triage result: lob={classifier_reply['packet']['lob']}, "
            f"status={classifier_reply['status']}"
        )
        assert (
            classifier_reply["packet"]["lob"] == "accounts"
        ), f"Expected accounts for the card-decline case, got {classifier_reply['packet']['lob']}."
        log("Step 4.11 advisor> approve (automatic)")
        classifier_final, _ = post_turn(
            LOCAL_BASE,
            json.dumps({"session_id": classifier_session, "advisor": "approve"}),
            classifier_response_id,
        )
    assert classifier_final["status"] == "approved", (
        f"Expected advisor approval to complete, got {classifier_final['status']}."
    )
    log(
        f"PASS Step 4.11: routed to {classifier_reply['packet']['lob']}; "
        f"advisor approval completed (status={classifier_final['status']})."
    )

# %% [markdown]
# ## Deploy the triage agent
#
# This cell deploys your saved triage package to Azure and displays its version status, which may incur charges.
# Restore the deliberately unsafe instruction before deployment; `PROJECT_RESOURCE_ID` must be configured.

# %% Step 4.12 - Deploy the triage agent
if "__file__" not in globals():
    build(standalone=True)
    subprocess.run(["bash", "-lc", deploy_commands()], cwd=HOSTED_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", AGENT_NAME], cwd=HOSTED_DIR, check=True)


# %% [markdown]
# This cell records the active triage version you inspected and checks a deployed handoff through advisor approval.
# Wait for active status and enter that version below before execution.
# %% Step 4.13 - Verify the deployed handoff
if "__file__" not in globals():
    DEPLOYED_VERSION = ""  # Set to the active version shown by the deployment cell.
    assert DEPLOYED_VERSION, "Enter the active Foundry version in DEPLOYED_VERSION."
    record_deployment(DEPLOYED_VERSION)
    demo(scenarios=("S2",), auto=True, deployed=True)

# %% [script-only]
def main(args: argparse.Namespace) -> None:
    if args.record_version:
        record_deployment(args.record_version, args.status)
        return
    if args.deploy:
        commands = deploy_commands()
        build(vendor=not args.no_vendor, standalone=True)
        print(
            f"\n[{LAB}] deploy from source (commands only; no cloud action was run):\n{commands}"
        )
        return
    log(
        f"data check: {marketplace_data.get_participant('P-1005').get('first_name', '?')} (P-1005) is in data/participants.json"
    )
    build(vendor=not args.no_vendor, standalone=args.standalone)
    if args.skip_demo:
        return
    scenarios = tuple(SCENARIOS) if args.scenario == "all" else (args.scenario,)
    demo(
        args.base,
        scenarios=scenarios,
        auto=args.auto_approve,
        deployed=args.deployed,
        restart_between_turns=args.restart_between_turns,
    )
    log(
        "done. Checkpoint: paste S3.json's open_questions, compliance_flags and advisor_decision in the room chat."
    )


if __name__ == "__main__" and "__file__" in globals():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", choices=["S1", "S2", "S3", "all"], default="all")
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="scripted advisor decisions (catch-up, CI)",
    )
    parser.add_argument(
        "--restart-between-turns",
        action="store_true",
        help="kill and restart the server before each advisor turn",
    )
    parser.add_argument("--skip-demo", action="store_true")
    parser.add_argument("--no-vendor", action="store_true")
    parser.add_argument(
        "--standalone", action="store_true", help="do not require artifacts/lab3"
    )
    parser.add_argument(
        "--base", default=None, help="talk to an already running server"
    )
    parser.add_argument(
        "--deployed", action="store_true", help="talk to the version Foundry runs"
    )
    parser.add_argument("--deploy", action="store_true", help="print the azd commands")
    parser.add_argument("--record-version", default=None)
    parser.add_argument("--status", default="active")
    main(parser.parse_args())
