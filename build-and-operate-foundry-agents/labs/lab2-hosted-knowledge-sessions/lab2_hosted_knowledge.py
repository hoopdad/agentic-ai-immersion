# %% [markdown]
# # Lab 2: Hosted knowledge and durable sessions
#
# **Technology focus.** This lab uses Microsoft Foundry (Foundry IQ; Search; MCP) and Microsoft Agent Framework
# (`MCPStreamableHTTPTool`; history).
#
# **Building upon the Healthcare Marketplace concierge from Lab 1: reusable governed knowledge and conversation continuity, with separate evidence for each.**
#
# |  | Details |
# | --- | --- |
# | Goal | Build the Foundry IQ knowledge base, run `healthcare-marketplace-concierge-hosted` v2 locally, prove a file-backed local process restart, and optionally configure Azure Blob history for deployment. |
# | Inputs | `labs/artifacts/lab1/hosted.json`; `data/knowledge`; `.env` with the explicit Azure settings in this lab's `README.md`. |
# | Outputs | `labs/artifacts/lab2/knowledge.json`, `hosted.json`, `sessions/`, `transcripts.md`, and `hosted_local.log` |
# | Time | 60 min (teach 10, demo 10, do 35, checkpoint 5) |
#
# **How to run code**
#
# |  | Command |
# | --- | --- |
# | Run cell by cell | Open `lab2_walkthrough.ipynb` (this file), or use the `# %%` cells in VS Code. |
# | Run top to bottom | `python lab2_hosted_knowledge.py` |
# | Build resources and package only | `python lab2_hosted_knowledge.py --build-only` |
# | Reuse existing Lab 2 artifacts for the demo | `python lab2_hosted_knowledge.py --demo-only` |
# | Print the azd commands | `python lab2_hosted_knowledge.py --deploy` |
# | After `azd up`, store version 2 | `python lab2_hosted_knowledge.py --record-version 2` |
#
# **Where this runs.** The notebook and driver run on your workstation. They build Azure AI Search resources,
# vendor the flat hosted package, start `hosted/main.py`, and call `POST /responses`. Foundry runs the same
# `hosted/main.py` in the deployed container.
#
# **Truthful session boundary.** Locally, the file message store plus the hosting runtime's local state store
# proves continuity after killing and restarting the Python process on one workstation. In Foundry, the hosting
#   runtime persists the AgentSession, but shared message history must use Azure Blob;
#   a file inside a container is not a scale-out or version-roll store.
#
# **Blob endpoint and identity.** `MARKETPLACE_BLOB_STORAGE_URL` is the storage account's Blob endpoint, such as
# `https://<storage-account>.blob.core.windows.net` (no container path, key, or identity); the container name is
# configured separately. `DefaultAzureCredential` uses the signed-in developer locally. A deployed Foundry
# hosted agent uses its dedicated Microsoft Entra agent identity, not a user-assigned managed identity. Grant
# that agent identity **Storage Blob Data Contributor** on the storage account or container.
#
# **Lab path and prerequisites.**
#
# - **Required:** Complete Lab 1 first. This lab reads `labs/artifacts/lab1/hosted.json`. If you joined after
#   Lab 1, run `python ../catch_up.py --through 1` from this lab folder.
# - **Optional:** Deploying version 2 and Azure Blob Storage are optional. Local history uses the configured
#   Azurite emulator or files; deployed shared history requires an Azure Blob URL.
# - **From Lab 1:** Keep the same dev-container setup, kernel, Foundry project, Responses protocol, agent name,
#   local port, and source-deployment workflow. Lab 1 introduced those steps; this lab extends that agent.
#
# **Checkpoint artifacts.** `artifacts/lab2/knowledge.json`, `artifacts/lab2/hosted.json`,
# `artifacts/lab2/sessions/`, `artifacts/lab2/transcripts.md`, and `artifacts/lab2/hosted_local.log`.
#
# %% [markdown]
# ## Before the first run (dev-container Bash)
#
# If you completed Lab 1 in this dev container, keep using its `/usr/local/bin/python` kernel and signed-in
# terminal. Add the Lab 2 Search values and any optional history-store settings documented in this lab's `README.md`
# to the root `.env`.
# Otherwise, follow the workshop `SETUP.md` before continuing.
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
# cd /workspaces/agentic-ai-immersion/build-and-operate-foundry-agents/labs/lab2-hosted-knowledge-sessions
# python -m jupyter lab lab2_walkthrough.ipynb
# ```
#
# %% [markdown]
# Shell commands use the container filesystem. Hosted deployment remains an explicit terminal action.
#
# %% Step 2.1 - Imports and paths
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = ROOT / "labs"
LAB_DIR = Path(__file__).resolve().parent
for folder in (ROOT, LABS_DIR, LAB_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from common import foundry_env, guardrails, model_resilience, resource_names  # noqa: E402

from azure.identity import AzureCliCredential  # noqa: E402
from azure.search.documents.indexes import SearchIndexClient  # noqa: E402

import knowledge_base  # noqa: E402
import lab_helpers as helpers  # noqa: E402

ENV = foundry_env.load_env()
MODEL = helpers.pick_model(ENV)
LAB = "lab2"
AGENT_NAME = resource_names.name(resource_names.HOSTED_CONCIERGE, ENV)
HOSTED_DIR = LAB_DIR / "hosted"
ARTIFACTS = helpers.artifact_path(LAB)
HOSTED_RECORD = ARTIFACTS / "hosted.json"
TRANSCRIPT_PATH = ARTIFACTS / "transcripts.md"
SERVER_LOG = ARTIFACTS / "hosted_local.log"
MESSAGE_STORE_DIR = ARTIFACTS / "message_store"
SESSION_DIR = ARTIFACTS / "sessions"
AGENTSERVER_STATE_ROOT = ARTIFACTS / "agentserver_state"
DEFAULT_PORT = int(os.environ.get("MARKETPLACE_HOSTED_PORT", "8088"))
DEFAULT_SESSION_ID = "S1-evelyn"


def log(message: str) -> None:
    print(f"[{LAB}] {message}", flush=True)




# %% Step 2.2 - Build knowledge resources and the hosted package
def container_environment(knowledge: dict, env: dict | None = None) -> dict[str, str]:
    env = env or ENV
    values = {
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": MODEL,
        "MARKETPLACE_KB_MCP_URL": knowledge["mcp_endpoint"],
        "MARKETPLACE_TODAY": env.get("MARKETPLACE_TODAY", "2026-10-06"),
    }
    blob_url = env.get("MARKETPLACE_BLOB_STORAGE_URL", "").strip()
    if blob_url:
        values["MARKETPLACE_BLOB_STORAGE_URL"] = blob_url
        values["MARKETPLACE_BLOB_STORAGE_CONTAINER"] = env.get(
            "MARKETPLACE_BLOB_STORAGE_CONTAINER", "marketplace-history"
        )
    return values


def build(skip_connection: bool = False) -> dict:
    resource_names.suffix(ENV, required=True)
    lab1 = helpers.require_artifact("lab1", "hosted.json", through=1, caller=LAB)
    credential = AzureCliCredential()
    index_client = SearchIndexClient(endpoint=knowledge_base.search_endpoint(), credential=credential)
    embed = knowledge_base.make_embedder(credential)
    counts = {
        name: knowledge_base.build_index(index_client, credential, name, contexts, embed)
        for name, contexts in knowledge_base.INDEXES.items()
    }
    knowledge_base.build_knowledge_sources(index_client)
    knowledge_base.build_knowledge_base(index_client)
    knowledge = knowledge_base.save_build_artifact(lab1, counts, credential, skip_connection)

    prepare = helpers.load_lab_module(f"{LAB_DIR.name}/hosted/prepare.py")
    vendored = prepare.vendor()
    previous = json.loads(HOSTED_RECORD.read_text(encoding="utf-8")) if HOSTED_RECORD.exists() else {}
    env_for_container = container_environment(knowledge)
    info = {
        "lab": LAB,
        "agent_name": AGENT_NAME,
        "version_label": "v2 (knowledge + sessions)",
        "protocol": "responses",
        "runtime": "python_3_14",
        "entry_point": "main.py",
        "hosted_dir": str(HOSTED_DIR.relative_to(ROOT)),
        "local_endpoint": f"http://localhost:{DEFAULT_PORT}/responses",
        "model": MODEL,
        "tools": [
            "get_participant",
            "get_enrollment_window",
            "get_hra_account",
            "search_plans",
            "compare_plans",
            "knowledge_base_retrieve (MCP healthcare-marketplace-kb)",
        ],
        "vendored": vendored,
        "env_for_container": env_for_container,
        "session_behavior": {
            "local": "message history uses configured Azure Blob, Azurite, or files; AgentServer state is local",
            "deployed": "Azure Blob message history across replicas and versions"
            if env_for_container.get("MARKETPLACE_BLOB_STORAGE_URL")
            else "single-container file history only; configure Azure Blob before claiming continuity",
        },
        "deployed": previous.get("deployed") or {"version": None, "status": "not deployed", "recorded_at": None},
        "built_at": helpers.now_iso(),
    }
    foundry_env.save_artifact(HOSTED_RECORD, info)
    log(f"saved {HOSTED_RECORD.relative_to(LABS_DIR)}")
    return info


if "__file__" not in globals():
    hosted = build()


# %% Step 2.3 - Prepare the deployment command
def deploy_commands(env: dict | None = None, hosted: dict | None = None) -> str:
    """Return a Bash deployment command without changing Azure or the local package."""
    from deployment import bash_deploy_block, validate_cloud_settings
    env = foundry_env.load_env() if env is None else env
    if hosted is None:
        if not HOSTED_RECORD.exists():
            raise SystemExit(f"[{LAB}] Run --build-only before printing deployment commands.")
        hosted = json.loads(HOSTED_RECORD.read_text(encoding="utf-8"))
    deployment_env = dict(env)
    if hosted.get("model"):
        deployment_env["AZURE_AI_MODEL_DEPLOYMENT_NAME"] = hosted["model"]
    settings = hosted.get("env_for_container", {})
    validate_cloud_settings(settings)
    block = bash_deploy_block(HOSTED_DIR, AGENT_NAME, "responses", deployment_env, settings)
    if env.get("MARKETPLACE_AZURITE_CONNECTION_STRING"):
        block += "\n# Local Azurite is never sent to the cloud deployment."
    if not settings.get("MARKETPLACE_BLOB_STORAGE_URL"):
        block += "\n# WARNING: No shared cloud message store is configured; deployed history is file-backed."
    return block


def record_deployment(version: str, status: str = "active") -> dict:
    if not HOSTED_RECORD.exists():
        raise SystemExit(f"[{LAB}] {HOSTED_RECORD.relative_to(LABS_DIR)} does not exist; run --build-only first")
    record = json.loads(HOSTED_RECORD.read_text(encoding="utf-8"))
    record["deployed"] = {"version": str(version), "status": status, "recorded_at": helpers.now_iso()}
    foundry_env.save_artifact(HOSTED_RECORD, record)
    log(f"recorded deployed version {version} ({status})")
    return record


# %% Step 2.4 - Define a local hosted process
def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


class HostedProcess:
    def __init__(
        self,
        knowledge: dict,
        *,
        port: int = DEFAULT_PORT,
        log_path: Path = SERVER_LOG,
        env_overrides: dict[str, str | None] | None = None,
    ):
        self.knowledge = knowledge
        self.port = port
        self.log_path = log_path
        self.env_overrides = env_overrides or {}
        self.process: subprocess.Popen | None = None
        self._log_handle = None

    def _tail(self, lines: int = 30) -> str:
        if not self.log_path.exists():
            return "(log file was not created)"
        return "\n".join(self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

    def start(self, timeout: float = 90.0) -> "HostedProcess":
        if port_open(self.port):
            raise SystemExit(f"[{LAB}] port {self.port} is already in use; stop the other hosted/main.py process")
        env = {
            **os.environ,
            **{key: value for key, value in ENV.items() if value},
            "MARKETPLACE_KB_MCP_URL": self.knowledge.get("mcp_endpoint", ""),
            "MARKETPLACE_HOSTED_PORT": str(self.port),
            "MARKETPLACE_MESSAGE_STORE_DIR": str(MESSAGE_STORE_DIR),
            "MARKETPLACE_SESSION_DIR": str(SESSION_DIR),
            "AGENTSERVER_STATE_ROOT": str(AGENTSERVER_STATE_ROOT),
            "PYTHONUNBUFFERED": "1",
        }
        env.pop("MARKETPLACE_REDIS_URL", None)
        for key, value in self.env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = str(value)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = self.log_path.open("a", encoding="utf-8")
        self._log_handle.write(f"\n--- start {helpers.now_iso()} port={self.port} ---\n")
        self._log_handle.flush()
        self.process = subprocess.Popen(
            [sys.executable, str(HOSTED_DIR / "main.py")],
            cwd=str(HOSTED_DIR),
            env=env,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
        )
        log(f"started hosted/main.py pid {self.process.pid} on port {self.port}; log -> {self.log_path.relative_to(LABS_DIR)}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                self._close_log()
                raise SystemExit(
                    f"[{LAB}] hosted/main.py exited early with code {self.process.returncode}. "
                    f"Log: {self.log_path}\n{self._tail()}"
                )
            if port_open(self.port):
                return self
            time.sleep(1)
        self.stop()
        raise SystemExit(f"[{LAB}] hosted/main.py did not open port {self.port} in {timeout:.0f}s.\n{self._tail()}")

    def _close_log(self) -> None:
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
            log(f"stopped hosted/main.py pid {self.process.pid} (exit {self.process.returncode})")
        self._close_log()


# %% Step 2.5 - Use the Responses conversation contract
def output_text(payload: dict) -> str:
    if payload.get("output_text"):
        return payload["output_text"]
    return "\n".join(
        content.get("text", "")
        for item in payload.get("output", []) or []
        for content in item.get("content", []) or []
        if content.get("type") in {"output_text", "text"} and content.get("text")
    )


def ask(
    port: int,
    text: str,
    session_id: str | None,
    previous_response_id: str | None = None,
) -> tuple[str, dict]:
    import httpx
    from opentelemetry.propagate import inject

    body: dict = {"input": text, "stream": False}
    if session_id:
        body["conversation"] = session_id
    elif previous_response_id:
        body["previous_response_id"] = previous_response_id
    headers: dict[str, str] = {}
    inject(headers)
    response = httpx.post(f"http://localhost:{port}/responses", json=body, headers=headers, timeout=180.0)
    response.raise_for_status()
    payload = response.json()
    model_resilience.ensure_response_succeeded(payload, LAB)
    text_out = output_text(payload)
    if not text_out.strip():
        raise RuntimeError(f"[{LAB}] empty response payload: {json.dumps(payload)[:500]}")
    return text_out, payload


def record_turn(store, session_id: str, participant_id: str, payload: dict, agent_version: str) -> None:
    rec = store.get(session_id) or helpers.SessionRecord(
        session_id=session_id,
        participant_id=participant_id,
        agent_name=AGENT_NAME,
        agent_version=agent_version,
        conversation_id=session_id,
        last_response_id=None,
        turn_count=0,
        updated_at=helpers.now_iso(),
        notes={"lab": LAB},
    )
    rec.conversation_id = session_id
    rec.last_response_id = payload.get("id")
    rec.turn_count += 1
    rec.updated_at = helpers.now_iso()
    store.put(rec)


# %% Step 2.6 - Demonstrate persisted history
TURNS = [
    "{identity} I take atorvastatin 20mg and I am on the Contoso Advantage Choice HMO. Is there a Salt Lake County "
    "plan with a lower formulary tier for it? Show me a comparison.",
    "And when am I allowed to switch plans this year? Please cite the rule.",
    "Before we go on: remind me which drug I asked about and which plans you compared for me.",
]
MEMORY_MARKERS = ["atorvastatin"]


def demo(
    knowledge: dict | None = None,
    session_id: str = DEFAULT_SESSION_ID,
    port: int = DEFAULT_PORT,
    restart: bool = True,
) -> dict:
    knowledge = knowledge or helpers.require_artifact(LAB, "knowledge.json", through=2, caller=LAB)
    hosted = helpers.require_artifact(LAB, "hosted.json", through=2, caller=LAB)
    if not (HOSTED_DIR / "common").exists():
        helpers.load_lab_module(f"{LAB_DIR.name}/hosted/prepare.py").vendor()
    store = helpers.get_session_store(SESSION_DIR, log_prefix=f"[{LAB}]")
    participant_id = "P-1001"
    identity = helpers.identity_line(participant_id)
    transcript: list[dict] = []
    previous: str | None = None
    server = HostedProcess(knowledge, port=port).start()
    try:
        for number, turn in enumerate(TURNS, start=1):
            if number == 3 and restart:
                server.stop()
                log("restarting a fresh Python process with the same conversation id")
                server = HostedProcess(knowledge, port=port).start()
                previous = None
            user_text = turn.format(identity=identity)
            print(f"\n[{LAB}] turn {number} participant> {user_text}")
            reply, payload = ask(port, user_text, session_id, previous)
            previous = payload.get("id")
            record_turn(store, session_id, participant_id, payload, hosted.get("version_label", "v2"))
            checks = helpers.guardrail_report(reply)
            print(f"[{LAB}] turn {number} {AGENT_NAME}> {reply}")
            print(f"[{LAB}] turn {number} checks: {helpers.fmt_checks(checks)}")
            transcript.append(
                {
                    "turn": number,
                    "participant": user_text,
                    "agent": guardrails.redact_pii(reply),
                    "checks": checks,
                    "process_pid": server.process.pid if server.process else None,
                }
            )
    finally:
        server.stop()
    continuity = all(marker in transcript[-1]["agent"].lower() for marker in MEMORY_MARKERS)
    result = {
        "session_id": session_id,
        "restarted_before_turn_3": restart,
        "continuity_ok": continuity,
        "pids": sorted({turn["process_pid"] for turn in transcript if turn["process_pid"]}),
        "turns": transcript,
        "finished_at": helpers.now_iso(),
    }
    write_transcript(result)
    hosted["last_demo"] = {key: value for key, value in result.items() if key != "turns"}
    foundry_env.save_artifact(HOSTED_RECORD, hosted)
    if restart and (not continuity or len(result["pids"]) < 2):
        raise AssertionError(
            f"Restart acceptance failed: continuity={continuity}, pids={result['pids']}. Read {SERVER_LOG}."
        )
    log(f"continuity {'PASS' if continuity else 'FAIL'}; pids={result['pids']}")
    return result


def write_transcript(result: dict) -> Path:
    lines = [
        f"# Lab 2 transcript: {AGENT_NAME} v2, session {result['session_id']}",
        "",
        f"Generated {result['finished_at']}. Process restarted: {result['restarted_before_turn_3']}. "
        f"Continuity: {'PASS' if result['continuity_ok'] else 'FAIL'}. Text is redacted.",
        "",
    ]
    for turn in result["turns"]:
        lines += [
            f"## Turn {turn['turn']} (pid {turn['process_pid']})",
            "",
            f"Participant: {turn['participant']}",
            "",
            f"Agent: {turn['agent']}",
            "",
            f"Checks: {helpers.fmt_checks(turn['checks'])}",
            "",
        ]
    TRANSCRIPT_PATH.write_text("\n".join(lines), encoding="utf-8")
    log(f"saved {TRANSCRIPT_PATH.relative_to(LABS_DIR)}")
    return TRANSCRIPT_PATH


# %% [markdown]
# ## YOUR TURN (5 min): prove two replicas share history
#
# Use Azure Blob or the local Azurite emulator for shared history. The gate starts two copies of `hosted/main.py`,
# sends the first turn to port 8088 and
# the memory question to port 8089, asserts that the second replica remembers `atorvastatin`, and stops both
# processes even when an assertion fails.

# %% Step 2.7 - Prove two replicas share history
def shared_history_env_overrides() -> dict[str, str | None]:
    blob_url = (
        os.environ.get("MARKETPLACE_BLOB_STORAGE_URL")
        or ENV.get("MARKETPLACE_BLOB_STORAGE_URL", "")
    ).strip()
    azurite_connection_string = (
        os.environ.get("MARKETPLACE_AZURITE_CONNECTION_STRING")
        or ENV.get("MARKETPLACE_AZURITE_CONNECTION_STRING", "")
    ).strip()
    if blob_url and azurite_connection_string:
        raise ValueError(
            "Set either MARKETPLACE_BLOB_STORAGE_URL or MARKETPLACE_AZURITE_CONNECTION_STRING, not both."
        )
    if blob_url:
        return {
            "MARKETPLACE_BLOB_STORAGE_URL": blob_url,
            "MARKETPLACE_BLOB_STORAGE_CONTAINER": (
                os.environ.get("MARKETPLACE_BLOB_STORAGE_CONTAINER")
                or ENV.get("MARKETPLACE_BLOB_STORAGE_CONTAINER", "marketplace-history")
            ),
            "MARKETPLACE_AZURITE_CONNECTION_STRING": None,
        }
    if azurite_connection_string:
        return {
            "MARKETPLACE_BLOB_STORAGE_URL": None,
            "MARKETPLACE_AZURITE_CONNECTION_STRING": azurite_connection_string,
        }
    raise RuntimeError("Configure Azure Blob Storage or Azurite before running the scale-out gate.")


def scale_out_acceptance_gate(knowledge: dict | None = None) -> None:
    history_env = shared_history_env_overrides()
    knowledge = knowledge or helpers.require_artifact(LAB, "knowledge.json", through=2, caller=LAB)
    session_id = f"scale-{uuid.uuid4().hex[:8]}"
    first = HostedProcess(knowledge, port=8088, env_overrides=history_env)
    second = HostedProcess(knowledge, port=8089, env_overrides=history_env)
    try:
        first.start()
        second.start()
        ask(8088, TURNS[0].format(identity=helpers.identity_line("P-1001")), session_id)
        reply, _ = ask(8089, TURNS[2], session_id)
        print(reply)
        assert "atorvastatin" in reply.lower(), "The second replica did not load shared conversation history."
    finally:
        first.stop()
        second.stop()


if "__file__" not in globals() and os.environ.get("RUN_LAB2_SCALE_OUT_GATE") == "1":
    scale_out_acceptance_gate()


# %% [markdown]
# ## YOUR TURN (5 min): break persistence on purpose
#
# Run this gate to give the restarted process an empty message-store directory while keeping the same conversation
# ID. The assertion proves that the memory marker disappears. The gate uses isolated temporary folders under the
# Lab 2 artifact directory and always stops both server processes.

# %% Step 2.8 - Test a broken shared store
def broken_store_acceptance_gate(knowledge: dict | None = None) -> None:
    knowledge = knowledge or helpers.require_artifact(LAB, "knowledge.json", through=2, caller=LAB)
    session_id = f"broken-{uuid.uuid4().hex[:8]}"
    root = ARTIFACTS / "acceptance" / session_id
    state_root = root / "agentserver_state"
    first = HostedProcess(
        knowledge,
        env_overrides={
            "MARKETPLACE_BLOB_STORAGE_URL": None,
            "MARKETPLACE_AZURITE_CONNECTION_STRING": None,
            "MARKETPLACE_MESSAGE_STORE_DIR": str(root / "messages-a"),
            "AGENTSERVER_STATE_ROOT": str(state_root),
        },
    )
    second = HostedProcess(
        knowledge,
        env_overrides={
            "MARKETPLACE_BLOB_STORAGE_URL": None,
            "MARKETPLACE_AZURITE_CONNECTION_STRING": None,
            "MARKETPLACE_MESSAGE_STORE_DIR": str(root / "messages-b"),
            "AGENTSERVER_STATE_ROOT": str(state_root),
        },
    )
    try:
        first.start()
        ask(DEFAULT_PORT, TURNS[0].format(identity=helpers.identity_line("P-1001")), session_id)
        first.stop()
        second.start()
        reply, _ = ask(DEFAULT_PORT, TURNS[2], session_id)
        print(reply)
        assert "atorvastatin" not in reply.lower(), "The empty store unexpectedly retained the original drug."
    finally:
        first.stop()
        second.stop()


if "__file__" not in globals() and os.environ.get("RUN_LAB2_BROKEN_STORE_GATE") == "1":
    broken_store_acceptance_gate()


# %% [markdown]
# ## YOUR TURN (5 min): prove the knowledge boundary
#
# The gate asks for premium-claim proof with the MCP URL present and requires `[KB-ACC-001]`. It then starts a
# fresh server without `MARKETPLACE_KB_MCP_URL`, asks again in a new conversation, and requires the answer to
# state that the rule text is not at hand rather than inventing a citation. Both outcomes count: use available
# governed knowledge, and make its absence explicit instead of manufacturing certainty.

# %% Step 2.9 - Test grounded knowledge
def knowledge_acceptance_gate(knowledge: dict | None = None) -> None:
    knowledge = knowledge or helpers.require_artifact(LAB, "knowledge.json", through=2, caller=LAB)
    question = "What proof of payment do you accept for a premium claim?"
    with_kb = HostedProcess(knowledge)
    without_kb = HostedProcess(knowledge, env_overrides={"MARKETPLACE_KB_MCP_URL": None})
    try:
        with_kb.start()
        grounded, _ = ask(DEFAULT_PORT, question, f"kb-{uuid.uuid4().hex[:8]}")
        print(grounded)
        assert "[KB-ACC-001]" in grounded, "The grounded answer did not cite KB-ACC-001."
        with_kb.stop()
        without_kb.start()
        unavailable, _ = ask(DEFAULT_PORT, question, f"no-kb-{uuid.uuid4().hex[:8]}")
        print(unavailable)
        assert "[KB-" not in unavailable, "The no-KB answer invented a knowledge citation."
        assert "not at hand" in unavailable.lower(), "The no-KB answer did not state the knowledge boundary."
    finally:
        with_kb.stop()
        without_kb.stop()


if "__file__" not in globals() and os.environ.get("RUN_LAB2_KNOWLEDGE_GATE") == "1":
    knowledge_acceptance_gate()


# %% Step 2.10 - Print the Bash deployment command
if "__file__" not in globals():
    print(deploy_commands())


# %% [markdown]
# ## Script-only entry point - skip in Jupyter
#
# **Running this notebook cell by cell? Skip the next cell.** The earlier cells provide the notebook path.
# The next cell is only the command-line entry point for running this lab's `.py` file as one program.
# Its command-line invocation is guarded in the generated notebook; running the cell does not launch the lab.
# For script mode instead, run `python lab2_hosted_knowledge.py --help` in a Bash terminal from this lab's folder and choose the desired options.

# %% Step 2.11 - Script-only entry point (skip in Jupyter)
def main(args: argparse.Namespace) -> None:
    if args.record_version:
        record_deployment(args.record_version, args.status)
        return
    if args.deploy:
        print(deploy_commands())
        return
    if args.acceptance_gate:
        gates = {
            "scale-out": scale_out_acceptance_gate,
            "broken-store": broken_store_acceptance_gate,
            "knowledge": knowledge_acceptance_gate,
        }
        gates[args.acceptance_gate]()
        return
    if args.demo_only:
        demo(session_id=args.session_id, port=args.port, restart=not args.no_restart)
        return
    info = build(skip_connection=args.skip_connection)
    if not args.build_only:
        demo(session_id=args.session_id, port=args.port, restart=not args.no_restart)
        print(f"\n[{LAB}] deploy from source when ready:\n{deploy_commands(hosted=info)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lab 2: Hosted knowledge and durable sessions")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--demo-only", action="store_true", help="reuse artifacts/lab2/knowledge.json and hosted.json")
    parser.add_argument("--deploy", action="store_true", help="print paste-safe Bash; does not deploy")
    parser.add_argument("--record-version", default=None, help="record the active Foundry version in hosted.json")
    parser.add_argument("--status", default="active", help="status stored with --record-version")
    parser.add_argument("--skip-connection", action="store_true", help="skip the ARM project connection PUT")
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-restart", action="store_true", help="keep one process for all three turns")
    parser.add_argument("--acceptance-gate", choices=("scale-out", "broken-store", "knowledge"))
    main(parser.parse_args())
