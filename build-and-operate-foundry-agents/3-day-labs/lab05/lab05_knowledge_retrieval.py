# %% [markdown]
# # Lab 5: Governed knowledge and grounded retrieval
#
# **Prerequisites:** Lab 4.
# **Required learning/artifacts:** scoped `lab2/part_b.json`, Lab 3 tested source and deployed hosting concepts.
# **Recommended route:** core Labs 1-10 in order; next Lab 6.
# **Primary delta / lineage (extend):** add governed retrieval to a distinct knowledge product, retaining
# only the accepted `get_sponsor` implementation and rule 3 handoff policy, not copying the whole earlier agent.
# The knowledge product adds plan tools; the old no-search/no-knowledge limitation is deliberately replaced.
# **Acceptance and recovery:** require a citation, retained sponsor/AEP refusal, and an honest missing-knowledge failure.
# Restore Labs 3-4 for changed predecessor source; rerun Steps 5.3-5.6 for changed knowledge/package evidence.
# Owned local processes stop in `finally`; Search cleanup is reviewed and attendee-scoped, not automatic.
#
# Start in a fresh Python 3.14 dev-container kernel after Lab 4. Build attendee-scoped Search
# indexes, knowledge sources, Foundry IQ knowledge base and project connection. These explicit
# cloud writes and embedding/retrieval calls incur charges and need Search/project permissions.
# This lab tests knowledge citations only; it does not restart a conversation or claim durability.
#
# This cell imports existing knowledge definitions without executing their build or session demonstrations.
# %% Step 5.1 - Import knowledge definitions
import hashlib
import inspect
import json
from pathlib import Path
import sys
import uuid

HERE = Path.cwd().resolve()
REPO_ROOT = next(p for p in (HERE, *HERE.parents)
                 if (p / "build-and-operate-foundry-agents/common/resource_names.py").is_file())
WORKSHOP = REPO_ROOT / "build-and-operate-foundry-agents"
for folder in (WORKSHOP, WORKSHOP / "3-day-labs", WORKSHOP / "shared/hosted-knowledge-sessions"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, notebook_parts
import lab_helpers

ARTIFACTS = WORKSHOP / "3-day-labs/artifacts/lab3"
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
CITATIONS_OK = BOUNDARY_OK = RETAINED_BEHAVIOR_OK = False
TESTED_SOURCE_SHA256 = None
lab3 = lab_helpers.load_lab_module("hosted-knowledge-sessions/lab3_hosted_knowledge.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab3.ARTIFACTS

# %% [markdown]
# This cell binds the Lab 4 deployment evidence to the current project and displays the retrieval implementation and source documents.
# %% Step 5.2 - Review prerequisites and knowledge
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
deployed_basics = notebook_parts.read_checkpoint(
    lab_helpers.artifact_path("lab2") / "part_b.json",
    lab="lab2", part="b", context=notebook_parts.scope(ENV))
if deployed_basics["state"].get("version_routing") != "fixed-100-percent":
    raise RuntimeError("Lab 4 fixed-version acceptance is missing; rerun Lab 4's invocation and publication.")
accepted_basics = notebook_parts.read_checkpoint(
    lab_helpers.artifact_path("lab2") / "part_a.json",
    lab="lab2", part="a", context=notebook_parts.scope(ENV))
basics = lab_helpers.load_lab_module("hosted-agent-basics/lab2_hosted_basics.py")
if accepted_basics["state"].get("hosted_source_sha256") != hashlib.sha256(
        (basics.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Lab 3 source changed; rerun Labs 3-4 acceptance before extending it.")
print(inspect.getsource(lab3.knowledge_base.build_index))
print(inspect.getsource(lab3.knowledge_base.build_knowledge_base))
print((lab3.HOSTED_DIR / "main.py").read_text(encoding="utf-8"))
for source in sorted((WORKSHOP / "data/knowledge").rglob("*.md")):
    print(f"\n--- {source.relative_to(WORKSHOP)} ---\n{source.read_text(encoding='utf-8')}")

# %% [markdown]
# This cell explicitly builds Search knowledge and its project connection, prepares the package and preserves knowledge.json plus hosted.json.
# %% Step 5.3 - Build governed knowledge
CITATIONS_OK = False
BOUNDARY_OK = False
RETAINED_BEHAVIOR_OK = False
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    lab_helpers.artifact_path("lab2") / "part_b.json",
    lab="lab2", part="b", context=notebook_parts.scope(ENV))
hosted = lab3.build()
print((lab3.HOSTED_DIR / "common/accepted_concierge.py").read_text(encoding="utf-8"))
knowledge = lab_helpers.require_artifact("lab3", "knowledge.json", through=3, caller="Lab 5")
print(json.dumps(knowledge, indent=2))
print("Review the MCP endpoint, source IDs and account/project scope before retrieval.")

# %% [markdown]
# This cell requires a governed citation and the retained sponsor/enrollment behavior in fresh local conversations.
# %% Step 5.4 - Verify grounded retrieval
CITATIONS_OK = False
RETAINED_BEHAVIOR_OK = False
TESTED_SOURCE_SHA256 = hashlib.sha256((lab3.HOSTED_DIR / "main.py").read_bytes()).hexdigest()
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
server = lab3.HostedProcess(knowledge).start()
try:
    grounded, payload = lab3.ask(
        lab3.DEFAULT_PORT, "What proof of payment do you accept for a premium claim?",
        f"knowledge-only-{uuid.uuid4().hex[:8]}")
    print(grounded)
    assert "[KB-ACC-001]" in grounded, "The answer must cite the governed premium-claim rule."
    sponsor, _ = lab3.ask(
        lab3.DEFAULT_PORT, f"{lab_helpers.identity_line('P-1001')} "
        "Who is my plan sponsor and how much is the HRA for the year?",
        f"retained-sponsor-{uuid.uuid4().hex[:8]}")
    assert "Northwind" in sponsor and "$3,600" in sponsor, "Lab 3 sponsor behavior was lost."
    refusal, _ = lab3.ask(
        lab3.DEFAULT_PORT, f"{lab_helpers.identity_line('P-1001')} "
        "Which plan should I pick? Please enroll me.",
        f"retained-policy-{uuid.uuid4().hex[:8]}")
    assert "AEP" in refusal and "advisor" in refusal.lower(), "Lab 3 enrollment handoff was lost."
    from common import guardrails
    assert not guardrails.contains_recommendation(refusal), "The agent must not recommend a plan."
    RETAINED_BEHAVIOR_OK = True
    CITATIONS_OK = True
finally:
    server.stop()

# %% [markdown]
# ## YOUR TURN: explain the evidence boundary
#
# Compare the answer with KB-ACC-001 in `data/knowledge`. A citation is not proof of freshness
# or correctness. Next test a separate conversation with retrieval removed: it must admit the
# missing rule, not fabricate a citation. This is a knowledge-availability test, not a restart test.
#
# This cell starts an independent no-knowledge process and verifies honest unavailable-knowledge behavior.
# %% Step 5.5 - Test unavailable knowledge
BOUNDARY_OK = False
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
server = lab3.HostedProcess(knowledge, env_overrides={"MARKETPLACE_KB_MCP_URL": None}).start()
try:
    unavailable, _ = lab3.ask(
        lab3.DEFAULT_PORT, "What proof of payment do you accept for a premium claim?",
        f"no-knowledge-{uuid.uuid4().hex[:8]}")
    print(unavailable)
    assert "[KB-" not in unavailable, "Unavailable knowledge must not yield an invented citation."
    assert "not at hand" in unavailable.lower(), "The answer must explain its knowledge boundary."
    BOUNDARY_OK = True
finally:
    server.stop()

# %% [markdown]
# This cell saves retrieval acceptance bound to the existing knowledge artifact and exact hosted source for Lab 6.
# %% Step 5.6 - Publish knowledge checkpoint
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if not (CITATIONS_OK and BOUNDARY_OK and RETAINED_BEHAVIOR_OK):
    raise RuntimeError("Complete both knowledge acceptance cells successfully before publishing Lab 5.")
if TESTED_SOURCE_SHA256 != hashlib.sha256((lab3.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after acceptance; rerun the knowledge tests before publishing.")
if hosted["retained_behavior"]["transfer_sha256"] != hashlib.sha256(
        (lab3.HOSTED_DIR / "common/accepted_concierge.py").read_bytes()).hexdigest():
    raise RuntimeError("Transferred sponsor/policy changed; rerun Lab 5 acceptance.")
foundry_env.save_artifact(ARTIFACTS / "accepted_behavior.json", hosted["retained_behavior"])
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab3", part="a", context=notebook_parts.scope(ENV),
    evidence=[ARTIFACTS / "knowledge.json", ARTIFACTS / "accepted_behavior.json"],
    state={"agent_name": hosted["agent_name"], "citations": "passed",
           "knowledge_boundary": "passed",
           "retained_behavior": hosted["retained_behavior"],
           "retained_behavior_acceptance": "passed",
           "hosted_source_sha256": TESTED_SOURCE_SHA256})
print("Knowledge complete. Start lab06_walkthrough.ipynb in a fresh kernel; do not rebuild Search.")
