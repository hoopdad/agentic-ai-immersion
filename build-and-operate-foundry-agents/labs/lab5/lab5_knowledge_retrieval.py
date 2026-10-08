# %% [markdown]
# # Lab 5: Governed knowledge and grounded retrieval
#
# **Prerequisites:** Lab 4.
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
for folder in (WORKSHOP, WORKSHOP / "labs", WORKSHOP / "shared/hosted-knowledge-sessions"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, notebook_parts
import lab_helpers

ARTIFACTS = WORKSHOP / "labs/artifacts/lab3"
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
CITATIONS_OK = BOUNDARY_OK = False
TESTED_SOURCE_SHA256 = None
lab3 = lab_helpers.load_lab_module("hosted-knowledge-sessions/lab3_hosted_knowledge.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab3.ARTIFACTS

# %% [markdown]
# This cell binds the Lab 4 deployment evidence to the current project and displays the retrieval implementation and source documents.
# %% Step 5.2 - Review prerequisites and knowledge
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    lab_helpers.artifact_path("lab2") / "part_b.json",
    lab="lab2", part="b", context=notebook_parts.scope(ENV))
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
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    lab_helpers.artifact_path("lab2") / "part_b.json",
    lab="lab2", part="b", context=notebook_parts.scope(ENV))
hosted = lab3.build()
knowledge = lab_helpers.require_artifact("lab3", "knowledge.json", through=3, caller="Lab 5")
print(json.dumps(knowledge, indent=2))
print("Review the MCP endpoint, source IDs and account/project scope before retrieval.")

# %% [markdown]
# This cell asks a fresh knowledge-only conversation and requires a governed premium-claim citation without any restart or memory exercise.
# %% Step 5.4 - Verify grounded retrieval
CITATIONS_OK = False
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
if not (CITATIONS_OK and BOUNDARY_OK):
    raise RuntimeError("Complete both knowledge acceptance cells successfully before publishing Lab 5.")
if TESTED_SOURCE_SHA256 != hashlib.sha256((lab3.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after acceptance; rerun the knowledge tests before publishing.")
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab3", part="a", context=notebook_parts.scope(ENV),
    evidence=[ARTIFACTS / "knowledge.json"],
    state={"agent_name": hosted["agent_name"], "citations": "passed",
           "knowledge_boundary": "passed",
           "hosted_source_sha256": TESTED_SOURCE_SHA256})
print("Knowledge complete. Start lab6_walkthrough.ipynb in a fresh kernel; do not rebuild Search.")
