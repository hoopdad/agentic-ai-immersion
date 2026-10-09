"""Prepare an isolated candidate without changing the evaluated Labs 9-10 source or deployment."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORE = ROOT / "shared" / "hosted-knowledge-sessions" / "hosted"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".env*", ".azure", "message_store", "sessions", "*.log")


def vendor() -> dict[str, int]:
    counts = {}
    for name in ("common", "data"):
        shutil.rmtree(HERE / name, ignore_errors=True)
        shutil.copytree(ROOT / name, HERE / name, ignore=IGNORE)
        counts[name] = sum(item.is_file() for item in (HERE / name).rglob("*"))
    shutil.copy2(CORE / "main.py", HERE / "core_product.py")
    accepted = CORE / "common" / "accepted_concierge.py"
    if not accepted.is_file():
        raise RuntimeError("Restore the accepted Lab 6 sponsor tool and handoff policy before preparing Lab 12.")
    shutil.copy2(accepted, HERE / "common" / "accepted_concierge.py")
    shutil.copy2(HERE.parent / "delegation.py", HERE / "delegation.py")
    counts["core_product"] = 1
    return counts


def source_fingerprints() -> dict[str, str]:
    if not (CORE / "common" / "accepted_concierge.py").is_file():
        raise RuntimeError("Restore the accepted Lab 6 sponsor tool and handoff policy before preparing Lab 12.")
    paths = [CORE / "main.py", HERE / "main.py", HERE / "prepare.py", HERE / "requirements.txt",
             HERE.parent / "delegation.py", CORE / "common" / "accepted_concierge.py",
             *(ROOT / "common").glob("*.py")]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


if __name__ == "__main__":
    vendor()
