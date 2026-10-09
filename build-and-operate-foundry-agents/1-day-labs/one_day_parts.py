"""Durable, scope-bound handoffs between numbered learner labs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import parse_qs, urlparse

SCOPE_KEYS = {
    "project_resource_id": "PROJECT_RESOURCE_ID",
    "project_endpoint": "FOUNDRY_PROJECT_ENDPOINT",
    "resource_suffix": "MARKETPLACE_RESOURCE_SUFFIX",
    "chat_deployment": "AZURE_AI_MODEL_DEPLOYMENT_NAME",
}
SECRET_KEYS = {"access_token", "refresh_token", "id_token", "password", "secret",
               "api_key", "account_key", "azure_openai_api_key", "azure_ai_search_api_key"}
LAB_NUMBERS = {
    "lab1": {"a": 1, "b": 1},
    "lab2": {"a": 3, "b": 4},
    "lab3": {"a": 5, "b": 6},
    "lab4": {"a": 7, "b": 8},
    "lab5": {"a": 9, "b": 10},
    "stretch6": {"a": 11},
    "hosted_delegation": {"a": 12},
    "stretch7": {"a": 13, "b": 14},
}


def lab_label(lab: str, part: str) -> str:
    """Translate stable artifact namespaces to the learner's sequential lab number."""
    if lab == "stretch6" and part == "b":
        return "Lab 12 (new hosted_delegation/part_a.json; old prompt-backed evidence is obsolete)"
    return f"Lab {LAB_NUMBERS[lab][part]}"


def scope(env: dict[str, str]) -> dict[str, str]:
    """Select only the verified project/model configuration used by a notebook."""
    context = {name: env.get(key, "") for name, key in SCOPE_KEYS.items()}
    _validate_context(context)
    return context


def _validate_context(context: dict[str, str]) -> None:
    if not context or any(not isinstance(value, str) or not value.strip()
                          or value.strip().startswith("<") for value in context.values()):
        raise ValueError("A notebook checkpoint requires explicit, populated Azure context.")
    _validate_state(context)


def _validate_state(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                raise ValueError("Credentials must not be saved in notebook checkpoints.")
            _validate_state(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_state(item)
    elif isinstance(value, str):
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and (
            parsed.username or parsed.password or "sig" in parse_qs(parsed.query)
        ):
            raise ValueError("Credential-bearing URLs must not be saved in notebook checkpoints.")
        if "AccountKey=" in value or "SharedAccessSignature=" in value:
            raise ValueError("Storage credentials must not be saved in notebook checkpoints.")


def _artifact_root(path: Path, lab: str, part: str) -> Path:
    if lab == "stretch6" and part == "b":
        raise ValueError("Lab 12 now requires hosted_delegation/part_a.json; rerun Lab 12, not Lab 11.")
    if lab not in LAB_NUMBERS or part not in LAB_NUMBERS[lab] \
            or path.name != f"part_{part}.json" or path.parent.name != lab:
        raise ValueError("Use the lab's artifacts directory and part_a.json or part_b.json.")
    root = path.parent.parent.resolve()
    if root.name != "artifacts" or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Notebook checkpoints must remain in the workshop artifacts directory.")
    return root


def _evidence_file(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.name.startswith(".env"):
        raise ValueError("Checkpoint evidence must be a file inside workshop artifacts, never configuration.")
    if resolved.name in {"part_a.json", "part_b.json"}:
        raise ValueError("Use outcome artifacts as evidence, not a mutable part checkpoint.")
    return resolved


def write_checkpoint(path: Path, *, lab: str, part: str, context: dict[str, str],
                     evidence: list[Path] | tuple[Path, ...] = (),
                     state: dict | None = None) -> dict:
    """Publish a successful part's selected state and fingerprints of its evidence."""
    path = Path(path)
    root = _artifact_root(path, lab, part)
    _validate_context(context)
    _validate_state(state or {})
    rows = []
    for item in evidence:
        source = _evidence_file(root, Path(item))
        rows.append({"path": source.relative_to(root).as_posix(),
                     "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    record = {"schema_version": 1, "lab": lab, "part": part,
              "context": context, "evidence": rows, "state": state or {}}
    text = json.dumps(record, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".checkpoint-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(text)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return record


def read_checkpoint(path: Path, *, lab: str, part: str, context: dict[str, str]) -> dict:
    """Reject missing, differently scoped, or changed evidence before the next part runs."""
    path = Path(path)
    if lab == "stretch6" and part == "b":
        raise RuntimeError("Old prompt-backed Lab 12 checkpoint is obsolete; rerun Lab 12 to publish hosted_delegation/part_a.json.")
    root = _artifact_root(path, lab, part)
    _validate_context(context)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Run {lab_label(lab, part)} to publish a valid checkpoint: {path}") from exc
    if not isinstance(record, dict) or record.get("schema_version") != 1 \
            or record.get("lab") != lab or record.get("part") != part \
            or record.get("context") != context:
        raise RuntimeError("Notebook checkpoint does not match this part and current project/model context.")
    if not isinstance(record.get("state"), dict) or not isinstance(record.get("evidence"), list):
        raise RuntimeError("Notebook checkpoint has invalid state or evidence.")
    _validate_state(record)
    for row in record["evidence"]:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise RuntimeError("Notebook checkpoint has invalid evidence.")
        try:
            source = _evidence_file(root, root / row["path"])
        except ValueError as exc:
            raise RuntimeError("Checkpoint evidence is missing or outside workshop artifacts.") from exc
        if hashlib.sha256(source.read_bytes()).hexdigest() != row.get("sha256"):
            raise RuntimeError(f"Checkpoint evidence changed; rerun {lab_label(lab, part)}: {source.name}")
    return record
