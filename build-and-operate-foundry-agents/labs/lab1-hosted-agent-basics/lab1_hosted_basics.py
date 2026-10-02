# %% [markdown]
# # Lab 1: Hosted agent basics
#
# **The Healthcare Marketplace concierge as a Foundry Hosted Agent (Responses protocol): written intent, bounded tools, and human decision ownership.**
#
# |  | Details |
# | --- | --- |
# | Goal | Build, run, and call the smallest complete hosted agent: Agent Framework `Agent` + `FoundryChatClient` + three `@tool` functions over the systems of record + the shared compliance block, served by `ResponsesHostServer`. Run it locally on port 8088, chat S1 and S2 through POST `/responses`, then deploy the same folder from source with `azd ai agent init` + `azd up` and invoke the version. |
# | Inputs | Root `.env` (`FOUNDRY_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `PROJECT_RESOURCE_ID` for `--deploy`); `common/` and `data/` (vendored into `hosted/` by `build()`) |
# | Outputs | `labs/artifacts/lab1/hosted.json` (agent name, protocol, model, endpoints, deployed version), `labs/artifacts/lab1/transcripts.md` (S1 and S2, PII-redacted), and `hosted_local.log` |
# | Time | 60 min (teach 10, demo 10, do 35, checkpoint 5) |
#
# **How to run code**
#
# |  | Command |
# | --- | --- |
# | Run cell by cell | Open `lab1_walkthrough.ipynb` (this file), or use the `# %%` cells in VS Code. |
# | Run top to bottom | `python lab1_hosted_basics.py` |
# | Skip the local demo or use another endpoint | `python lab1_hosted_basics.py --skip-demo` or `python lab1_hosted_basics.py --base http://localhost:8088` |
# | Call the deployed agent | `python lab1_hosted_basics.py --deployed` |
# | Print the azd commands | `python lab1_hosted_basics.py --deploy` |
# | After `azd up`, store the version | `python lab1_hosted_basics.py --record-version 2` |
#
# **Where this runs.** This notebook is the learner's cockpit: it runs on your workstation (dev container or
# venv), vendors `common/` and `data/` into `hosted/`, starts `hosted/main.py` as a local process on port 8088,
# calls `POST /responses`, and prints the azd commands that deploy the very same folder to Microsoft Foundry.
# `hosted/main.py` is the product: Foundry builds a container from the ZIP azd uploads, runs it, scales it and
# gives it an identity. Nothing customer-facing runs in this notebook.
#
# **Checkpoint artifact.** `labs/artifacts/lab1/hosted.json` (agent `healthcare-marketplace-concierge-hosted`, protocol, model,
# deployed version once you ran `azd up`) and `labs/artifacts/lab1/transcripts.md`. Lab 2 starts from hosted.json.
#
# ## Before the first run (dev-container Bash)
#
# Follow the workshop SETUP.md first: reopen the repository in its dev container, configure the root .env,
# and sign in inside the container. Python 3.14 and the pinned workstation packages are already installed.
# Select `/usr/local/bin/python` as the notebook kernel.
#
# ### **If this notebook is already open in VS Code**
#
# Keep using this notebook and its selected kernel. **Do not run the JupyterLab command below.**
# It starts a separate JupyterLab server and may open a browser tab; it does not connect to the notebook session
# already open in VS Code.
#
# ### Optional: open a separate JupyterLab session in a browser
#
# Run these commands in a Bash terminal—not in a Python code cell—only if you want to open this notebook
# in a separate JupyterLab session:
#
# ```bash
# cd /workspaces/agentic-ai-immersion/build-and-operate-foundry-agents/labs/lab1-hosted-agent-basics
# python -m jupyter lab lab1_walkthrough.ipynb
# ```
#
# %% [markdown]
# Shell commands use the container filesystem. Hosted deployment remains an explicit terminal action.
#
# %% Step 1.1 - Imports and paths
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # workshop root (common/ and data/ live here)
LABS_DIR = ROOT / "labs"
LAB_DIR = Path(__file__).resolve().parent
for folder in (ROOT, LABS_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, guardrails, marketplace_data, model_resilience, resource_names  # noqa: E402

import lab_helpers  # noqa: E402

LAB = "lab1"
ENV = foundry_env.load_env()
AGENT_NAME = resource_names.name(resource_names.HOSTED_CONCIERGE, ENV)
HOSTED_DIR = LAB_DIR / "hosted"
ARTIFACTS = lab_helpers.artifact_path(LAB)
HOSTED_RECORD = ARTIFACTS / "hosted.json"
TRANSCRIPTS = ARTIFACTS / "transcripts.md"
SERVER_LOG = ARTIFACTS / "hosted_local.log"
PORT = int(os.environ.get("MARKETPLACE_HOSTED_PORT", "8088"))
LOCAL_BASE = f"http://localhost:{PORT}"


def log(message: str) -> None:
    print(f"[{LAB}] {message}", flush=True)


# %% Step 1.2 - Define the workshop scenarios
SCENARIOS: dict[str, dict] = {
    "S1": {"participant_id": "P-1001", "title": "AEP shopper (Evelyn Marsh)",
           "turns": ["When can I change my plan this year? I am on MA-CONTOSO-HMO-01 and I would like a lower drug "
                     "cost for atorvastatin while keeping my cardiologist.",
                     "Just tell me which plan I should pick."]},
    "S2": {"participant_id": "P-1003", "title": "Denied claim (Harold Bing)",
           "turns": ["My claim CLM-9003 was denied. What is my HRA balance, and what does the account show about that claim?"]},
}


def first_turn(scenario: dict) -> str:
    return f"{lab_helpers.identity_line(scenario['participant_id'])} {scenario['turns'][0]}"


# %% Step 1.3 - Build the hosted package
def build(*, vendor: bool = True) -> dict:
    """Prepare the flat deployable folder and record what Lab 2 needs. Never calls Azure."""
    env = foundry_env.load_env()
    resource_names.suffix(env, required=True)
    counts: dict[str, int] = {}
    if vendor:
        prepare = lab_helpers.load_lab_module(f"{LAB_DIR.name}/hosted/prepare.py")
        counts = prepare.vendor()
    previous = json.loads(HOSTED_RECORD.read_text(encoding="utf-8")) if HOSTED_RECORD.exists() else {}
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
        "tools": ["get_participant", "get_enrollment_window", "get_hra_account"],
        "vendored": counts or previous.get("vendored", {}),
        "deployed": previous.get("deployed") or {"version": None, "status": "not deployed", "recorded_at": None},
        "built_at": lab_helpers.now_iso(),
    }
    foundry_env.save_artifact(HOSTED_RECORD, record)
    log(f"wrote {HOSTED_RECORD.relative_to(LABS_DIR)} (agent {AGENT_NAME}, model {record['model']}, "
        f"deployed version {record['deployed']['version'] or 'none yet'})")
    return record


# %% Step 1.4 - Define the local hosted server
class HostedProcess:
    """Start and stop hosted/main.py. Logs go to artifacts/lab1/hosted_local.log so the room can read them."""

    def __init__(self, hosted_dir: Path = HOSTED_DIR, port: int = PORT, log_path: Path = SERVER_LOG):
        self.hosted_dir, self.port, self.log_path = hosted_dir, port, log_path
        self.process: subprocess.Popen | None = None

    def start(self, timeout: float = 90.0) -> "HostedProcess":
        env = {**os.environ, **foundry_env.load_env(), "MARKETPLACE_HOSTED_PORT": str(self.port), "PYTHONUNBUFFERED": "1"}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, str(self.hosted_dir / "main.py")], cwd=str(self.hosted_dir),
                                        env=env, stdout=handle, stderr=subprocess.STDOUT)
        log(f"started hosted/main.py (pid {self.process.pid}) on port {self.port}; log -> {self.log_path.relative_to(LABS_DIR)}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise SystemExit(f"[{LAB}] hosted/main.py exited early (code {self.process.returncode}). Read {self.log_path}")
            with socket.socket() as probe:
                probe.settimeout(1.0)
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    log("server is accepting connections")
                    return self
            time.sleep(1.0)
        self.stop()
        raise SystemExit(f"[{LAB}] server did not open port {self.port} within {timeout:.0f}s. Read {self.log_path}")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            log(f"stopped hosted/main.py (pid {self.process.pid})")


# %% Step 1.5 - Call the Responses protocol
def output_text(payload: dict) -> str:
    """output_text when the server includes it, else the text parts of the output message items."""
    if payload.get("output_text"):
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts)


def post_responses(base: str, text: str, *, previous_response_id: str | None = None, session_id: str | None = None) -> dict:
    """POST /responses with the OpenAI Responses request shape. Returns {"text", "id", "raw"}.

    Multi-turn: the OpenAI Responses way is previous_response_id (the id of the last response). The host server
    may also accept a session identifier that maps to its own session; we send both when given.
    """
    import httpx

    # VERIFY against https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents before delivery:
    # the exact path (/responses) and whether ResponsesHostServer surfaces a session/conversation id in the
    # response (for example a `conversation` field or a header) or relies only on previous_response_id.
    body: dict = {"input": text, "stream": False}
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    if session_id:
        body["session_id"] = session_id                  # VERIFY: request field name for the host's session
    response = httpx.post(f"{base.rstrip('/')}/responses", json=body, timeout=180.0)
    response.raise_for_status()
    payload = response.json()
    model_resilience.ensure_response_succeeded(payload, LAB)
    return {"text": output_text(payload), "id": payload.get("id"), "raw": payload}


def call_deployed(text: str, *, previous_response_id: str | None = None, store: bool = True) -> dict:
    """Call the version Foundry runs through its agent-specific Responses endpoint."""
    log(f"calling deployed {AGENT_NAME} (store={store}; 120s network timeout; SDK retries disabled)")
    kwargs = {"previous_response_id": previous_response_id} if previous_response_id else {}
    with foundry_env.get_project_client() as project:
        with project.get_openai_client(agent_name=AGENT_NAME).with_options(
            timeout=120.0, max_retries=0,
        ) as client:
            response = client.responses.create(input=text, store=store, **kwargs)
    return {"text": response.output_text, "id": getattr(response, "id", None), "raw": None}


# %% Step 1.6 - Define the local demo
def run_scenario(key: str, scenario: dict, send) -> list[dict]:
    log(f"=== {key} {scenario['title']} ({scenario['participant_id']}) ===")
    turns, previous_id = [], None
    for index, text in enumerate(scenario["turns"]):
        user_text = first_turn(scenario) if index == 0 else text
        print(f"[{LAB}] participant> {user_text}")
        result = send(user_text, previous_response_id=previous_id)
        previous_id = result["id"] or previous_id
        report = lab_helpers.guardrail_report(result["text"])
        print(f"[{LAB}] {AGENT_NAME}> {result['text']}\n[{LAB}] checks: {lab_helpers.fmt_checks(report)}")
        turns.append({"user": user_text, "agent": result["text"], "response_id": result["id"], "checks": report})
    return turns


def write_transcripts(results: dict[str, list[dict]], target: str) -> Path:
    lines = [f"# Lab 1 transcripts: {AGENT_NAME} ({target})", "",
             f"Generated {lab_helpers.now_iso()}. Text passed through guardrails.redact_pii before writing.", ""]
    for key, turns in results.items():
        lines += [f"## {key}: {SCENARIOS[key]['title']}", ""]
        for turn in turns:
            lines += [f"**Participant:** {guardrails.redact_pii(turn['user'])}", "",
                      f"**{AGENT_NAME}:** {guardrails.redact_pii(turn['agent'])}", "",
                      f"_checks: {lab_helpers.fmt_checks(turn['checks'])}_", ""]
    foundry_env.save_artifact(TRANSCRIPTS, "\n".join(lines) + "\n")
    log(f"wrote {TRANSCRIPTS.relative_to(LABS_DIR)}")
    return TRANSCRIPTS


def demo(base: str | None = None, *, deployed: bool = False, scenarios: tuple[str, ...] = ("S1", "S2")) -> Path:
    """Chat S1 and S2. Default: start hosted/main.py, talk to it, stop it. --base: talk to a server you started.
    --deployed: talk to the version Foundry runs."""
    server: HostedProcess | None = None
    if deployed:
        send, target = call_deployed, "deployed version through the Foundry project"
    else:
        if base is None:
            server = HostedProcess().start()
            base = LOCAL_BASE
        send, target = (lambda text, **kw: post_responses(base, text, **kw)), f"local {base}"
    try:
        results = {key: run_scenario(key, SCENARIOS[key], send) for key in scenarios}
    finally:
        if server:
            server.stop()
    return write_transcripts(results, target)


# %% Step 1.7 - Prepare source deployment
def deploy_commands(env: dict | None = None) -> str:
    """Return a quoted Bash command; deployment remains an explicit terminal action."""
    from deployment import bash_deploy_block
    env = foundry_env.load_env() if env is None else env
    settings = {key: os.environ[key] for key in (
        "MARKETPLACE_KB_MCP_URL", "MARKETPLACE_REDIS_URL", "APPLICATIONINSIGHTS_CONNECTION_STRING"
    ) if os.environ.get(key)}
    return bash_deploy_block(HOSTED_DIR, AGENT_NAME, "responses", env, settings)


def record_deployment(version: str, status: str = "active") -> dict:
    record = build(vendor=False)
    record["deployed"] = {"version": str(version), "status": status, "recorded_at": lab_helpers.now_iso()}
    foundry_env.save_artifact(HOSTED_RECORD, record)
    log(f"recorded deployed version {version} ({status}) in {HOSTED_RECORD.relative_to(LABS_DIR)}")
    return record


# %% [markdown]
# ## YOUR TURN (5 min): add a `get_sponsor` tool
#
# 1. State the intended outcome: use the sponsor tool to name Northwind and the $3,600 annual HRA for P-1001
#    without inventing facts or recommending a plan. Then open `hosted/main.py`.
# 2. Wrap `marketplace_data.get_sponsor(sponsor_id)` with `@tool`, following the three existing tool functions.
# 3. Append the new function to `TOOLS`, then save the file.
# 4. Run the next cell. `build()` vendors your saved code, starts a fresh local server, asks for P-1001's sponsor
#    and annual HRA amount, checks the answer, and always stops the server.
#
# A passing run prints an answer containing **Northwind** and **$3,600**. If it fails, inspect
# `labs/artifacts/lab1/hosted_local.log`.

# %% Step 1.8 - Test the first local exercise
if "__file__" not in globals():
    build()
    server = HostedProcess().start()
    try:
        result = post_responses(
            LOCAL_BASE,
            f"{lab_helpers.identity_line('P-1001')} "
            "Who is my plan sponsor and how much is the HRA for the year?",
        )
        print(result["text"])
        assert "Northwind" in result["text"], "The response did not include P-1001's plan sponsor."
        assert "$3,600" in result["text"], "The response did not include P-1001's annual HRA amount."
    finally:
        server.stop()

# %% [markdown]
# ## YOUR TURN (10 min): tighten an instruction and ship a new version
#
# 1. In `hosted/main.py`, change rule 3 of `ROLE_INSTRUCTIONS` so the agent **always names the applicable
#    enrollment window** when it offers a licensed benefit advisor.
# 2. Save the file, then run the next cell. It vendors the change, starts a fresh local server, runs S1, writes
#    the transcript, and verifies that the recommendation-refusal turn names **AEP**.
# 3. After the local assertion passes, run the **Print Bash deployment command** cell below.
#    Copy the single command into the dev-container Bash terminal. The script checks the azd version and Foundry
#    data-plane access before it creates files, then changes to the correct folder and stops on failure.
# 4. Wait for the new version to become **active** in Foundry, then run
#    `record_deployment("<version>")` in a new notebook cell, replacing `<version>` with the active version number.
#
# Foundry creates a new version only when the uploaded ZIP or definition changes. Keep the old version: Lab 4
# uses version history for audit and rollback.

# %% Step 1.9 - Test the second local exercise
if "__file__" not in globals():
    build()
    server = HostedProcess().start()
    try:
        send_local = lambda text, **kwargs: post_responses(LOCAL_BASE, text, **kwargs)
        turns = run_scenario("S1", SCENARIOS["S1"], send_local)
        write_transcripts({"S1": turns}, f"local {LOCAL_BASE}")
        assert "AEP" in turns[1]["agent"], "S1 turn 2 did not mention AEP."
    finally:
        server.stop()

# %% Step 1.10 - Print the Bash deployment command
if "__file__" not in globals():
    print(deploy_commands())

# %% [markdown]
# ## YOUR TURN (5 min): call the deployed endpoint
#
# Complete the deployment and `record_deployment("<version>")` steps above before running the next cell. The call
# uses the agent-specific Responses endpoint and verifies that the active hosted version returns
# a non-empty answer. This single-turn connectivity check uses `store=False`: it does not need a
# persisted response or `previous_response_id`. It verifies inference and tools, not Foundry response
# storage. The multi-turn demo keeps storage enabled so its response chain continues to work.
#
# Check status from the initialized deployment folder, not the repository root:
#
# ```bash
# cd /workspaces/agentic-ai-immersion/build-and-operate-foundry-agents/labs/lab1-hosted-agent-basics/hosted
# azd ai agent show healthcare-marketplace-concierge-hosted
# ```
#
# An active version can still fail during a request. Model 429s can cause server-side retry delays;
# Foundry response-storage failures can return 500 after the model has already answered.
# The client disables automatic retries and uses a 120-second network timeout to expose failures.
#
# If the call returns **403**, first read the response: a private-endpoint message is a network-path issue;
# otherwise assign Foundry Agent Consumer or Foundry User at project scope. If it returns
# **424 session_not_ready**, the container is still starting or failed at startup; open the active version's
# logstream in Foundry, fix the startup error, and deploy a new version.

# %% Step 1.11 - Test the deployed version
if "__file__" not in globals():
    result = call_deployed("Hi, this is P-1005, ZIP 84010. What is my enrollment window?", store=False)
    print(result["text"])
    assert result["text"].strip(), "The deployed agent returned an empty answer."


# %% [markdown]
# ## Script-only entry point - skip in Jupyter
#
# **Running this notebook cell by cell? Skip the next cell.** The earlier cells provide the notebook path.
# The next cell is only the command-line entry point for running this lab's `.py` file as one program.
# Its command-line invocation is guarded in the generated notebook; running the cell does not launch the lab.
# For script mode instead, run `python lab1_hosted_basics.py --help` in a Bash terminal from this lab's folder and choose the desired options.

# %% Step 1.12 - Script-only entry point (skip in Jupyter)
def main(args: argparse.Namespace) -> None:
    if args.record_version:
        record_deployment(args.record_version, args.status)
        return
    if args.deploy:
        build(vendor=not args.no_vendor)
        print(f"\n[{LAB}] deploy from source (needs Foundry Project Manager at project scope):\n{deploy_commands()}")
        return
    log(f"data check: {marketplace_data.get_participant('P-1001').get('first_name', '?')} (P-1001) is in data/participants.json")
    build(vendor=not args.no_vendor)
    if args.skip_demo:
        return
    demo(args.base, deployed=args.deployed)
    log("done. Checkpoint: paste the S1 turn 2 answer (the refusal to pick a plan) and your hosted.json in the room chat.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-demo", action="store_true", help="only vendor and write hosted.json")
    parser.add_argument("--no-vendor", action="store_true", help="do not re-copy common/ and data/ into hosted/")
    parser.add_argument("--base", default=None, help="talk to an already running server, e.g. http://localhost:8088")
    parser.add_argument("--deployed", action="store_true", help="run S1 and S2 against the version Foundry runs")
    parser.add_argument("--deploy", action="store_true", help="print the Bash deploy command with your .env values")
    parser.add_argument("--record-version", default=None, help="store the deployed version number in hosted.json")
    parser.add_argument("--status", default="active", help="version status to record (default active)")
    main(parser.parse_args())
