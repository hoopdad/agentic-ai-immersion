# %% [markdown]
# # Stretch 6: Invocations, Toolbox and Skills
#
# **The second hosting protocol, compared with the Responses protocol from Lab 1: deterministic facts, bounded model reasoning, and reusable governed procedures.**
#
# |  | Details |
# | --- | --- |
# | Goal | Build and call an Invocations-protocol hosted agent for denied-claims review, then run the Responses concierge with a bundled skill and, when configured, a Foundry Toolbox. Compare the two protocols. |
# | Inputs | Root `.env`; optional `labs/artifacts/lab1/hosted.json`; optional `TOOLBOX_NAME`, `TOOLBOX_MCP_URL`, and `SKILL_NAMES` |
# | Outputs | `labs/artifacts/stretch6/invocations.json`, `claim_reviews/*.json`, and `*_local.log` |
# | Time | 45–60 min (stretch) |
#
# **How to run code**
#
# |  | Command |
# | --- | --- |
# | Run cell by cell | Open `stretch6_walkthrough.ipynb` (this file), or use the `# %%` cells in VS Code. |
# | Run the Invocations agent locally | `python stretch6_invocations.py` |
# | Create deterministic packets without a model | `python stretch6_invocations.py --offline` |
# | Run the optional Responses + Skills demo | `python stretch6_invocations.py --skills-demo` |
# | Print azd commands for both agents | `python stretch6_invocations.py --deploy` |
#
# **Where this runs.** This notebook (workstation) vendors `common/`, `data/` and `skills/` into the two hosted
# folders, starts each `main.py` locally on port 8088 and calls it: the Invocations agent with a JSON batch of claim
# ids, the Responses agent with a participant question that makes it read the bundled skill. Both folders deploy to
# Foundry with `azd` (`--protocol invocations` and `--protocol responses`); Foundry Toolbox and Skills are preview.
#
# **Lab path and prerequisites.**
#
# - **Optional stretch:** This lab is independent of Stretch 5 and is not required for the four core labs.
# - **No prior artifact is required:** The Invocations exercise and `--offline` path run without Lab 1 output.
# - **Recommended before the comparison:** Complete Lab 1, or run `python ../catch_up.py --through 1`, so its
#   Responses agent is available as the concrete comparison.
# - **From Lab 1:** Reuse the dev-container setup, local port, source packaging, and explicit `azd` deployment
#   workflow. Lab 1 introduced the Responses protocol; this lab highlights where Invocations differs.
# - **Optional:** `--skills-demo`, Foundry Toolbox configuration, and deployment are extension paths. Toolbox and
#   Skills are preview features.
#
# **Checkpoint artifact.** `labs/artifacts/stretch6/invocations.json` (agent names, protocol comparison, one batch
# result) and `labs/artifacts/stretch6/claim_reviews/CLM-*.json`.
#
# %% [markdown]
# ## Before the first run (dev-container Bash)
#
# Continue with the dev container, root `.env`, Azure sign-in, and `/usr/local/bin/python` kernel used in Lab 1.
# If you have not completed that setup, follow the workshop `SETUP.md` first. The `--offline` path does not call
# Azure, but it still uses the repository's dev-container environment.
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
# cd /workspaces/agentic-ai-immersion/build-and-operate-foundry-agents/labs/stretch6-invocations-toolbox-skills
# python -m jupyter lab stretch6_walkthrough.ipynb
# ```
#
# %% [markdown]
# Shell commands use the container filesystem. Hosted deployment remains an explicit terminal action.
#
# %% Step S6.1 - Imports and paths
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # workshop root (common/ and data/ live here)
LABS_DIR = ROOT / "labs"
LAB_DIR = Path(__file__).resolve().parent
for folder in reversed((ROOT, LABS_DIR, LAB_DIR / "hosted-invocations")):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, guardrails, marketplace_data, resource_names  # noqa: E402

import lab_helpers  # noqa: E402
from claims_review import hra_rules, review_claims  # noqa: E402  (pure Python; the same code the agent calls as a tool)

LAB = "stretch6"
ENV = foundry_env.load_env()
INVOCATIONS_AGENT = resource_names.name(resource_names.HOSTED_CLAIMS, ENV)
SKILLS_AGENT = resource_names.name(resource_names.HOSTED_CONCIERGE, ENV)
INVOCATIONS_DIR = LAB_DIR / "hosted-invocations"
SKILLS_HOST_DIR = LAB_DIR / "hosted-responses-skills"
SKILLS_SRC = LAB_DIR / "skills"
ARTIFACTS = lab_helpers.artifact_path(LAB)
RECORD = ARTIFACTS / "invocations.json"
REVIEWS_DIR = ARTIFACTS / "claim_reviews"
PORT = int(os.environ.get("MARKETPLACE_HOSTED_PORT", "8088"))
LOCAL_BASE = f"http://localhost:{PORT}"


def nightly_denial_ids() -> list[str]:
    """Return every denied claim id by walking each participant account through the public data helper."""
    accounts = json.loads((ROOT / "data" / "hra_accounts.json").read_text(encoding="utf-8"))
    denied = {
        claim_id
        for source in accounts
        for claim_id in marketplace_data.get_hra_account(source["participant_id"]).get("claims_summary", {}).get("denied_claim_ids", [])
    }
    return sorted(denied)


BATCH = nightly_denial_ids()
S2_QUESTION = "Hi, this is P-1003, ZIP 84604. My claim CLM-9003 was denied. Why, and what exactly do I need to send?"
DEBIT_CARD_QUESTION = "Hi, this is P-1004, ZIP 38103. My card was declined at the pharmacy. What should I check?"
FACT_FIELDS = (
    "claim_id", "participant_id", "hra_account_id", "status", "type", "amount", "submitted",
    "denial_reason_code", "denial_reason_text", "kb_rule", "fix_available", "accepted_proof_of_payment",
    "not_accepted_as_proof", "resubmission_steps", "advisor_action_required", "knowledge_ref", "review",
)


def log(message: str) -> None:
    print(f"[{LAB}] {message}", flush=True)


# %% Step S6.2 - Compare hosted protocols
PROTOCOLS = [
    {"dimension": "Interaction", "invocations": "one structured request -> one structured response", "responses": "multi-turn conversation"},
    {"dimension": "Tool use", "invocations": "deterministic; the model fills in prose only", "responses": "model-directed: decides when to call tools, skills, toolbox"},
    {"dimension": "Streaming", "invocations": "no (batch result)", "responses": "token by token (OpenAI compatible)"},
    {"dimension": "State", "invocations": "stateless", "responses": "session history (Lab 2 message store)"},
    {"dimension": "Request body", "invocations": '{"message": "<json string>"}  POST /invocations', "responses": '{"input": "...", "previous_response_id"?}  POST /responses'},
    {"dimension": "Best for", "invocations": "batch jobs, API-to-API, nightly reviews, pipelines", "responses": "advisor and participant chat, research"},
    {"dimension": "Host server", "invocations": "InvocationsHostServer(agent)", "responses": "ResponsesHostServer(agent)"},
    {"dimension": "Healthcare Marketplace example", "invocations": "denied-claims-review over the day's denials", "responses": "healthcare-marketplace-concierge-hosted, healthcare-marketplace-triage-hosted"},
]


# %% Step S6.3 - Build both hosted packages
def build(*, vendor: bool = True) -> dict:
    env = foundry_env.load_env()
    resource_names.suffix(env, required=True)
    previous = lab_helpers.artifact_path("lab1", "hosted.json")
    lab1 = foundry_env.load_artifact(previous) if previous.exists() else {}
    if not lab1:
        log("artifacts/lab1/hosted.json missing (run Lab 1 or `python catch_up.py --through 1`); continuing, S6 does not depend on it")
    counts: dict[str, dict] = {}
    if vendor:
        invocations_prepare = lab_helpers.load_lab_module(f"{LAB_DIR.name}/hosted-invocations/prepare.py")
        responses_prepare = lab_helpers.load_lab_module(f"{LAB_DIR.name}/hosted-responses-skills/prepare.py")
        counts["hosted-invocations"] = invocations_prepare.vendor()
        counts["hosted-responses-skills"] = responses_prepare.vendor()
    skills = sorted(p.parent.name for p in SKILLS_SRC.glob("*/SKILL.md"))
    existing = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else {}
    record = {
        "lab": LAB, "preview": ["Foundry Toolbox", "Foundry Skills"],
        "agents": {
            "invocations": {"agent_name": INVOCATIONS_AGENT, "protocol": "invocations", "hosted_dir": str(INVOCATIONS_DIR.relative_to(ROOT)),
                            "operation": "denied-claims-review", "input": {"claim_ids": ["CLM-9003", "..."]},
                            "output": "ClaimReviewBatch {reviewed_at, reviews[]}", "knowledge": hra_rules()["doc_id"],
                            "deployed": (existing.get("agents", {}).get("invocations") or {}).get("deployed") or {"version": None, "status": "not deployed"}},
            "responses_skills": {"agent_name": SKILLS_AGENT, "protocol": "responses", "hosted_dir": str(SKILLS_HOST_DIR.relative_to(ROOT)),
                                 "skills": skills, "toolbox": env.get("TOOLBOX_NAME") or None, "toolbox_mcp_url_set": bool(env.get("TOOLBOX_MCP_URL")),
                                 "deployed": (existing.get("agents", {}).get("responses_skills") or {}).get("deployed") or {"version": None, "status": "not deployed"}},
        },
        "model": lab_helpers.pick_model(env), "protocol_comparison": PROTOCOLS, "vendored": counts or existing.get("vendored", {}),
        "sample_run": existing.get("sample_run"), "lab1_agent": lab1.get("agent_name"), "built_at": lab_helpers.now_iso(),
    }
    foundry_env.save_artifact(RECORD, record)
    log(f"wrote {RECORD.relative_to(LABS_DIR)} (agents {INVOCATIONS_AGENT}, {SKILLS_AGENT}; skills {skills})")
    return record


# %% Step S6.4 - Define the local hosted server
class HostedProcess:
    def __init__(self, hosted_dir: Path, port: int = PORT, extra_env: dict | None = None):
        self.hosted_dir, self.port, self.extra_env = hosted_dir, port, extra_env or {}
        self.log_path = ARTIFACTS / f"{hosted_dir.name}_local.log"
        self.process: subprocess.Popen | None = None
        self.log_handle = None

    def start(self, timeout: float = 120.0) -> "HostedProcess":
        env = {**os.environ, **foundry_env.load_env(), **self.extra_env, "MARKETPLACE_HOSTED_PORT": str(self.port), "PYTHONUNBUFFERED": "1"}
        self.log_handle = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, str(self.hosted_dir / "main.py")], cwd=str(self.hosted_dir), env=env,
                                        stdout=self.log_handle, stderr=subprocess.STDOUT)
        log(f"started {self.hosted_dir.name}/main.py (pid {self.process.pid}) on port {self.port}; log -> {self.log_path.relative_to(LABS_DIR)}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                self.stop()
                raise SystemExit(f"[{LAB}] main.py exited early (code {self.process.returncode}). Read {self.log_path}")
            with socket.socket() as probe:
                probe.settimeout(1.0)
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
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
            log(f"stopped {self.hosted_dir.name}/main.py")
        if self.log_handle and not self.log_handle.closed:
            self.log_handle.close()


# %% Step S6.5 - Call the Invocations protocol
def call_invocations(base: str, claim_ids: list[str]) -> tuple[list[dict], str]:
    """POST the batch to the installed SDK's documented POST /invocations route."""
    test_local = lab_helpers.load_lab_module(f"{LAB_DIR.name}/hosted-invocations/test_local.py")
    import httpx

    body = {"message": json.dumps({"claim_ids": claim_ids})}
    path = test_local.invocations_path()
    response = httpx.post(f"{base.rstrip('/')}{path}", json=body, timeout=180.0)
    response.raise_for_status()
    payload = response.json() if "application/json" in response.headers.get("content-type", "") else response.text
    reviews = test_local.extract_reviews(payload)
    assert_review_facts(reviews, claim_ids, require_explanations=True)
    return reviews, path


def assert_review_facts(reviews: list[dict], claim_ids: list[str], *, require_explanations: bool) -> None:
    """Prove that model output preserved every deterministic field exposed by the response schema."""
    expected = {packet["claim_id"]: packet for packet in review_claims(claim_ids)}
    actual = {packet.get("claim_id"): packet for packet in reviews}
    if set(actual) != set(expected):
        raise AssertionError(f"claim ids differ: expected {sorted(expected)}, got {sorted(actual)}")
    rules = hra_rules()
    for claim_id, expected_packet in expected.items():
        packet = actual[claim_id]
        for field in FACT_FIELDS:
            if packet.get(field) != expected_packet.get(field):
                raise AssertionError(
                    f"{claim_id} changed deterministic field {field}: "
                    f"expected {expected_packet.get(field)!r}, got {packet.get(field)!r}"
                )
        if claim_id == "CLM-9003" and packet["accepted_proof_of_payment"] != rules["proof_of_payment"]:
            raise AssertionError("CLM-9003 must copy the complete KB-ACC-001 proof-of-payment list")
        explanation = str(packet.get("participant_explanation") or "").strip()
        if require_explanations and (not explanation or "[KB-ACC-001]" not in explanation):
            raise AssertionError(f"{claim_id} participant_explanation must be non-empty and cite [KB-ACC-001]")
        if guardrails.contains_payment_promise(explanation):
            raise AssertionError(f"{claim_id} participant_explanation promises an outcome: {explanation!r}")


def save_reviews(reviews: list[dict], source: str) -> None:
    for review in reviews:
        path = REVIEWS_DIR / f"{review.get('claim_id', 'unknown')}.json"
        foundry_env.save_artifact(path, json.loads(guardrails.redact_pii(json.dumps({**review, "source": source}, default=str))))
    log(f"wrote {len(reviews)} packets to {REVIEWS_DIR.relative_to(LABS_DIR)}/ ({source})")


# %% Step S6.6 - Define the Invocations demo
def demo(base: str | None = None, *, offline: bool = False, claim_ids: list[str] = BATCH) -> dict:
    if offline:
        reviews, source, path = review_claims(claim_ids), "offline (claims_review.py, no model)", None
        assert_review_facts(reviews, claim_ids, require_explanations=False)
    else:
        server = None
        if base is None:
            server = HostedProcess(INVOCATIONS_DIR).start()
            base = LOCAL_BASE
        try:
            reviews, path = call_invocations(base, claim_ids)
        finally:
            if server:
                server.stop()
        source = f"local {base}{path}"
    for review in reviews:
        line = f"{review.get('claim_id')}: {review.get('status')} -> {review.get('review')}"
        if review.get("participant_explanation"):
            line += f"\n[{LAB}]     {review['participant_explanation']}"
        print(f"[{LAB}] {line}")
    save_reviews(reviews, source)
    record = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else build(vendor=False)
    record["sample_run"] = {"source": source, "claim_ids": claim_ids, "reviews": len(reviews),
                            "denied_with_fix": [r["claim_id"] for r in reviews if r.get("review") == "resubmit"],
                            "denied_no_fix": [r["claim_id"] for r in reviews if r.get("review") == "no_fix"], "at": lab_helpers.now_iso()}
    foundry_env.save_artifact(RECORD, record)
    return record["sample_run"]


# %% Step S6.7 - Define the Skills demos and acceptance gates
def skills_demo(base: str | None = None) -> str:
    lab1 = lab_helpers.load_lab_module("lab1-hosted-agent-basics/lab1_hosted_basics.py")   # reuse post_responses()
    server = None
    if base is None:
        server = HostedProcess(SKILLS_HOST_DIR).start()
        base = LOCAL_BASE
    try:
        print(f"[{LAB}] participant> {S2_QUESTION}")
        result = lab1.post_responses(base, S2_QUESTION)
    finally:
        if server:
            server.stop()
    text = result["text"]
    report = lab_helpers.guardrail_report(text)
    print(f"[{LAB}] {SKILLS_AGENT}> {text}\n[{LAB}] checks: {lab_helpers.fmt_checks(report)}")
    if "KB-ACC-001" not in text:
        log("WARNING: the answer does not cite [KB-ACC-001]; check the server log for the read_skill call")
    foundry_env.save_artifact(ARTIFACTS / "skills_transcript.md",
                              f"# Stretch 6 skills transcript\n\n**Participant:** {S2_QUESTION}\n\n**{SKILLS_AGENT}:** {guardrails.redact_pii(text)}\n")
    return text


def nightly_denials_acceptance_gate(base: str | None = None, *, offline: bool = False) -> dict:
    """Acceptance gate for YOUR TURN: BATCH must contain every denied claim and no non-denied claim."""
    expected = nightly_denial_ids()
    if sorted(BATCH) != expected:
        raise AssertionError(f"Set BATCH to nightly_denial_ids(); expected {expected}, got {sorted(BATCH)}")
    sample = demo(base, offline=offline, claim_ids=BATCH)
    if sorted(sample["denied_with_fix"] + sample["denied_no_fix"]) != expected:
        raise AssertionError(f"nightly run did not return every denied claim: {sample}")
    log(f"nightly denials acceptance PASS ({len(expected)} denied claims)")
    return sample


def validate_second_skill_source() -> Path:
    """Fail unless the learner's second skill is a governed KB-ACC-002 skill."""
    path = SKILLS_SRC / "debit-card-faq" / "SKILL.md"
    if not path.is_file():
        raise AssertionError(f"Create {path.relative_to(ROOT)} before running this gate")
    meta, body = marketplace_data.split_frontmatter(path.read_text(encoding="utf-8"))
    if meta.get("name") != "debit-card-faq" or meta.get("source_doc") != "KB-ACC-002":
        raise AssertionError("The second skill frontmatter must set name: debit-card-faq and source_doc: KB-ACC-002")
    required = ("declined", "blocked", "lost", "never read, request or record the full card number")
    missing = [term for term in required if term.lower() not in body.lower()]
    if missing:
        raise AssertionError(f"The second skill is missing required procedures/safety text: {missing}")
    return path


def second_skill_acceptance_gate(base: str | None = None) -> str:
    """Build, invoke, assert KB-ACC-002 use, and always stop the learner's local server."""
    validate_second_skill_source()
    build()
    server = None
    if base is None:
        server = HostedProcess(SKILLS_HOST_DIR).start()
        base = LOCAL_BASE
    try:
        lab1 = lab_helpers.load_lab_module("lab1-hosted-agent-basics/lab1_hosted_basics.py")
        result = lab1.post_responses(base, DEBIT_CARD_QUESTION)
    finally:
        if server:
            server.stop()
    text = result["text"]
    if "[KB-ACC-002]" not in text:
        raise AssertionError("The debit-card answer must cite [KB-ACC-002]")
    log_text = (ARTIFACTS / "hosted-responses-skills_local.log").read_text(encoding="utf-8", errors="replace")
    if "read_skill name=debit-card-faq" not in log_text:
        raise AssertionError("The server log does not show read_skill('debit-card-faq')")
    log("second skill acceptance PASS")
    return text


# %% Step S6.8 - Prepare both deployments
def deploy_commands(env: dict | None = None) -> str:
    from deployment import bash_deploy_block
    env = foundry_env.load_env() if env is None else env
    blocks = []
    for folder, name, protocol in (
        (INVOCATIONS_DIR, INVOCATIONS_AGENT, "invocations"),
        (SKILLS_HOST_DIR, SKILLS_AGENT, "responses"),
    ):
        blocks.append(bash_deploy_block(folder, name, protocol, env, check_package=True))
    return "\n\n".join(blocks)

# %% [markdown]
# ## Print-only deployment
#
# Set `PROJECT_RESOURCE_ID` in the workshop `.env`, then run the next cell. It prints both paste-ready Bash
# deployment blocks in the notebook; it does not execute `azd`, vendor the packages, or deploy either agent.

# %% Step S6.9 - Print the Bash deployment commands
if "__file__" not in globals():
    print(deploy_commands())

# %% Step S6.10 - Process nightly denials
# Run this cell to process the data-derived nightly denial batch. The gate invokes the exact batch, checks
# every deterministic field, and stops its child server even when an assertion fails.
if "__file__" not in globals():
    nightly_denials_acceptance_gate(offline=False)

# %% Step S6.11 - Add a second skill
# Write skills/debit-card-faq/SKILL.md from data/knowledge/debit-card-faq.md, then run this cell. The gate checks
# the governed source metadata, rebuilds, invokes the skill question, proves read_skill ran, and cleans up.
if "__file__" not in globals():
    second_skill_acceptance_gate()


# %% [markdown]
# ## Script-only entry point - skip in Jupyter
#
# **Running this notebook cell by cell? Skip the next cell.** The earlier cells provide the notebook path.
# The next cell is only the command-line entry point for running this lab's `.py` file as one program.
# Its command-line invocation is guarded in the generated notebook; running the cell does not launch the lab.
# For script mode instead, run `python stretch6_invocations.py --help` in a Bash terminal from this lab's folder and choose the desired options.

# %% Step S6.12 - Script-only entry point (skip in Jupyter)
def main(args: argparse.Namespace) -> None:
    if args.deploy:
        print(f"\n[{LAB}] deploy from source (two agents, two protocols):\n{deploy_commands()}")
        return
    log(f"data check: {marketplace_data.get_claim_status('CLM-9003').get('status')} claim CLM-9003 is in data/hra_accounts.json")
    build(vendor=not args.no_vendor)
    if args.skip_demo:
        return
    demo(args.base, offline=args.offline)
    if args.skills_demo:
        skills_demo(args.base)
    log("done. Checkpoint: paste the CLM-9003 participant_explanation and the protocol comparison row you found most useful.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Stretch 6 Invocations, Toolbox, and Skills lab.")
    parser.add_argument("--offline", action="store_true", help="no model: deterministic review packets only")
    parser.add_argument("--skills-demo", action="store_true", help="also run the Responses + Skills agent on S2")
    parser.add_argument("--skip-demo", action="store_true")
    parser.add_argument("--no-vendor", action="store_true")
    parser.add_argument("--base", default=None, help="talk to an already running server")
    parser.add_argument("--deploy", action="store_true")
    main(parser.parse_args())
