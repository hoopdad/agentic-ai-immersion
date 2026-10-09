# %% [markdown]
# # Lab 12: Hosted-to-hosted delegation
#
# **Prerequisites:** BOTH Lab 8 (deployed triage capability) and Lab 9 (telemetry/evaluation).
# **Recommended route:** finish Lab 10 first, then extend an isolated candidate.
#
# Branch the accepted knowledge concierge into `healthcare-concierge-delegation-{suffix}`;
# reuse Lab 8's deployed graph as the callee. No Prompt Agent and no second graph are built.
# The original Labs 9-10 version, evaluated bundle and sources are not overwritten.
# One request returns pending advisor approval; it NEVER decides or resumes a case.
#
# The hosted caller's managed identity needs Foundry Agent Consumer (or Azure AI User)
# on the callee's project/agent, plus existing knowledge/model/history access. An
# administrator reviews RBAC/network access and pins the callee endpoint to the accepted
# Lab 8 version; the notebook does not silently change permissions or traffic routing.
# Name endpoints route by their server-side selector, not an invented version query.
# [Endpoint routing](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent)
# and [async client API](https://learn.microsoft.com/en-us/python/api/azure-ai-projects/azure.ai.projects.aio.aiprojectclient?view=azure-python).
#
# This cell restores both required predecessors in a fresh kernel without replaying their cloud actions.
# %% Step 12.1 - Restore the two hosted prerequisites
# ruff: noqa: F704
from pathlib import Path
import json
import re
import subprocess
import sys
import uuid

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/3-day-labs/lab12/lab12_workflows_delegation.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/3-day-labs/lab12/lab12_workflows_delegation.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "3-day-labs", ROOT / "shared/hosted-delegation"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import foundry_env, notebook_parts, resource_names
from delegation import validate_request, validate_target, validate_pending, require_pinned_selector

ENV = foundry_env.load_env()
ARTIFACTS = lab_helpers.artifact_path("hosted_delegation")
HOSTED_DIR = ROOT / "shared/hosted-delegation/hosted"
CANDIDATE_NAME = resource_names.name("healthcare-concierge-delegation", ENV, required=True)
prepare = lab_helpers.load_lab_module("hosted-delegation/hosted/prepare.py")
if "__file__" not in globals():
    (ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    accepted = {}
    triage_checkpoint = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab4", "part_b.json"), lab="lab4", part="b",
        context=notebook_parts.scope(ENV),
    )
    operate_checkpoint = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a",
        context=notebook_parts.scope(ENV),
    )
    if "triage_reference" not in triage_checkpoint["state"]:
        raise RuntimeError("Rerun Lab 8 to publish the current deployed triage capability contract.")
    target = validate_target(triage_checkpoint["state"]["triage_reference"])
    evaluated = operate_checkpoint["state"].get("bundle", {})
    if not evaluated.get("info", {}).get("evaluated_target"):
        raise RuntimeError("Rerun Lab 9 to publish the immutable evaluated-target contract.")
    trace_prerequisite = foundry_env.load_artifact(lab_helpers.artifact_path("lab5", "trace_evidence.json"))
    if not trace_prerequisite.get("ingestion_verified") or not trace_prerequisite.get("observed_trace_id") \
            or not trace_prerequisite.get("observed_resource_id"):
        raise RuntimeError("Complete Lab 9's Azure trace observation before hosted delegation.")
    core_hosted = evaluated["hosted"]
    operations = lab_helpers.load_lab_module("operate-hosted-agents/lab5_operate.py")
    evaluated_target = evaluated["info"]["evaluated_target"]
    operations.validate_evaluated_target(evaluated_target, core_hosted, evaluated["knowledge"])
    assert CANDIDATE_NAME != core_hosted["agent_name"] != target["agent_name"]
    foundry_env.save_artifact(ARTIFACTS / "target.json", target)
    print("Callee:", target, "\nIsolated caller:", CANDIDATE_NAME)

# %% [markdown]
# ## Inspect the boundary and reject unsafe calls
#
# `shared/hosted-delegation/delegation.py` uses `DefaultAzureCredential` and
# `get_openai_client(agent_name=...)`; the pinned SDK disables automatic retries.
# The full turn has a bounded timeout; authentication, transport, JSON and remote
# status errors propagate visibly. The callee recognizes a `pending_case` input envelope
# and runs the SAME graph as Labs 7-8, without a model inventing an advisor decision.
# The zero-argument tool reads only an application-bound envelope; model calls without
# that binding fail before networking. The notebook explicitly supplies IDs and participant.
# Case/session/traceparent travel in the input and traceparent also in Responses
# `extra_headers`. The callee extracts W3C context before its workflow span.
#
# This cell verifies that an attempted advisor decision is rejected before any remote request.
# %% Step 12.2 - Observe the controlled failure
if "__file__" not in globals():
    (ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    accepted.pop("failure", None)
    unsafe_request = {"operation": "pending_case", "advisor_decision": "approve"}
    try:
        validate_request(unsafe_request)
    except ValueError as exc:
        failure = {"rejected": True, "reason": str(exc), "remote_request_sent": False}
        print(failure)
    else:
        raise AssertionError("The delegation boundary accepted a manufactured advisor decision.")
    foundry_env.save_artifact(ARTIFACTS / "failure_evidence.json", failure)
    accepted["failure"] = True

# %% [markdown]
# ## YOUR TURN: choose a bound, predict a failure and inspect retained behavior
#
# Choose a timeout between 1 and 120 seconds before preparing. Predict why a 401/403,
# a changed version selector, timeout, duplicate case or non-pending response must not
# produce a success-shaped packet. Never retry blindly: a timed-out request may have
# created pending state. Inspect its case/session and service logs first; a deliberate
# new case is not distributed resume or idempotent replay.
#
# Inspect original `hosted/main.py` and `delegation.py`, not prepared copies.
# The candidate reuses the accepted Lab 6 tools, knowledge, compliance and history
# implementation; only its delegation boundary is added. Separate candidate storage
# keeps its message/session state out of the measured core product.
#
# This cell prepares an isolated package and records the exact source fingerprints without deploying it.
# %% Step 12.3 - Prepare the isolated candidate
if "__file__" not in globals():
    (ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    accepted.pop("package", None)
    assert accepted.get("failure"), "Observe the controlled failure first."
    DELEGATION_TIMEOUT = 90
    assert 0 < DELEGATION_TIMEOUT <= 120
    print((HOSTED_DIR / "main.py").read_text(encoding="utf-8"))
    tested_sources = prepare.source_fingerprints()
    prepare.vendor()
    settings = dict(core_hosted.get("env_for_container", {}))
    settings.update({
        "MARKETPLACE_DELEGATION_AGENT_NAME": CANDIDATE_NAME,
        "MARKETPLACE_TRIAGE_REFERENCE": json.dumps(target),
        "MARKETPLACE_DELEGATION_TIMEOUT": str(DELEGATION_TIMEOUT),
        "MARKETPLACE_MESSAGE_STORE_DIR": "/files/delegation-message-store",
        "MARKETPLACE_SESSION_DIR": "/files/delegation-sessions",
        "MARKETPLACE_BLOB_STORAGE_CONTAINER": "delegation-" + ENV["MARKETPLACE_RESOURCE_SUFFIX"],
        "APPLICATIONINSIGHTS_CONNECTION_STRING": ENV.get("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
    })
    assert not settings.get("MARKETPLACE_AZURITE_CONNECTION_STRING"), "Azurite is local only; choose cloud Blob or candidate files explicitly."
    assert settings["APPLICATIONINSIGHTS_CONNECTION_STRING"], "Restore Lab 9 telemetry configuration."
    foundry_env.save_artifact(ARTIFACTS / "source_evidence.json", tested_sources)
    accepted["package"] = True

# %% [markdown]
# The next action creates only this attendee-scoped candidate. It does not promote it
# or mutate the Lab 9 evaluated target. Ensure the distinct history container exists
# with reviewed access; local Azurite is never a cloud backend.
#
# This cell deploys only the accepted candidate and displays its actual version status.
# %% Step 12.4 - Deploy the extension candidate
if "__file__" not in globals():
    (ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    accepted.pop("deployment", None)
    assert accepted.get("package") and prepare.source_fingerprints() == tested_sources, "Rerun candidate preparation after source changes."
    from deployment import bash_deploy_block
    command = bash_deploy_block(HOSTED_DIR, CANDIDATE_NAME, "responses", ENV, settings, check_package=True)
    subprocess.run(["bash", "-lc", command], cwd=HOSTED_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", CANDIDATE_NAME], cwd=HOSTED_DIR, check=True)
    accepted["deployment"] = True

# %% [markdown]
# Pin the candidate endpoint in Foundry to the active version shown above before invoking.
# Select fresh explicit IDs once; rerunning this cell is a deliberate new case, NOT retry.
# A rejected selector sends no state-changing turn; a timeout needs case/session inspection.
#
# This cell invokes the deployed caller and verifies the callee's correlated pending status and exact version.
# %% Step 12.5 - Delegate one pending case across hosted services
if "__file__" not in globals():
    (ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    accepted.pop("pending", None)
    assert accepted.get("deployment"), "Deploy the separate candidate first."
    DEPLOYED_VERSION = ""  # Enter the candidate version inspected and explicitly pinned in Foundry.
    assert DEPLOYED_VERSION
    request = {
        "operation": "pending_case", "case_id": "delegated-" + uuid.uuid4().hex,
        "session_id": "delegation-" + uuid.uuid4().hex, "participant_id": "P-1005",
        "message": "Hi, this is P-1005, ZIP 84010. Which ACA plan should I choose?",
        "traceparent": "00-" + uuid.uuid4().hex + "-" + uuid.uuid4().hex[:16] + "-01",
    }
    validate_request(request)
    from azure.ai.projects.aio import AIProjectClient
    from azure.identity.aio import DefaultAzureCredential
    import asyncio
    async with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=ENV["FOUNDRY_PROJECT_ENDPOINT"], credential=credential, allow_preview=True,
    ) as project:
        async with asyncio.timeout(DELEGATION_TIMEOUT):
            candidate_details = await project.agents.get(CANDIDATE_NAME)
        require_pinned_selector(candidate_details, DEPLOYED_VERSION)
        async with project.get_openai_client(
            agent_name=CANDIDATE_NAME, max_retries=0, timeout=DELEGATION_TIMEOUT,
        ) as client:
            async with asyncio.timeout(DELEGATION_TIMEOUT):
                response = await client.responses.create(
                    input=json.dumps(request), store=False,
                    extra_headers={"traceparent": request["traceparent"]},
                )
        async with asyncio.timeout(DELEGATION_TIMEOUT):
            require_pinned_selector(await project.agents.get(CANDIDATE_NAME), DEPLOYED_VERSION)
    assert response.status == "completed", f"Caller failed: {response.status}; inspect case/session before retry."
    result = json.loads(response.output_text)
    assert result.get("caller_version") == DEPLOYED_VERSION, "Caller version changed; rerun the affected gates."
    validate_pending(result, request, target)
    foundry_env.save_artifact(ARTIFACTS / "delegation_evidence.json", {
        "request": request, "result": result, "caller_name": CANDIDATE_NAME,
        "caller_version": DEPLOYED_VERSION, "response_id": response.id,
    })
    print(result)
    print('union requests, dependencies\n| where timestamp > ago(1h)\n'
          f'| where operation_Id == "{request["traceparent"].split("-")[1]}"\n'
          '| project timestamp, name, id, operation_ParentId, customDimensions\n| order by timestamp asc')
    accepted["pending"] = True

# %% [markdown]
# Find this request's trace ID in the intended Application Insights resource. Confirm a
# caller delegation span and a callee intake/workflow span share the trace, case and session;
# merely generating IDs or configuring telemetry is not ingestion evidence.
# [Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-client-side?tabs=python).
# File-backed pending state is single-instance only; no advisor action is forwarded and
# no replica-safe or cross-version resume is claimed.
# The envelope session ID is application correlation, not proof of platform sandbox continuity.
#
# This cell saves hosted delegation only after correlated Azure telemetry has been inspected.
# %% Step 12.6 - Accept correlation and publish the independent handoff
if "__file__" not in globals():
    (ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    assert accepted.get("pending") and prepare.source_fingerprints() == tested_sources
    current_triage = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab4", "part_b.json"), lab="lab4", part="b", context=notebook_parts.scope(ENV),
    )
    current_operations = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(ENV),
    )
    assert current_triage["state"]["triage_reference"] == target, "Lab 8 target changed; repeat the affected delegation gates."
    assert current_operations["state"]["bundle"] == evaluated, "Lab 9 measured bundle changed; restore and repeat acceptance."
    operations.validate_evaluated_target(evaluated_target, core_hosted, evaluated["knowledge"])
    TRACE_QUERY_EVIDENCE = ""  # Paste the Application Insights query and observed caller/callee span IDs.
    CALLER_SPAN_ID = ""
    CALLEE_SPAN_ID = ""
    assert TRACE_QUERY_EVIDENCE.strip() and CALLER_SPAN_ID and CALLEE_SPAN_ID, "Inspect both hosted spans first."
    assert all(re.fullmatch(r"[0-9a-f]{16}", item) for item in (CALLER_SPAN_ID, CALLEE_SPAN_ID)), "Use actual hexadecimal Azure span IDs."
    assert CALLER_SPAN_ID != CALLEE_SPAN_ID
    trace_id = request["traceparent"].split("-")[1]
    assert trace_id in TRACE_QUERY_EVIDENCE, "The inspected query must identify this request's trace."
    assert CALLER_SPAN_ID in TRACE_QUERY_EVIDENCE and CALLEE_SPAN_ID in TRACE_QUERY_EVIDENCE, "Include both observed span rows in the evidence."
    foundry_env.save_artifact(ARTIFACTS / "trace_evidence.json", {
        "trace_id": trace_id, "case_id": request["case_id"], "session_id": request["session_id"],
        "caller_span_id": CALLER_SPAN_ID, "callee_span_id": CALLEE_SPAN_ID,
        "inspection": TRACE_QUERY_EVIDENCE, "ingestion_verified_by_learner": True,
    })
    accepted["correlation"] = True
    part_a = notebook_parts.write_checkpoint(
        ARTIFACTS / "part_a.json", lab="hosted_delegation", part="a", context=notebook_parts.scope(ENV),
        state={"triage_reference": target, "caller_name": CANDIDATE_NAME, "caller_version": DEPLOYED_VERSION,
               "evaluated_target": evaluated_target,
               "accepted": accepted, "tested_sources": tested_sources, "one_shot_pending_only": True},
        evidence=[ARTIFACTS / name for name in (
            "target.json", "source_evidence.json", "failure_evidence.json",
            "delegation_evidence.json", "trace_evidence.json",
        )],
    )

# %% [markdown]
# Recovery: missing Lab 8/9 evidence requires the producer lab, not Lab 11. Changed candidate
# source, target version or measured bundle requires affected gates again; old `stretch6/part_b.json`
# is explicitly obsolete. No local server was started by these cells. Use reviewed cleanup
# for the separate candidate; keep core release/evaluation evidence intact.
