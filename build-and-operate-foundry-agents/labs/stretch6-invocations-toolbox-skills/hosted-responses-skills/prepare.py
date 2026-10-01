"""Vendor and verify the self-contained Responses + Skills deployment package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LAB_DIR = HERE.parent
SOURCES = {"common": ROOT / "common", "data": ROOT / "data", "skills": LAB_DIR / "skills"}
REQUIRED_ROOT_FILES = ("main.py", "requirements.txt", ".agentignore")
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", ".azure", ".venv", "venv"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
MANIFEST = HERE / ".vendored.json"


def _included(path: Path) -> bool:
    return not any(part in IGNORED_NAMES for part in path.parts) and path.suffix not in IGNORED_SUFFIXES


def _manifest(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise SystemExit(f"[hosted-responses-skills] missing source directory: {root}")
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and _included(path.relative_to(root))
    }


def vendor() -> dict[str, int]:
    """Replace vendored inputs and record their deterministic SHA-256 manifests."""
    manifests: dict[str, dict[str, str]] = {}
    for name, source in SOURCES.items():
        source_manifest = _manifest(source)
        target = HERE / name
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".mypy_cache", ".*_selftest"),
        )
        target_manifest = _manifest(target)
        if target_manifest != source_manifest:
            raise SystemExit(f"[hosted-responses-skills] vendored {name}/ does not match its source")
        manifests[name] = source_manifest
        print(f"[hosted-responses-skills] vendored {name}/ ({len(source_manifest)} files)")
    MANIFEST.write_text(
        json.dumps({"format": 1, "sources": manifests}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    review()
    return {name: len(files) for name, files in manifests.items()}


def review() -> dict[str, int]:
    """Fail unless the package is complete, clean, and identical to workshop sources."""
    missing = [name for name in REQUIRED_ROOT_FILES if not (HERE / name).is_file()]
    if missing:
        raise SystemExit(f"[hosted-responses-skills] package is missing required files: {', '.join(missing)}")
    if not MANIFEST.is_file():
        raise SystemExit("[hosted-responses-skills] .vendored.json is missing; run python .\\prepare.py")
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = recorded.get("sources")
    if not isinstance(expected, dict):
        raise SystemExit("[hosted-responses-skills] invalid .vendored.json")
    counts: dict[str, int] = {}
    for name, source in SOURCES.items():
        source_manifest = _manifest(source)
        target_manifest = _manifest(HERE / name)
        if expected.get(name) != source_manifest or target_manifest != source_manifest:
            raise SystemExit(f"[hosted-responses-skills] {name}/ is stale; run python .\\prepare.py")
        counts[name] = len(target_manifest)
    if not counts["skills"]:
        raise SystemExit("[hosted-responses-skills] no bundled SKILL.md content was found")
    forbidden = [
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.is_file()
        and (
            any(part in {".azure", ".git", ".venv", "venv", "__pycache__"} for part in path.relative_to(HERE).parts)
            or path.name == ".env"
            or path.name.startswith(".env.")
            or path.suffix in IGNORED_SUFFIXES
        )
    ]
    if forbidden:
        raise SystemExit(f"[hosted-responses-skills] forbidden package files: {', '.join(sorted(forbidden))}")
    print(f"[hosted-responses-skills] package review PASS ({sum(counts.values())} vendored files)")
    return counts


def clean() -> None:
    for name in SOURCES:
        target = HERE / name
        if target.exists():
            shutil.rmtree(target)
            print(f"[hosted-responses-skills] removed {name}/")
    if MANIFEST.exists():
        MANIFEST.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--clean", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    clean() if args.clean else review() if args.check else vendor()
