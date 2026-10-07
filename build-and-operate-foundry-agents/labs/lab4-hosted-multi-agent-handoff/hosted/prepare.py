"""Vendor the shared code into hosted/ before azd packages this folder (Lab 4).

The container only gets the folder that holds main.py, so common/ and data/ are copied here. The paths are
chosen so the copied code's own path arithmetic keeps working without edits:
    common/marketplace_data.py resolves data/ as Path(__file__).parents[1] / "data"  ->  hosted/data

    python prepare.py            copy (idempotent; run it again after editing common/ or data/)
    python prepare.py --clean    remove the copies again

The vendored copies are build output that azd packages with the rest of the folder. Re-run prepare.py before
every azd up; do not add a .gitignore inside hosted/ that could hide them from the package step.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                                   # build-and-operate-foundry-agents/
SOURCES = {"common": ROOT / "common", "data": ROOT / "data"}   # target (relative to hosted/) -> source
IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".ipynb_checkpoints",
    ".azure",
    ".venv",
    "venv",
    ".*_selftest",
)


IGNORED_PARTS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ipynb_checkpoints",
    ".azure", ".venv", "venv",
}


def manifest(folder: Path, *, source: bool = False) -> dict[str, str]:
    """Relative file paths and SHA-256 hashes for an exact vendoring check."""
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
        and (
            not source
            or (
                not any(part in IGNORED_PARTS or (part.startswith(".") and part.endswith("_selftest"))
                        for part in path.relative_to(folder).parts)
                and path.suffix not in {".pyc", ".pyo"}
            )
        )
    }


def vendor(extra: dict[str, Path] | None = None) -> dict[str, int]:
    """Copy every source into hosted/. Returns {target: file_count}."""
    counts: dict[str, int] = {}
    for name, source in {**SOURCES, **(extra or {})}.items():
        if not source.is_dir():
            raise SystemExit(f"[hosted] missing {source}; run from a full checkout of build-and-operate-foundry-agents")
        target = HERE / name
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, ignore=IGNORE)
        source_manifest = manifest(source, source=True)
        target_manifest = manifest(target)
        if source_manifest != target_manifest:
            missing = sorted(set(source_manifest) - set(target_manifest))
            extra_files = sorted(set(target_manifest) - set(source_manifest))
            changed = sorted(path for path in source_manifest.keys() & target_manifest.keys()
                             if source_manifest[path] != target_manifest[path])
            raise RuntimeError(
                f"[hosted] vendoring verification failed for {name}/ "
                f"(missing={missing[:3]}, extra={extra_files[:3]}, changed={changed[:3]})"
            )
        counts[name] = len(target_manifest)
        print(f"[hosted] vendored {name}/ ({counts[name]} files)")
    (HERE / ".vendored").write_text("created by prepare.py; safe to delete with --clean\n", encoding="utf-8")
    return counts


def clean(names: tuple[str, ...] = ("common", "data")) -> None:
    for name in names:
        target = HERE / name
        if target.exists():
            shutil.rmtree(target)
            print(f"[hosted] removed {name}/")
    marker = HERE / ".vendored"
    if marker.exists():
        marker.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    clean() if args.clean else vendor()
