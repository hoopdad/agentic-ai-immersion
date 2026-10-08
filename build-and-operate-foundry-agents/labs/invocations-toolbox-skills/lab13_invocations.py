# %% [markdown]
# # Lab 13: Batch Invocations
#
# **Prerequisites:** Lab 2.
#
# Build only the stateless batch host, compare deterministic offline facts with a model-assisted nightly run,
# and optionally deploy this Invocations package in its explicit deployment cell.
# No Skills/Responses host is built, invoked, or deployed in this lab.
# Local model-assisted Invocations and Azure deployment may incur charges.
#
# This cell imports the protocol and batch helpers without executing the original notebook's Skills actions.
# %% Step 13.1 - Load batch protocol helpers
from pathlib import Path
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/invocations-toolbox-skills/lab13_invocations.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/invocations-toolbox-skills/lab13_invocations.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("invocations-toolbox-skills/stretch7_invocations.py")

if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted = {}

# %% [markdown]
# This cell compares protocol boundaries and prepares only the Invocations package without deploying the Skills host.
# %% Step 13.2 - Build the batch-only host
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("batch_package", None)
    for row in driver.PROTOCOLS:
        print(f"{row['dimension']}: Invocations = {row['invocations']}; Responses = {row['responses']}")
    record = driver.build(protocols=("invocations",))
    accepted["batch_package"] = True

# %% [markdown]
# This cell executes the deterministic offline batch and checks every source-of-record claim field without model calls.
# %% Step 13.3 - Verify offline batch facts
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("offline_batch", None)
    assert accepted.get("batch_package"), "Prepare the current batch package before invoking it."
    offline_sample = driver.nightly_denials_acceptance_gate(offline=True)
    assert offline_sample["claim_ids"] == driver.nightly_denial_ids()
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "offline_batch.json", offline_sample)
    accepted["offline_batch"] = True

# %% [markdown]
# This cell invokes the nightly denial batch through the local Invocations server and verifies preserved facts and cited explanations.
# %% Step 13.4 - Process the nightly denial scenario
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("nightly_batch", None)
    assert accepted.get("offline_batch"), "Complete the current offline fact gate before the model-assisted batch."
    nightly_sample = driver.nightly_denials_acceptance_gate(offline=False)
    assert nightly_sample["reviews"] == len(driver.nightly_denial_ids())
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "nightly_batch.json", nightly_sample)
    accepted["nightly_batch"] = True

# %% [markdown]
# This cell deploys only the verified Invocations package to Azure and displays its version status.
# %% Step 13.5 - Deploy the batch protocol
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    accepted.pop("deployment", None)
    assert accepted.get("nightly_batch"), "Complete the current nightly batch gate before deployment."
    from deployment import bash_deploy_block
    command = bash_deploy_block(
        driver.INVOCATIONS_DIR, driver.INVOCATIONS_AGENT, "invocations", driver.ENV, check_package=True,
    )
    subprocess.run(["bash", "-lc", command], cwd=driver.INVOCATIONS_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", driver.INVOCATIONS_AGENT], cwd=driver.INVOCATIONS_DIR, check=True)
    accepted["deployment"] = True

# %% [markdown]
# This cell checkpoints the observed batch evidence so a fresh Skills kernel never needs to replay Invocations.
# %% Step 13.6 - Save the batch handoff
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    assert all(accepted.get(key) for key in ("batch_package", "offline_batch", "nightly_batch", "deployment")), (
        "Complete every current Lab 13 gate before publishing its handoff."
    )
    part_a = notebook_parts.write_checkpoint(
        driver.ARTIFACTS / "part_a.json", lab="stretch7", part="a", context=notebook_parts.scope(driver.ENV),
        state={"invocations": record["agents"]["invocations"], "offline": offline_sample, "nightly": nightly_sample, "accepted": accepted},
        evidence=[
            driver.ARTIFACTS / "offline_batch.json", driver.ARTIFACTS / "nightly_batch.json",
            *(driver.REVIEWS_DIR / f"{claim_id}.json" for claim_id in driver.nightly_denial_ids()),
        ],
    )
