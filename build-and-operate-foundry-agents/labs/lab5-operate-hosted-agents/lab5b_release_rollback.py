# %% [markdown]
# # Lab 5B: Release gates, promotion, and rollback
#
# Start a fresh kernel after Lab 5A; gate its saved model evaluation rather than evaluating again.
# An intentionally corrupted response demonstrates regression detection, then the unchanged measured baseline is restored.
# This is a release-control exercise, not a claim that the agent improved.
# Promotion and rollback use the approved operator workflow; notebook dry runs never pretend to deploy.
#
# This cell loads A's durable bundle and existing release utilities without creating models or reevaluating responses.
# %% Step 5.1 - Load measured release evidence
from pathlib import Path
import copy
import json
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/lab5-operate-hosted-agents/lab5b_release_rollback.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/lab5-operate-hosted-agents/lab5b_release_rollback.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import foundry_env, notebook_parts

driver = lab_helpers.load_lab_module("lab5-operate-hosted-agents/lab5_operate.py")
gate = lab_helpers.load_lab_module("lab5-operate-hosted-agents/eval_gate.py")
promotion = lab_helpers.load_lab_module("lab5-operate-hosted-agents/promote.py")


def gate_rows(rows: list[dict], errors: list[str] | None = None) -> dict:
    incomplete = [
        f"row {index}: missing measured {metric} judge score"
        for index, row in enumerate(rows, 1) for metric in ("groundedness", "relevance")
        if not isinstance(row.get("scores"), dict) or row["scores"].get(metric) is None
    ]
    return gate.evaluate_gate(
        rows, min_groundedness=driver.PASS_THRESHOLD,
        min_relevance=driver.PASS_THRESHOLD, strict=True, input_errors=[*(errors or []), *incomplete],
    )


if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    part_a = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(driver.ENV),
    )
    bundle = part_a["state"]["bundle"]
    rows, load_errors = gate.load_results(gate.RESULTS_PATH)
    assert not load_errors and len(rows) == part_a["state"]["summary"]["questions"]

# %% [markdown]
# This cell recomputes deterministic release rules on A's exact responses and applies strict thresholds to its saved judge scores.
# %% Step 5.2 - Gate the measured baseline
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    baseline_gate = gate_rows(rows, load_errors)
    gate.write_outputs(baseline_gate)
    assert baseline_gate["passed"], baseline_gate["failures"]
    driver.print_version_operations()

# %% [markdown]
# This cell demonstrates blocked promotion using a deliberately unsafe copy of one response while preserving A's measured files.
# %% Step 5.3 - Reject a release regression
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    broken_rows = copy.deepcopy(rows)
    broken_rows[0]["response"] = "You should choose Gold Plus."
    broken_gate = gate_rows(broken_rows)
    assert not broken_gate["passed"] and broken_gate["no_recommendation_violations"]
    gate.write_outputs(broken_gate)
    try:
        promotion.check_gate()
    except ValueError:
        print("PASS: promotion rejected the unsafe response.")
    else:
        raise AssertionError("Promotion accepted a failed release gate.")
    foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "regression_gate.json"), broken_gate)

# %% [markdown]
# This cell restores the exact baseline gate without model calls and records recovered release evidence in the original artifact contract.
# %% Step 5.4 - Recover the known-good release evidence
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    recovered_gate = gate_rows(rows, load_errors)
    assert recovered_gate["passed"], recovered_gate["failures"]
    gate.write_outputs(recovered_gate)
    foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "operate.json"), {
        **bundle["info"],
        "release_recovery": {"reused_evaluation": True, "gate_evaluated_at": recovered_gate["evaluated_at"]},
    })

# %% [markdown]
# ## YOUR TURN: rehearse a gated promotion
#
# Inspect active and previous versions in Foundry and enter your proposed target and release tag below.
# An authorized release administrator owns target configuration, approvals, deployment, and smoke tests
# through the optional operator workflow; learners do not edit operator environment files or execute terminal commands.
# This notebook records only a validated `dry-run`, not a successful cloud release.
#
# This cell validates the recovered gate and prepares a target-environment promotion without executing a deployment.
# %% Step 5.5 - Prepare a gated promotion
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    TARGET_ENVIRONMENT = "test"
    RELEASE_TAG = ""  # Enter your proposed release tag; this notebook does not create it.
    assert TARGET_ENVIRONMENT in promotion.ORDER, "Choose a supported target environment."
    assert RELEASE_TAG and "REPLACE" not in RELEASE_TAG and "<" not in RELEASE_TAG, "Enter a real proposed release tag."
    subprocess.run(["git", "check-ref-format", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT, check=True)
    validated_gate = promotion.check_gate()
    print(f"Promotion rehearsal: target={TARGET_ENVIRONMENT}, tag={RELEASE_TAG}; dry-run only, not deployed.")
    promotion.record(validated_gate, TARGET_ENVIRONMENT, RELEASE_TAG, "dry-run")

# %% [markdown]
# ## YOUR TURN: rehearse rollback
#
# Inspect the known-good source revision and its gate evidence; the opt-in workflow in `.github/workflows/agent-ci.yml`
# owns approved rollback execution and its deployed smoke test.
# Enter the active and known-good version labels you inspected, retain a recovery plan, and never equate rehearsal with activation.
# Multi-replica state migration and automatic rollback are outside this notebook's scope.
#
# This cell records your inspected rollback plan and completes B only with passing recovered evaluation evidence.
# %% Step 5.6 - Retain version and rollback evidence
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    ACTIVE_VERSION = ""  # Enter the version inspected in Foundry.
    KNOWN_GOOD_VERSION = ""  # Enter the retained, validated rollback version.
    KNOWN_GOOD_REVISION = ""  # Enter its source revision for the approved operator workflow.
    assert ACTIVE_VERSION and KNOWN_GOOD_VERSION and KNOWN_GOOD_REVISION, "Inspect and enter real version/source labels."
    release_plan = {
        "active_version": ACTIVE_VERSION, "known_good_version": KNOWN_GOOD_VERSION,
        "known_good_revision": KNOWN_GOOD_REVISION,
        "promotion": "dry-run", "rollback": "rehearsal; not executed",
        "operator_workflow": str(driver.WORKFLOW_FILE.relative_to(ROOT)),
        "gate_evaluated_at": recovered_gate["evaluated_at"],
    }
    foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "release_plan.json"), release_plan)
    part_b = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("lab5", "part_b.json"), lab="lab5", part="b", context=notebook_parts.scope(driver.ENV),
        state={"recovered_gate": recovered_gate, "release_plan": release_plan},
        evidence=[
            gate.RESULTS_PATH, gate.GATE_PATH, lab_helpers.artifact_path("lab5", "operate.json"),
            lab_helpers.artifact_path("lab5", "regression_gate.json"),
            lab_helpers.artifact_path("lab5", "release_plan.json"), promotion.PROMOTIONS_PATH,
        ],
    )
