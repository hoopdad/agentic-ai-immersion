# %% [markdown]
# # Stretch 7A: Batch Invocations
#
# Build only the stateless batch host, compare deterministic offline facts with a model-assisted nightly run,
# and optionally deploy this Invocations package in its explicit deployment cell.
# No Skills/Responses host is built, invoked, or deployed in this half.
# Local model-assisted Invocations and Azure deployment may incur charges.
#
# This cell imports the protocol and batch helpers without executing the original notebook's Skills actions.
# %% Step S7.1 - Load batch protocol helpers
from pathlib import Path
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/stretch7-invocations-toolbox-skills/stretch7a_invocations.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/stretch7-invocations-toolbox-skills/stretch7a_invocations.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("stretch7-invocations-toolbox-skills/stretch7_invocations.py")

if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)

# %% [markdown]
# This cell compares protocol boundaries and prepares only the Invocations package without deploying the Skills host.
# %% Step S7.2 - Build the batch-only host
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    for row in driver.PROTOCOLS:
        print(f"{row['dimension']}: Invocations = {row['invocations']}; Responses = {row['responses']}")
    record = driver.build(protocols=("invocations",))

# %% [markdown]
# This cell executes the deterministic offline batch and checks every source-of-record claim field without model calls.
# %% Step S7.3 - Verify offline batch facts
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    offline_sample = driver.nightly_denials_acceptance_gate(offline=True)
    assert offline_sample["claim_ids"] == driver.nightly_denial_ids()
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "offline_batch.json", offline_sample)

# %% [markdown]
# This cell invokes the nightly denial batch through the local Invocations server and verifies preserved facts and cited explanations.
# %% Step S7.4 - Process the nightly denial scenario
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    nightly_sample = driver.nightly_denials_acceptance_gate(offline=False)
    assert nightly_sample["reviews"] == len(driver.nightly_denial_ids())
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "nightly_batch.json", nightly_sample)

# %% [markdown]
# This cell deploys only the verified Invocations package to Azure and displays its version status.
# %% Step S7.5 - Deploy the batch protocol
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    from deployment import bash_deploy_block
    command = bash_deploy_block(
        driver.INVOCATIONS_DIR, driver.INVOCATIONS_AGENT, "invocations", driver.ENV, check_package=True,
    )
    subprocess.run(["bash", "-lc", command], cwd=driver.INVOCATIONS_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", driver.INVOCATIONS_AGENT], cwd=driver.INVOCATIONS_DIR, check=True)

# %% [markdown]
# This cell checkpoints the observed batch evidence so a fresh Skills kernel never needs to replay Invocations.
# %% Step S7.6 - Save the batch handoff
if "__file__" not in globals():
    (driver.ARTIFACTS / "part_a.json").unlink(missing_ok=True)
    (driver.ARTIFACTS / "part_b.json").unlink(missing_ok=True)
    part_a = notebook_parts.write_checkpoint(
        driver.ARTIFACTS / "part_a.json", lab="stretch7", part="a", context=notebook_parts.scope(driver.ENV),
        state={"invocations": record["agents"]["invocations"], "offline": offline_sample, "nightly": nightly_sample},
        evidence=[
            driver.ARTIFACTS / "offline_batch.json", driver.ARTIFACTS / "nightly_batch.json",
            *(driver.REVIEWS_DIR / f"{claim_id}.json" for claim_id in driver.nightly_denial_ids()),
        ],
    )
