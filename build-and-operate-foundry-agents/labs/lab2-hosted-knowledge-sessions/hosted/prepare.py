"""Vendor the shared code into hosted/ before azd packages this folder (Lab 2).

Runs on: the learner workstation. azd ships only the folder that holds main.py, so common/ and data/ are
copied here. Paths are chosen so the copied code's own path arithmetic keeps working without edits:
  common/marketplace_data.py resolves data/ as Path(__file__).parents[1] / "data"   -> hosted/data
  main.py inserts hosted/ into sys.path last, so hosted/common wins over the checkout's common/ in the container.

    python prepare.py            copy (idempotent)
    python prepare.py --clean    remove the copies again
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                          # build-and-operate-foundry-agents/
SOURCES = {"common": ROOT / "common", "data": ROOT / "data"}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".*_selftest")


def vendor(extra: dict[str, Path] | None = None) -> dict[str, int]:
    """Copy each source into hosted/. Returns {target: file_count}."""
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
