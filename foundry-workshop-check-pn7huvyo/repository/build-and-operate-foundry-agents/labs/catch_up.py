"""catch_up.py: internal automation to recreate artifacts for labs 2..K.

Runs on: a configured workstation or CI runner (az login, .env filled). Lab 1 project/model setup is explicit;
this helper never provisions a Foundry account or project. It imports each lab's driver module by file name and
calls its build() (the creation work), never its demo() (the scenario runs), so it is the minimum that makes the
next lab's `require_artifact` pass.

    python catch_up.py --through 3         labs 2 and 3 (hosted basics record, knowledge base, vendored hosted/)
    python catch_up.py --through 5         + lab 4 record + lab 5 operate.json, pipeline.md and a short evaluation
    python catch_up.py --through 7         + stretch 6 prompt agents and workflow, stretch 7 invocations record
    python catch_up.py --only 5            one lab only (its inputs must already exist)

Lab folders and main files (exact names from the sequence brief):
    2  lab2-hosted-agent-basics/lab2_hosted_basics.py                 build()
    3  lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py        build(skip_connection=False)
    4  lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py     build()
    5  lab5-operate-hosted-agents/lab5_operate.py                     build() then demo(limit=6, skip judges)
    6  stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py build()
    7  stretch7-invocations-toolbox-skills/stretch7_invocations.py    build()
Each step is wrapped in try/except: a missing module, a missing role or a network error prints a friendly message
and the script continues to the next lab so you can see everything that still needs attention.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

LABS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LABS_DIR))
import lab_helpers as helpers  # noqa: E402

STEPS = {
    2: ("lab2-hosted-agent-basics/lab2_hosted_basics.py", "artifacts/lab2/hosted.json"),
    3: ("lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py", "artifacts/lab3/knowledge.json, hosted.json"),
    4: ("lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py", "artifacts/lab4/hosted.json"),
    5: ("lab5-operate-hosted-agents/lab5_operate.py", "artifacts/lab5/operate.json, pipeline.md, eval_report.md"),
    6: ("stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py", "artifacts/stretch6/agents.json"),
    7: ("stretch7-invocations-toolbox-skills/stretch7_invocations.py", "artifacts/stretch7/invocations.json"),
}


def run_step(n: int, skip_connection: bool = False) -> bool:
    relative_file, produces = STEPS[n]
    label = f"[catch_up] lab {n}"
    print(f"\n{label}: {relative_file} -> {produces}")
    try:
        module = helpers.load_lab_module(relative_file)
    except FileNotFoundError:
        print(f"{label} SKIP: {relative_file} is not in this checkout yet")
        return False
    except ImportError as exc:
        print(f"{label} SKIP: cannot import ({exc}). Install labs/requirements.txt in this environment")
        return False
    build = getattr(module, "build", None)
    if not callable(build):
        print(f"{label} SKIP: {relative_file} has no build() function")
        return False
    try:
        if n == 3:
            module.build(skip_connection=skip_connection)
        elif n == 5:
            bundle = module.build(skip_judges=True)
            module.demo(bundle, limit=6)         # six golden questions, custom evaluators only: fast and deterministic
        else:
            module.build()
        print(f"{label} done")
        return True
    except SystemExit as exc:
        print(f"{label} STOPPED: {exc}")
    except Exception as exc:                     # noqa: BLE001
        print(f"{label} FAILED: {type(exc).__name__}: {str(exc)[:300]}")
        if "--trace" in sys.argv:
            traceback.print_exc()
        if "403" in str(exc) or "401" in str(exc):
            print(f"{label} hint: RBAC. Check SETUP.md section 5; role propagation takes 5 to 15 minutes")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--through", type=int, choices=sorted(STEPS), help="recreate artifacts for labs 2..K (not project setup)")
    parser.add_argument("--only", type=int, choices=sorted(STEPS), help="run one lab's build() only")
    parser.add_argument("--skip-connection", action="store_true", help="lab 3: skip the ARM project connection PUT")
    parser.add_argument("--trace", action="store_true", help="print full tracebacks on failure")
    args = parser.parse_args()
    if args.only:
        steps = [args.only]
    elif args.through:
        steps = [n for n in sorted(STEPS) if n <= args.through]
    else:
        parser.error("pass --through K or --only K")
    results = {n: run_step(n, skip_connection=args.skip_connection) for n in steps}
    print("\n[catch_up] summary: " + ", ".join(f"lab {n}: {'ok' if ok else 'not done'}" for n, ok in results.items()))
    if not all(results.values()):
        print("[catch_up] fix the lines marked STOPPED/FAILED/SKIP above and rerun; each lab's README has a troubleshooting table")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
