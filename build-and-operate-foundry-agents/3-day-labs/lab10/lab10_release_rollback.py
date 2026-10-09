# %% [markdown]
# # Lab 10: Release gates, promotion, and rollback
#
# **Prerequisites:** Lab 9.
# **Required learning/artifacts:** scoped `lab5/part_a.json`, exact evaluated bundle, responses, scores and target fingerprints.
# **Recommended route:** finish core Labs 1-10, then select optional Labs 11-14 without concurrent port/source/quota use.
# **Primary delta / lineage (continue evidence):** gate the measured candidate; do not rerun judges or mutate its product.
# **Acceptance and recovery:** unsafe copied response blocks promotion, unchanged baseline restores a passing gate.
# Default promotion/rollback are rehearsals, not live operations. Extension candidates must have separate names/versions.
# Changed runtime, questions or evidence requires Lab 9 then Steps 10.1-10.6, never stale PASS reuse.
# No server is started here; retain release evidence and review cleanup without deleting rollback inputs.
#
# Start a fresh kernel after Lab 9; gate its saved model evaluation rather than evaluating again.
# An intentionally corrupted response demonstrates regression detection, then the unchanged measured baseline is restored.
# This is a release-control exercise, not a claim that the agent improved.
# Promotion and rollback use the approved operator workflow; notebook dry runs never pretend to deploy.
#
# This cell loads Lab 9's durable bundle and existing release utilities without creating models or reevaluating responses.
# %% Step 10.1 - Load measured release evidence
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/3-day-labs/lab10/lab10_release_rollback.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/3-day-labs/lab10/lab10_release_rollback.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "3-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import foundry_env, notebook_parts

driver = lab_helpers.load_lab_module("operate-hosted-agents/lab5_operate.py")
gate = lab_helpers.load_lab_module("operate-hosted-agents/eval_gate.py")
promotion = lab_helpers.load_lab_module("operate-hosted-agents/promote.py")


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
    accepted = {}
    part_a = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(driver.ENV),
    )
    bundle = part_a["state"]["bundle"]
    bundle_path = lab_helpers.artifact_path("lab5", "evaluation_bundle.json")
    assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == part_a["state"].get("bundle_sha256"), (
        "Lab 9 bundle changed; rerun Lab 9 evaluation before release gating."
    )
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == bundle
    driver.validate_evaluated_target(bundle["info"]["evaluated_target"], bundle["hosted"], bundle["knowledge"])
    rows, load_errors = gate.load_results(gate.RESULTS_PATH)
    assert not load_errors and len(rows) == part_a["state"]["summary"]["questions"]

# %% [markdown]
# This cell recomputes deterministic release rules on Lab 9's exact responses and applies strict thresholds to its saved judge scores.
# %% Step 10.2 - Gate the measured baseline
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("baseline_gate", None)
    notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(driver.ENV))
    driver.validate_evaluated_target(bundle["info"]["evaluated_target"], bundle["hosted"], bundle["knowledge"])
    baseline_gate = gate_rows(rows, load_errors)
    baseline_gate["evaluation_bundle_sha256"] = part_a["state"]["bundle_sha256"]
    baseline_gate["evaluation_results_sha256"] = hashlib.sha256(gate.RESULTS_PATH.read_bytes()).hexdigest()
    gate.write_outputs(baseline_gate)
    assert baseline_gate["passed"], baseline_gate["failures"]
    driver.print_version_operations()
    accepted["baseline_gate"] = True

# %% [markdown]
# This cell demonstrates blocked promotion using a deliberately unsafe copy of one response while preserving Lab 9's measured files.
# %% Step 10.3 - Reject a release regression
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("regression", None)
    assert accepted.get("baseline_gate"), "Complete the current baseline gate."
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
    accepted["regression"] = True

# %% [markdown]
# This cell restores the exact baseline gate without model calls and records recovered release evidence in the original artifact contract.
# %% Step 10.4 - Recover the known-good release evidence
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("recovery", None)
    assert accepted.get("regression"), "Observe the current regression failure before recovery."
    notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(driver.ENV))
    driver.validate_evaluated_target(bundle["info"]["evaluated_target"], bundle["hosted"], bundle["knowledge"])
    recovered_gate = gate_rows(rows, load_errors)
    recovered_gate["evaluation_bundle_sha256"] = part_a["state"]["bundle_sha256"]
    recovered_gate["evaluation_results_sha256"] = hashlib.sha256(gate.RESULTS_PATH.read_bytes()).hexdigest()
    assert recovered_gate["passed"], recovered_gate["failures"]
    gate.write_outputs(recovered_gate)
    foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "operate.json"), {
        **bundle["info"],
        "release_recovery": {"reused_evaluation": True, "gate_evaluated_at": recovered_gate["evaluated_at"]},
    })
    accepted["recovery"] = True

# %% [markdown]
# ## YOUR TURN: rehearse a gated promotion
#
# Inspect active and previous versions in Foundry and enter your proposed target and release tag below.
# An authorized release administrator owns target configuration, approvals, deployment, and smoke tests
# through the optional operator workflow; learners do not edit operator environment files or execute terminal commands.
# This notebook records only a validated `dry-run`, not a successful cloud release.
#
# This cell validates the recovered gate and prepares a target-environment promotion without executing a deployment.
# %% Step 10.5 - Prepare a gated promotion
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("promotion_rehearsal", None)
    assert accepted.get("recovery"), "Complete the current recovered gate before promotion rehearsal."
    TARGET_ENVIRONMENT = "test"
    RELEASE_TAG = ""  # Enter your proposed release tag; this notebook does not create it.
    assert TARGET_ENVIRONMENT in promotion.ORDER, "Choose a supported target environment."
    assert RELEASE_TAG and "REPLACE" not in RELEASE_TAG and "<" not in RELEASE_TAG, "Enter a real proposed release tag."
    subprocess.run(["git", "check-ref-format", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT, check=True)
    validated_gate = promotion.check_gate()
    print(f"Promotion rehearsal: target={TARGET_ENVIRONMENT}, tag={RELEASE_TAG}; dry-run only, not deployed.")
    promotion.record(validated_gate, TARGET_ENVIRONMENT, RELEASE_TAG, "dry-run")
    accepted["promotion_rehearsal"] = True

# %% [markdown]
# ## YOUR TURN: rehearse rollback
#
# Inspect the known-good source revision and its gate evidence; the opt-in workflow in `.github/workflows/agent-ci.yml`
# owns approved rollback execution and its deployed smoke test.
# Enter the active and known-good version labels you inspected, retain a recovery plan, and never equate rehearsal with activation.
# Multi-replica state migration and automatic rollback are outside this notebook's scope.
#
# This cell records your inspected rollback plan and completes Lab 10 only with passing recovered evaluation evidence.
# %% Step 10.6 - Retain version and rollback evidence
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("rollback_rehearsal", None)
    assert all(accepted.get(key) for key in ("baseline_gate", "regression", "recovery", "promotion_rehearsal")), (
        "Complete every current release gate before retaining rollback evidence."
    )
    promotion.check_gate()
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
        "evaluation_bundle_sha256": part_a["state"]["bundle_sha256"],
        "evaluated_target": bundle["info"]["evaluated_target"],
    }
    foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "release_plan.json"), release_plan)
    accepted["rollback_rehearsal"] = True
    part_b = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("lab5", "part_b.json"), lab="lab5", part="b", context=notebook_parts.scope(driver.ENV),
        state={"recovered_gate": recovered_gate, "release_plan": release_plan, "accepted": accepted},
        evidence=[
            gate.RESULTS_PATH, gate.GATE_PATH, lab_helpers.artifact_path("lab5", "operate.json"),
            lab_helpers.artifact_path("lab5", "regression_gate.json"),
            lab_helpers.artifact_path("lab5", "release_plan.json"), promotion.PROMOTIONS_PATH,
        ],
    )
