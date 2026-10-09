"""Vendor the shared code into hosted/ before azd packages this folder (Labs 5-6).

Runs on: the learner workstation. azd ships only the folder that holds main.py, so common/ and data/ are
copied here. Paths are chosen so the copied code's own path arithmetic keeps working without edits:
  common/marketplace_data.py resolves data/ as Path(__file__).parents[1] / "data"   -> hosted/data
  main.py inserts hosted/ into sys.path last, so hosted/common wins over the checkout's common/ in the container.

    python prepare.py            copy (idempotent)
    python prepare.py --clean    remove the copies again
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                          # build-and-operate-foundry-agents/
SOURCES = {"common": ROOT / "common", "data": ROOT / "data"}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".*_selftest")

def transfer_accepted_behavior(source: Path, expected_sha256: str) -> dict[str, str]:
    """Carry only Lab 3's sponsor tool and enrollment handoff policy into this product."""
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError("Lab 3 source changed; rerun Labs 3-4 acceptance before Lab 5.")
    text = raw.decode("utf-8")
    tree = ast.parse(text)
    sponsor = next((node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "get_sponsor"), None)
    instructions = next((ast.literal_eval(node.value) for node in tree.body
                         if isinstance(node, ast.Assign) and any(
                             isinstance(target, ast.Name) and target.id == "ROLE_INSTRUCTIONS"
                             for target in node.targets)), "")
    lines = instructions.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith("3.")), None)
    end = next((index for index, line in enumerate(lines)
                if start is not None and index > start and line[:1].isdigit()), len(lines))
    if sponsor is None or start is None:
        raise RuntimeError("Lab 3 sponsor tool or rule 3 is missing; complete its exercises.")
    policy = "\n".join(lines[start:end]).strip()
    aliases = [
        ast.unparse(node) for node in tree.body
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PID" for target in node.targets)
        and any(isinstance(name, ast.Name) and name.id == "PID" for name in ast.walk(sponsor))
    ]
    product = (
        "from typing import Annotated\nfrom pydantic import Field\n"
        "from agent_framework import tool\nfrom common import marketplace_data\n\n"
        + "\n".join(aliases) + "\n" + ast.unparse(sponsor) + f"\n\nHANDOFF_POLICY = {policy!r}\n"
    )
    target = HERE / "common" / "accepted_concierge.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(product, encoding="utf-8")
    return {"source_sha256": digest, "transfer_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "handoff_policy": policy}


def vendor(extra: dict[str, Path] | None = None) -> dict[str, int]:
    """Copy each source into hosted/. Returns {target: file_count}."""
    retained = HERE / "common" / "accepted_concierge.py"
    accepted = retained.read_bytes() if retained.is_file() else None
    counts: dict[str, int] = {}
    for name, source in {**SOURCES, **(extra or {})}.items():
        if not source.exists():
            raise SystemExit(f"[hosted] missing {source}; run from a full checkout of build-and-operate-foundry-agents")
        target = HERE / name
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, ignore=IGNORE, dirs_exist_ok=True)
        counts[name] = sum(1 for item in target.rglob("*") if item.is_file())
        print(f"[hosted] vendored {name}/ ({counts[name]} files)")
    if accepted is not None:
        retained.write_bytes(accepted)
    (HERE / ".vendored").write_text("created by prepare.py; safe to delete with --clean\n", encoding="utf-8")
    return counts


def clean(names: tuple[str, ...] = ("common", "data")) -> None:
    for name in names:
        target = HERE / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            print(f"[hosted] removed {name}/")
    marker = HERE / ".vendored"
    if marker.exists():
        marker.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    clean() if args.clean else vendor()
