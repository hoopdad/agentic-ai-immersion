"""Generate the one-day track from canonical three-day sources; never edit the canonical track."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from py_to_ipynb import build_notebook, split_cells, validate_cell_descriptions, validate_step_ids

ROOT = Path(__file__).resolve().parents[1]
SELECTED = (1, 4, 7)
EXCLUDED = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".azure", ".venv", "venv",
    "common", "data", "artifacts", "sessions", ".git", ".vendored", ".vendored.json",
}


def replace_once(text: str, before: str, after: str, label: str) -> str:
    if text.count(before) != 1:
        raise ValueError(f"{label}: expected exactly one adaptation anchor {before!r}; review the upstream change.")
    return text.replace(before, after, 1)


def short_paths(text: str) -> str:
    return text.replace("3-day-labs/", "1-day-labs/").replace('"3-day-labs"', '"1-day-labs"')


def short_checkpoint_imports(text: str) -> str:
    def replace_import(match: re.Match) -> str:
        indent, names = match.groups()
        items = [name.strip() for name in names.split(",")]
        if "notebook_parts" not in items:
            return match.group(0)
        remaining = [name for name in items if name != "notebook_parts"]
        return ((indent + "from common import " + ", ".join(remaining) + "\n") if remaining else "") \
            + indent + "import one_day_parts as notebook_parts"
    return re.sub(r"^(\s*)from common import ([\w ,]+)$", replace_import, text, flags=re.MULTILINE)


def source_for(canonical: Path, number: int) -> Path:
    sources = list((canonical / f"lab{number:02d}").glob("*.py"))
    if len(sources) != 1:
        raise ValueError(f"Lab {number}: expected one canonical authoring source.")
    return sources[0]


def adapt_team_source(canonical: Path) -> tuple[str, str]:
    path = source_for(canonical, 7)
    text = short_paths(path.read_text(encoding="utf-8"))
    intro_end = text.index("# This cell imports")
    text = (
        "# %% [markdown]\n# # Lab 7: Build and host a multi-agent team\n#\n"
        "# **Prerequisites:** Lab 4's accepted deployed Responses checkpoint.\n"
        "# **Recommended route:** one-day Labs 1 -> 4 -> 7 (capstone).\n"
        "# Turn one hosted agent into a separate code-defined specialist team: parallel work,\n"
        "# structured merge, compliance review, a human approval boundary and Foundry hosting.\n"
        "# MAF supplies orchestration; Foundry supplies container hosting and versioned invocation.\n"
        "# Use synthetic data and local knowledge tools; no Search, Lab 6 or Prompt Agents required.\n"
        "# Edit the isolated product under `../products/hosted-multi-agent-handoff/hosted/`.\n"
        "# Acceptance requires a changed classifier, explicit decisions and fixed-version invocation.\n"
        "# No restart exercise, distributed recovery, production advisor authorization or evaluation claim.\n"
        "# Model calls and deployment incur charges. Stop owned processes; use a fresh kernel.\n#\n"
    ) + text[intro_end:]
    # Retain upstream helper/baseline/classifier cells, not unsafe-instruction or long-track handoffs.
    start = text.index("# %% [markdown]\n# ## YOUR TURN: reject an unsafe specialist draft")
    end = text.index("# %% [markdown]\n# ## YOUR TURN: model-based classification")
    text = text[:start] + text[end:]
    end = text.index("# %% [markdown]\n# This cell records validated intermediate evidence")
    text = text[:end]
    text = replace_once(text, "Step 7.4 - Verify ambiguous", "Step 7.3 - Verify ambiguous", "team numbering")
    text = text.replace("Restore the safe specialist instruction, then add", "Add")
    text = text.replace("../../shared/hosted-multi-agent-handoff/", "../products/hosted-multi-agent-handoff/")
    text = text.replace("driver.build(standalone=False)", "driver.build(standalone=True)")
    text = replace_once(text, '    accepted["orchestration"] = True',
                        '    print(driver.SERVER_LOG.read_text(encoding="utf-8", errors="replace"))\n'
                        '    accepted["orchestration"] = True', "observed team execution")
    text = replace_once(text, "    accepted = {}", """    accepted = {}
    prerequisite = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab2", "part_b.json"), lab="lab2", part="b",
        context=notebook_parts.scope(driver.ENV))
    assert prerequisite["state"].get("deployed_inference") == "passed", "Complete Lab 4 deployed inference."
    import inspect
    workflow_source = (driver.HOSTED_DIR / "marketplace_workflow.py").read_text(encoding="utf-8")
    print(workflow_source)
    print("intake -> marketplace + accounts -> merge -> compliance -> human review")
    print(inspect.getsource(driver.deployed_turn))
""", "team prerequisite")
    return path.name, text + (Path(__file__).with_name("one_day_team_finish.py")).read_text(encoding="utf-8")


def adapt_source(canonical: Path, number: int) -> tuple[str, str]:
    if number == 7:
        name, text = adapt_team_source(canonical)
        return name, short_checkpoint_imports(text)
    path = source_for(canonical, number)
    text = short_paths(path.read_text(encoding="utf-8"))
    if number == 1:
        text = text[:text.index("# %% [markdown]\n# ## Checkpoint")]
        start = text.index("# This cell locates")
        text = (
            "# %% [markdown]\n# # Lab 1: Project, identity and chat inference\n#\n"
            "# **Prerequisites:** Administrator-approved Foundry account, network, chat quota and permissions.\n"
            "# **Recommended route:** one-day Labs 1 -> 4 -> 7.\n"
            "# Establish approved identity/project scope, deploy only a chat model and verify inference.\n"
            "# No embedding model or RAG setup. Hosting enablement and roles remain administrator-owned.\n"
            "# Provisioning and inference incur charges; review each explicit approval before acting.\n"
            "# Save scope-bound chat evidence for Lab 4; never fabricate acceptance or broaden permissions.\n"
            "# Use a fresh Python 3.14 dev-container kernel; run all cells in order.\n#\n"
        ) + text[start:]
        text = replace_once(text, "import project_setup", "import project_setup\nfrom common import foundry_env",
                            "setup environment import")
        text += Path(__file__).with_name("one_day_setup_finish.py").read_text(encoding="utf-8")
        text = replace_once(text, "for folder in (WORKSHOP, LAB_DIR):",
                            'for folder in (WORKSHOP, LAB_DIR, WORKSHOP / "1-day-labs"):',
                            "setup checkpoint imports")
    elif number == 4:
        local = short_paths(source_for(canonical, 3).read_text(encoding="utf-8"))
        local = replace_once(local, 'print("Lab 3 complete. Open lab04_walkthrough.ipynb in a fresh kernel to deploy.")',
                             'print("Local acceptance passed. Continue below to deploy this exact source.")',
                             "local completion")
        title_end = local.index("# This cell imports")
        intro = (
            "# %% [markdown]\n# # Lab 4: Build, test, deploy, and invoke a hosted agent\n#\n"
            "# **Prerequisites:** Lab 1's verified project and chat inference. No separate Lab 2 or 3 is required.\n"
            "# **One-day route:** Lab 1 -> Lab 4 -> Lab 7 team capstone.\n"
            "# This condensed lab includes Lab 3's real local acceptance before Lab 4's deployment.\n"
            "# Edit the isolated product in `../products/hosted-agent-basics/hosted/main.py`.\n"
            "# Preserve sponsor facts, the enrollment-window refusal, and source fingerprints.\n"
            "# Local model calls and hosted deployment incur charges; review each explicit action.\n"
            "# Recovery: rerun the local gates after source changes, never fabricate their checkpoint.\n#\n"
        )
        local = intro + local[title_end:]
        local = local.replace("../../shared/hosted-agent-basics/", "../products/hosted-agent-basics/")
        local = local.replace("Steps 3.", "Steps 4.").replace("Lab 3.", "this local phase.")
        local = re.sub(r"Step 3\.(\d+)", lambda m: f"Step 4.{m[1]}", local)
        local = replace_once(local, "import sys", "import subprocess\nimport sys", "deployment imports")
        local = local.replace('caller="Lab 3"', 'caller="Lab 4"').replace("publishing Lab 3", "publishing local acceptance")
        local = replace_once(local, 'for model in ("chat", "embedding")', 'for model in ("chat",)', "chat-only prerequisite")
        local = replace_once(local, '    "EMBEDDING_MODEL_DEPLOYMENT_NAME": project.get("embedding_deployment", {}).get("name"),\n', '', "remove embedding prerequisite")
        local = local.replace("Lab 2", "Lab 1").replace("Labs 1-2", "Lab 1")
        local = local.replace("No separate Lab 1 or 3", "No separate Lab 2 or 3")
        blocks = split_cells(text, notebook_safe=False)
        deployment = []
        include = False
        for kind, lines in blocks:
            raw = "\n".join(lines)
            if kind == "code" and "# Step 4.2 -" in raw:
                include = True
            if include:
                if kind == "markdown":
                    deployment.append("# %% [markdown]\n" + "\n".join("# " + line if line else "#" for line in lines))
                elif kind == "code":
                    raw = re.sub(r"Step 4\.(\d+)", lambda m: f"Step 4.{int(m[1]) + 7}", raw)
                    deployment.append("# %%\n" + raw)
        if not deployment:
            raise ValueError("Lab 4 deployment cells changed; review the one-day adapter.")
        text = local + (
            "\n# %% [markdown]\n"
            "# This cell validates the just-tested local phase before deployment; it does not rerun cloud setup.\n"
        ) + "\n\n".join(deployment) + "\n"
        text = text.replace("rerun Lab 3", "rerun this lab's local phase")
        text = text.replace("rerun its local acceptance cells", "rerun the local acceptance cells above")
        text = text.replace("repeat Labs 3-4 acceptance", "repeat this lab's local and deployed acceptance")
        text = text.replace("Lab 3 source", "Local source")
        text = text.replace("Lab 3 acceptance", "this lab's local acceptance")
        text = text.replace("consumed by Lab 5", "available to the optional extension")
        text = text.replace("Continue with lab05_walkthrough.ipynb.", "Continue with lab07_walkthrough.ipynb to build and host a multi-agent team.")
    else:
        text = text.replace("core Labs 1-10 in order", "one-day Labs 1, 2, and 4 in order")
        text = text.replace("core Labs 1-10 first, then selected optional branches", "one-day Labs 1, 2, and 4 first")
        text = text.replace("next Lab 3, not a protocol branch yet", "next Lab 4, including local acceptance")
        text = text.replace("Next: lab03_walkthrough.ipynb", "Next: lab04_walkthrough.ipynb")
        text = text.replace("lab03_walkthrough.ipynb", "lab04_walkthrough.ipynb")
    text = text.replace("ROOT / \"shared\"", "ROOT / \"1-day-labs/products\"")
    return path.name, short_checkpoint_imports(text)


def product_files(root: Path) -> dict[str, bytes]:
    result = {}
    for topic in ("hosted-agent-basics", "hosted-multi-agent-handoff"):
        source = root / "shared" / topic
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if not path.is_file() or path.is_symlink() or EXCLUDED.intersection(relative.parts):
                continue
            if path.name.startswith(".env") or path.suffix in {".pyc", ".pyo", ".log"}:
                continue
            if path.suffix not in {".py", ".md", ".txt", ".yaml", ".yml"} \
                    and path.name not in {"Dockerfile", ".agentignore", ".gitignore"}:
                continue
            data = path.read_bytes()
            if path.suffix in {".py", ".md"}:
                text = short_paths(data.decode("utf-8"))
                text = text.replace(f"shared/{topic}/", f"1-day-labs/products/{topic}/")
                if path.suffix == ".py":
                    if "ROOT = SOURCE_PATH.parents[2]" in text:
                        text = replace_once(text, "ROOT = SOURCE_PATH.parents[2]", "ROOT = SOURCE_PATH.parents[3]", str(path))
                    if "ROOT = HERE.parents[2]" in text:
                        text = replace_once(text, "ROOT = HERE.parents[2]", "ROOT = HERE.parents[3]", str(path))
                    text = text.replace("HERE.parents[2] /", "HERE.parents[3] /")
                    text = text.replace("HERE.parents[2] if len(HERE.parents) > 2",
                                        "HERE.parents[3] if len(HERE.parents) > 3")
                    if topic == "hosted-agent-basics" and path.name == "lab2_hosted_basics.py":
                        text = text.replace('for model in ("chat", "embedding")', 'for model in ("chat",)')
                        text = text.replace("Labs 1-2", "Lab 1")
                    text = text.replace("ROOT = LAB_DIR.parents[1]", "ROOT = LAB_DIR.parents[2]")
                    if topic == "hosted-multi-agent-handoff":
                        if path.name == "marketplace_specialists.py":
                            text = replace_once(text, 'KB_MCP_URL = os.environ.get("MARKETPLACE_KB_MCP_URL", "")',
                                                'KB_MCP_URL = ""  # One-day team uses synthetic local knowledge only.',
                                                "local team knowledge")
                        if path.name == "lab4_hosted_multi_agent.py":
                            start = text.index("def require_previous_lab(")
                            end = text.index("\n\n# %% [markdown]", start)
                            text = text[:start] + '''def require_previous_lab(standalone: bool = False) -> dict:
    """Restore the accepted one-day Lab 4, never Lab 6 knowledge evidence."""
    from common import notebook_parts
    checkpoint = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab2", "part_b.json"), lab="lab2", part="b",
        context=notebook_parts.scope(ENV))
    if checkpoint["state"].get("deployed_inference") != "passed":
        raise RuntimeError("Complete one-day Lab 4 deployed inference before building the team.")
    return lab_helpers.require_artifact("lab2", "hosted.json", 2, "Lab 7")
''' + text[end:]
                            text = text.replace('env.get("MARKETPLACE_KB_MCP_URL")', 'False')
                            text = replace_once(text, '''env.setdefault(
            "MARKETPLACE_SESSION_DIR", str(ARTIFACTS / "sessions")
        )''', '''env["MARKETPLACE_SESSION_DIR"] = str(ARTIFACTS / "sessions")''', "team state isolation")
                data = short_checkpoint_imports(text).encode("utf-8")
            result[f"products/{topic}/{relative.as_posix()}"] = data
    return result


def render(root: Path = ROOT) -> dict[str, bytes]:
    canonical = root / "3-day-labs"
    outputs = product_files(root)
    helper = short_paths((canonical / "lab_helpers.py").read_text(encoding="utf-8"))
    helper = replace_once(helper, "from common import marketplace_data, foundry_env, guardrails, notebook_parts",
                          "from common import marketplace_data, foundry_env, guardrails\nimport one_day_parts as notebook_parts",
                          "helper chat-only scope")
    helper = replace_once(helper, 'path = ROOT / "shared" / relative_file',
                          'path = ROOT / "1-day-labs/products" / relative_file',
                          "one-day helper")
    helper = replace_once(helper, 'producer = notebook_parts.lab_label(lab, "a" if name == "knowledge.json" or local_handoff else "b")',
                          'producer = "Lab 4 local phase" if lab == "lab2" and local_handoff else '
                          'notebook_parts.lab_label(lab, "a" if name == "knowledge.json" else "b")',
                          "one-day recovery")
    outputs["lab_helpers.py"] = helper.encode("utf-8")
    outputs["deployment.py"] = (canonical / "deployment.py").read_bytes()
    parts = (root / "common/notebook_parts.py").read_text(encoding="utf-8")
    parts = replace_once(parts, '    "embedding_deployment": "EMBEDDING_MODEL_DEPLOYMENT_NAME",\n', '', "chat-only checkpoint scope")
    parts = replace_once(parts, '"lab1": {"a": 1, "b": 2}', '"lab1": {"a": 1, "b": 1}', "combined setup recovery")
    outputs["one_day_parts.py"] = parts.encode("utf-8")
    for number in SELECTED:
        name, text = adapt_source(canonical, number)
        notebook = build_notebook(text, seed=Path(name).stem)
        problems = validate_step_ids(notebook, str(number)) + validate_cell_descriptions(notebook)
        if problems:
            raise ValueError(f"One-day Lab {number}: {'; '.join(problems)}")
        folder = f"lab{number:02d}"
        outputs[f"{folder}/{name}"] = text.encode("utf-8")
        outputs[f"{folder}/{folder}_walkthrough.ipynb"] = (
            json.dumps(notebook, indent=1, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        prerequisites = {1: "Administrator-approved account, chat quota and permissions.", 4: "Lab 1 verified chat-only setup; local acceptance is included here.", 7: "Lab 4's accepted deployed Responses checkpoint; no Lab 6 requirement."}
        title = {1: "Project, identity and chat inference", 4: "Build, test, deploy, and invoke", 7: "Build and host a multi-agent team"}
        guide = (
            f"# Lab {number}: {title[number]}\n\n"
            f"## Prerequisites\n\n{prerequisites[number]}\n\n"
            f"Open [{folder}_walkthrough.ipynb]({folder}_walkthrough.ipynb) in a fresh "
            "Python 3.14 dev-container kernel. Run the described cells in order.\n"
            "The notebook contains the actual inputs, YOUR TURN edits, and acceptance gates.\n\n"
            "## One-day scope and continuity\n\n"
            + ("Local tool/policy exercises and their genuine acceptance are folded into this lab "
               "before deployment. No separate Lab 3 is needed. Edit only the isolated "
               "`../products/hosted-agent-basics/hosted/main.py`, never the three-day product.\n"
               if number == 4 else (
                   "Inspect the scaffolded MAF graph, watch S1-S3 route to specialists and pause for "
                   "review, add a tool-free structured classifier, and prove the ambiguous card issue "
                   "routes to accounts. Then explicitly approve a mixed-case packet and deploy the "
                   "same edited workflow in Foundry. Review and explicitly approve its hosted packet.\n\n"
                   "MAF provides fan-out/fan-in, structured merge and the human request boundary; "
                   "Foundry provides the versioned hosted Responses endpoint. Specialists are "
                   "code-defined inside one container, not Prompt Agents. Synthetic local knowledge "
                   "replaces Search. Compliance review remains in the graph; forced unsafe drafts, "
                   "restart recovery, external history, delegation and production authorization are "
                       "outside this short capstone. If you stop before the local decision cell, "
                       "run `team_server.stop()` before leaving the notebook.\n"
                   if number == 7 else "This notebook is derived from the canonical lab with one-day paths and navigation.\n"))
            + "\nArtifacts live in `../artifacts/`; use a distinct attendee suffix for a separate workshop run. "
            "Configuration remains in the repository-root `.env`, so tracks are not simultaneous environments.\n\n"
            "## Checkpoint\n\n"
            + {1: "`artifacts/lab1/part_a.json` is the internal project handoff within this lab; "
                  "`part_b.json` and `project.json` pass verified chat-only configuration to Lab 4. "
                  "No embedding model is deployed or verified.",
               4: "`artifacts/lab2/part_a.json` records real local acceptance inside Lab 4; "
                  "`part_b.json` records the actual deployed invocation for capstone Lab 7.",
               7: "`artifacts/lab4/part_a.json` is explicitly marked `one-day-team`; it records "
                  "local classifier/approval and actual fixed-version hosted approval. It is not the "
                  "three-day Lab 7/8 recovery contract. No downstream lab consumes this capstone."}[number]
            + "\n\n## Recovery and synchronization\n\n"
            "Rerun the producing notebook's failed gates; do not invent checkpoints or replay unrelated provisioning. "
            "Only notebook-owned processes are stopped. Deployment/model calls incur charges; local and deployed "
            "evidence are distinct. Use reviewed attendee-scoped cleanup.\n\n"
            "This guide, notebook, source, and starting product are generated. Edit canonical material "
            "or the explicit adapter in `tools/sync_one_day_labs.py`; run sync before delivery, "
            "never over a learner's in-progress exercises.\n\n"
            f"[Canonical detailed guide](../../3-day-labs/{folder}/README.md) "
            "describes the full workshop; its additional prerequisites and next labs are not "
            "one-day requirements. For this adapted capstone, follow this guide and notebook.\n"
        )
        outputs[f"{folder}/README.md"] = guide.encode("utf-8")
    outputs["README.md"] = ONE_DAY_GUIDE.encode("utf-8")
    outputs["artifacts/README.md"] = (
        "# One-day runtime artifacts\n\n"
        "Ignored evidence belongs only to this track. Lab 4 produces both lab2 local "
        "and deployed handoffs; no separate Lab 3 notebook is required. Never copy "
        "three-day checkpoints here. Do not commit generated runtime evidence.\n"
    ).encode("utf-8")
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(outputs.items())}
    inputs = {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in [source_for(canonical, number) for number in (*SELECTED, 3)]}
    inputs["tools/one_day_team_finish.py"] = hashlib.sha256(
        Path(__file__).with_name("one_day_team_finish.py").read_bytes()).hexdigest()
    inputs["tools/one_day_setup_finish.py"] = hashlib.sha256(
        Path(__file__).with_name("one_day_setup_finish.py").read_bytes()).hexdigest()
    outputs["sync-manifest.json"] = (json.dumps({
        "schema_version": 1, "selected_labs": list(SELECTED), "inputs": inputs, "outputs": hashes,
    }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return outputs


ONE_DAY_GUIDE = """# One-day hosted-agent workshop

The short route keeps the original lab numbers: **1 -> 4 -> 7**.
Lab 1 combines approved identity/project setup with chat-model deployment and
verified inference. No embedding model, standalone Lab 2 or RAG setup is required.
Lab 4 includes the real local tool/policy build-and-test phase needed before
deployment; a separate Lab 3 notebook is not required. The fourth lab is
**Lab 7: Build and host a multi-agent team**, the one-day capstone. It follows
Lab 4 directly, uses synthetic local knowledge, and needs no Search or Lab 6.
MAF orchestrates code-defined specialists inside one service; Foundry hosts
and versions that service behind the Responses endpoint. No Prompt Agents.

```text
Administrator prerequisites and dev container
`-- Lab 01: Project, identity and chat inference
    `-- Lab 04: Local acceptance, deploy and invoke hosted Responses
        `-- Lab 07: Build and host a multi-agent team [capstone]
            |-- Parallel specialists -> merge -> compliance review
            |-- Change routing and explicitly approve the result
            `-- Deploy and invoke the same team in Foundry
```

Read [setup](../SETUP.md) for approved account, model quota, hosted enablement,
network and permissions. No Search, Blob, telemetry or Prompt Agent setup is
required for this route. Use Python 3.14 in the repository dev container.
Open each selected walkthrough in a fresh kernel, read its guide, and run its
cells in order. The capstone includes explicit paid deployment and human
decisions, not auto-approval. Actual timing requires rehearsal, not a promise of
one-day fit. Full restart recovery, external history, evaluations and delegation
are intentionally left to the three-day workshop.

| Order | Notebook | Main outcome |
|---|---|---|
| 1 | [Lab 1](lab01/lab01_walkthrough.ipynb) | Approved project and verified chat inference |
| 2 | [Lab 4](lab04/lab04_walkthrough.ipynb) | Tested tools/policy and actual deployed invocation |
| 3 | [Lab 7](lab07/lab07_walkthrough.ipynb) | Your changed multi-agent workflow, reviewed and hosted in Foundry |

## Isolation

Artifacts and editable product copies belong to `1-day-labs`, not `3-day-labs`.
Never edit the three-day notebooks/products for a short-track exercise.
The root `.env`, model quota and port 8088 are shared: tracks must not run
concurrently in one workspace. Use a distinct attendee suffix and review Azure
scope before a separate run. Fresh kernels prevent helper-module caching across tracks.
Do not copy three-day acceptance artifacts into the short track.

## Author synchronization

Canonical curriculum lives in `../3-day-labs`; shared product source lives in
`../shared`. This directory is generated by the versioned explicit adapter.
The sync reads source material only, never credentials, executed outputs, runtime
artifacts, caches or prepared package copies. Lab 4 composes canonical Labs 3 and
4 without weakening their acceptance gates.

From the repository root, in the author environment:

```bash
python build-and-operate-foundry-agents/tools/sync_one_day_labs.py
python build-and-operate-foundry-agents/tools/sync_one_day_labs.py --check
```

Default sync refuses to overwrite modified generated files, including learner
product edits. Archive those edits before deliberately using `--overwrite`.
Check mode is read-only and fails on upstream drift or local changes.
Never sync during delivery. Sync never writes the canonical three-day track.
To change short-only teaching, edit the adapter, not a generated notebook.
"""


def sync(root: Path = ROOT, *, check: bool = False, overwrite: bool = False) -> None:
    target = root / "1-day-labs"
    if target.is_symlink():
        raise ValueError("The one-day target must not be a symlink.")
    outputs = render(root)
    manifest_path = target / "sync-manifest.json"
    previous = {}
    if manifest_path.exists():
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
        if record.get("schema_version") != 1 or not isinstance(record.get("outputs"), dict):
            raise ValueError("Invalid one-day sync manifest; restore it before syncing.")
        previous = record["outputs"]
    stale = [name for name, data in outputs.items()
             if not (target / name).is_file() or (target / name).read_bytes() != data]
    retired = set(previous) - set(outputs)
    for name in set(previous) | set(outputs):
        if Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
            raise ValueError(f"Invalid generated manifest path: {name}")
    if check:
        if stale or retired:
            raise ValueError(f"One-day sync drift: {', '.join(sorted(set(stale) | retired))}. Run author sync.")
        return
    for name in set(outputs) | retired:
        path = target / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
            raise ValueError(f"Refusing a symlink in the generated path: {path}")
        if not path.exists() or overwrite or name == "sync-manifest.json":
            continue
        expected = previous.get(name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected != actual and path.read_bytes() != outputs.get(name):
            raise ValueError(f"Local edits in {path}; archive them before using --overwrite.")
    for name in retired:
        (target / name).unlink(missing_ok=True)
    retired_directories = {
        parent for name in retired for parent in (target / name).parents
        if parent != target and parent.is_relative_to(target)
    }
    for directory in sorted(retired_directories, key=lambda path: len(path.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    for name, data in outputs.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Fail on drift without writing.")
    group.add_argument("--overwrite", action="store_true", help="Replace locally edited generated material.")
    args = parser.parse_args()
    try:
        sync(check=args.check, overwrite=args.overwrite)
    except (OSError, ValueError) as exc:
        print(f"One-day sync failed: {exc}", file=sys.stderr)
        return 1
    print("One-day source synchronization verified." if args.check else "Generated one-day chat-only setup 1, hosted agent 4 and MAF team 7.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
