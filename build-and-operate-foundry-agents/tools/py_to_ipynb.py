"""py_to_ipynb: stdlib-only converter from a `# %%` cell script to a Jupyter notebook.

Usage:
    python tools/py_to_ipynb.py labs/lab05/lab05_knowledge_retrieval.py --name lab05_walkthrough
    python tools/py_to_ipynb.py <script.py> [-o <notebook.ipynb>] [--name lab06_walkthrough]
    python tools/py_to_ipynb.py --check <notebook.ipynb>      # validate an existing notebook

Rules:
* `# %%` starts a code cell. Anything after the marker on the same line is a cell title
  and becomes a comment on the first line of the cell (unless it is a tag such as [markdown]).
* `# %% [markdown]` starts a Markdown cell. Lines in the block are Markdown; a leading `# ` on each
  line is stripped so the block reads well in the .py file too. Triple-quoted blocks inside a
  Markdown cell are also accepted (the quotes are dropped).
* `# %% [raw]` starts a non-executable raw cell.
* `# %% [script-only]` keeps internal CLI helpers in the authoring source but omits them from notebooks.
* A module docstring (before the first marker, or at the top of the first code cell after a leading Markdown
  cell) becomes its own Markdown cell.
* Code before the first marker (imports, sys.path setup) becomes the first code cell.
* Empty cells are skipped.
* Notebook safety (disable with --keep-script-semantics): `Path(__file__)` falls back to a file in the
  notebook's folder so `parents[N]` arithmetic keeps working, and CLI-only cells are omitted.

Output is nbformat 4.5 JSON that `python -m json.tool` and Jupyter both accept. No nbformat dependency.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

CELL_RE = re.compile(r"^\s*#\s*%%(.*)$")
MARKDOWN_TAG_RE = re.compile(r"\[\s*markdown\s*\]", re.IGNORECASE)
RAW_TAG_RE = re.compile(r"\[\s*raw\s*\]", re.IGNORECASE)
SCRIPT_ONLY_TAG_RE = re.compile(r"\[\s*script-only\s*\]", re.IGNORECASE)
STEP_RE = re.compile(r"^# Step (?P<id>S?\d+\.\d+) - .+")


def _cell_id(seed: str, index: int) -> str:
    return hashlib.sha1(f"{seed}:{index}".encode("utf-8")).hexdigest()[:8]


def _split_docstring(text: str) -> tuple[str | None, str]:
    """Return (leading docstring, remaining source) using the AST so quoting styles do not matter.

    Works on a whole script or on one cell's text: only a bare string literal that is the first statement
    counts, so docstrings inside def/class bodies are left alone.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None, text
    if not tree.body:
        return None, text
    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
            and isinstance(first.value.value, str):
        lines = text.splitlines(keepends=True)
        end = first.end_lineno or first.lineno
        doc = first.value.value
        rest = "".join(lines[end:])
        return doc, rest
    return None, text


FILE_FALLBACK = 'Path(globals().get("__file__", Path.cwd() / "_walkthrough_.py"))'
MAIN_GUARD = 'if __name__ == "__main__" and "__file__" in globals():'


def _notebookify(lines: list[str]) -> list[str]:
    """Make a code cell safe to run in a kernel without changing what the .py does."""
    out = []
    for line in lines:
        line = line.replace("Path(__file__)", FILE_FALLBACK)
        if line.strip() == 'if __name__ == "__main__":':
            line = line.replace('if __name__ == "__main__":', MAIN_GUARD)
        out.append(line)
    return out


TRIPLE_RE = re.compile(r'^\s*[rRuU]?("""|\'\'\')')


def _clean_markdown(lines: list[str]) -> list[str]:
    """Comment prefixes are stripped; a triple-quoted block inside the cell becomes a fenced text block so the
    aligned Goal / Inputs / Outputs layout of a module docstring survives Markdown rendering."""
    out: list[str] = []
    in_block = False
    for line in lines:
        stripped = line.rstrip("\n")
        if not in_block and TRIPLE_RE.match(stripped):
            in_block = True
            out.append("```text")
            stripped = TRIPLE_RE.sub("", stripped, count=1)
            if stripped.rstrip().endswith(('"""', "'''")):          # one-line docstring
                stripped = stripped.rstrip()[:-3]
                out.extend([stripped, "```"])
                in_block = False
                continue
        elif in_block and stripped.rstrip().endswith(('"""', "'''")):
            body = stripped.rstrip()[:-3]
            if body.strip():
                out.append(body)
            out.append("```")
            in_block = False
            continue
        if not in_block:
            if stripped.startswith("# "):
                stripped = stripped[2:]
            elif stripped.strip() == "#":
                stripped = ""
        out.append(stripped)
    if in_block:
        out.append("```")
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _clean_code(lines: list[str]) -> list[str]:
    out = [line.rstrip("\n") for line in lines]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _clean_raw(lines: list[str]) -> list[str]:
    title = lines[0].rstrip("\n") if lines and lines[0].startswith("# Step ") else None
    cleaned = _clean_markdown(lines)
    if title and cleaned:
        cleaned[0] = title
    return cleaned


def _source_list(lines: list[str]) -> list[str]:
    """nbformat wants a list of lines, each ending with \\n except the last."""
    if not lines:
        return []
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def split_cells(text: str, notebook_safe: bool = True) -> list[tuple[str, list[str]]]:
    """Split script text into [(cell_type, lines)] in file order."""
    cells: list[tuple[str, list[str]]] = []
    current_type = "code"
    current: list[str] = []
    for raw in text.splitlines(keepends=True):
        match = CELL_RE.match(raw)
        if match:
            cells.append((current_type, current))
            tag = match.group(1).strip()
            if SCRIPT_ONLY_TAG_RE.search(tag):
                current_type = "script-only"
                current = []
            elif RAW_TAG_RE.search(tag):
                current_type = "raw"
                title = RAW_TAG_RE.sub("", tag).strip()
                current = [f"# {title}\n"] if title else []
            elif MARKDOWN_TAG_RE.search(tag):
                current_type = "markdown"
                current = []
            else:
                current_type = "code"
                title = re.sub(r"\[[^\]]*\]", "", tag).strip()
                current = [f"# {title}\n"] if title else []
            continue
        current.append(raw)
    cells.append((current_type, current))

    result: list[tuple[str, list[str]]] = []
    for cell_type, lines in cells:
        if cell_type == "script-only":
            if notebook_safe:
                continue
            cell_type = "code"
        if cell_type == "code":
            docstring, rest = _split_docstring("".join(lines))
            if docstring:
                result.append(("markdown", _clean_markdown(docstring.strip("\n").splitlines())))
                lines = rest.splitlines(keepends=True)
            cleaned = _clean_code(lines)
            if notebook_safe:
                cleaned = _notebookify(cleaned)
        elif cell_type == "raw":
            cleaned = _clean_raw(lines)
        else:
            cleaned = _clean_markdown(lines)
        if cleaned:
            result.append((cell_type, cleaned))
    return result


def build_notebook(text: str, seed: str = "notebook", notebook_safe: bool = True) -> dict:
    cells = []
    for index, (cell_type, lines) in enumerate(split_cells(text, notebook_safe)):
        cell = {
            "id": _cell_id(seed, index),
            "cell_type": cell_type,
            "metadata": {},
            "source": _source_list(lines),
        }
        if cell_type == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def validate_notebook(nb: dict) -> list[str]:
    """Structural checks that mirror what nbformat.validate would reject."""
    problems: list[str] = []
    if nb.get("nbformat") != 4:
        problems.append("nbformat must be 4")
    if not isinstance(nb.get("cells"), list):
        problems.append("cells must be a list")
        return problems
    seen: set[str] = set()
    for i, cell in enumerate(nb["cells"]):
        ct = cell.get("cell_type")
        if ct not in ("code", "markdown", "raw"):
            problems.append(f"cell {i}: bad cell_type {ct!r}")
        if not isinstance(cell.get("source"), list):
            problems.append(f"cell {i}: source must be a list of lines")
        if not isinstance(cell.get("metadata"), dict):
            problems.append(f"cell {i}: metadata must be a dict")
        cid = cell.get("id")
        if not cid or cid in seen:
            problems.append(f"cell {i}: missing or duplicate id")
        seen.add(cid)
        if ct == "code":
            if "outputs" not in cell or cell.get("execution_count", "missing") == "missing":
                problems.append(f"cell {i}: code cell needs outputs and execution_count")
    return problems


def validate_step_ids(nb: dict, expected_prefix: str) -> list[str]:
    """Require consecutive, visible step identifiers on executable and raw cells."""
    problems: list[str] = []
    actual: list[str] = []
    for index, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") not in {"code", "raw"}:
            continue
        source = cell.get("source") or []
        first_line = source[0].rstrip("\n") if source else ""
        match = STEP_RE.fullmatch(first_line)
        if not match:
            problems.append(f"cell {index}: code/raw cell must start with '# Step {expected_prefix}.N - ...'")
            continue
        actual.append(match.group("id"))
    expected = [f"{expected_prefix}.{index}" for index in range(1, len(actual) + 1)]
    if actual != expected:
        problems.append(f"step ids must be consecutive: expected {expected}, got {actual}")
    return problems


def validate_cell_descriptions(nb: dict) -> list[str]:
    """Require a visible explanation immediately before every executable cell."""
    problems = []
    for index, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        previous = nb["cells"][index - 1] if index else {}
        if previous.get("cell_type") != "markdown" or not "".join(previous.get("source", [])).strip():
            problems.append(f"cell {index}: code cell needs a preceding Markdown description")
    return problems


def convert(script: Path, output: Path | None = None, name: str | None = None, notebook_safe: bool = True) -> Path:
    text = script.read_text(encoding="utf-8")
    nb = build_notebook(text, seed=script.stem, notebook_safe=notebook_safe)
    problems = validate_notebook(nb)
    if problems:
        raise SystemExit("[py_to_ipynb] invalid notebook: " + "; ".join(problems))
    if output is None:
        stem = name or script.stem
        output = script.with_name(f"{stem}.ipynb")
    output.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("script", type=Path, help="a # %%%% cell script, or a .ipynb when --check is used")
    parser.add_argument("-o", "--output", type=Path, default=None, help="notebook path (default: next to the script)")
    parser.add_argument("--name", default=None, help="notebook stem, for example lab05_walkthrough")
    parser.add_argument("--check", action="store_true", help="validate an existing .ipynb instead of converting")
    parser.add_argument("--keep-script-semantics", action="store_true",
                        help="do not rewrite Path(__file__) or guard the __main__ block")
    args = parser.parse_args(argv)

    if args.check:
        nb = json.loads(Path(args.script).read_text(encoding="utf-8"))
        problems = validate_notebook(nb)
        if problems:
            print("[py_to_ipynb] FAIL " + "; ".join(problems))
            return 1
        print(f"[py_to_ipynb] ok {args.script} ({len(nb['cells'])} cells)")
        return 0

    out = convert(args.script, args.output, args.name, notebook_safe=not args.keep_script_semantics)
    nb = json.loads(out.read_text(encoding="utf-8"))
    code = sum(1 for c in nb["cells"] if c["cell_type"] == "code")
    md = sum(1 for c in nb["cells"] if c["cell_type"] == "markdown")
    raw = sum(1 for c in nb["cells"] if c["cell_type"] == "raw")
    print(f"[py_to_ipynb] wrote {out} ({code} code cells, {md} markdown cells, {raw} raw cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
