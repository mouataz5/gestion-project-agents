#!/usr/bin/env python3
"""
Run each agent one by one for smoke testing.

Usage:
  python scripts/test_agents.py              # run Agents 2, 3, 4 (no PDF/DB)
  python scripts/test_agents.py --agent 1 --pdf path/to/spec.pdf
  python scripts/test_agents.py --agent 2   # run only Agent 2
  python scripts/test_agents.py --agent 5   # needs: docker compose -p agentdata up -d && python -m src.infrastructure.setup_postgres
  python scripts/test_agents.py --agent 6   # run Agent 6 on current dir (slow: ReAct loop)
  python scripts/test_agents.py --all       # run all (Agent 1 only if --pdf given)

Requirements: GROQ_API_KEY in .env.
Agent 5: PostgreSQL on localhost:5433 + jira_history table (see above).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT = PROJECT_ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], timeout: int = 120) -> tuple[bool, str]:
    """Run command; return (success, combined stdout+stderr)."""
    try:
        r = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ},
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def test_agent1(pdf_path: Path | None) -> tuple[bool, str]:
    if not pdf_path or not pdf_path.exists():
        return False, "Agent 1 requires a PDF. Run: python scripts/run_agent1.py path/to/spec.pdf"
    ok, out = run([sys.executable, "scripts/run_agent1.py", str(pdf_path)], timeout=90)
    return ok, out


def test_agent2(agent1_json: Path | None) -> tuple[bool, str]:
    # Demo mode if no agent1 output
    args = [sys.executable, "scripts/run_agent2.py"]
    if agent1_json and agent1_json.exists():
        args.append(str(agent1_json))
    ok, out = run(args, timeout=30)
    return ok, out


def test_agent3() -> tuple[bool, str]:
    code_file = PROJECT_ROOT / "src" / "agents" / "agent2" / "graph.py"
    if not code_file.exists():
        return False, "Test file not found"
    ok, out = run([sys.executable, "scripts/run_agent3.py", str(code_file)], timeout=90)
    return ok, out


def test_agent4() -> tuple[bool, str]:
    transcript = OUT / "sample_transcript.txt"
    if not transcript.exists():
        return False, "out/sample_transcript.txt not found"
    ok, out = run([sys.executable, "scripts/run_agent4.py", str(transcript)], timeout=60)
    return ok, out


def test_agent5() -> tuple[bool, str]:
    ok, out = run([sys.executable, "scripts/run_agent5.py"], timeout=60)
    return ok, out


def test_agent6() -> tuple[bool, str]:
    # Use src/ so it's smaller than full project
    ok, out = run(
        [sys.executable, "scripts/run_agent6.py", "src"],
        timeout=180,
    )
    return ok, out


def main() -> int:
    parser = argparse.ArgumentParser(description="Test agents one by one")
    parser.add_argument(
        "--agent",
        type=int,
        choices=[1, 2, 3, 4, 5, 6],
        default=None,
        help="Run only this agent (default: run 2,3,4 and optionally 5,6)",
    )
    parser.add_argument("--pdf", type=Path, default=None, help="PDF for Agent 1")
    parser.add_argument("--all", action="store_true", help="Run all agents (Agent 1 skipped unless --pdf)")
    args = parser.parse_args()

    if not (os.environ.get("GROQ_API_KEY") or "").strip().startswith("gsk_"):
        try:
            from dotenv import load_dotenv
            load_dotenv(PROJECT_ROOT / ".env")
        except Exception:
            pass
        if not (os.environ.get("GROQ_API_KEY") or "").strip().startswith("gsk_"):
            print("Error: GROQ_API_KEY not set in .env", file=sys.stderr)
            return 1

    agents_to_run: list[tuple[int, str, callable]] = []
    if args.agent:
        if args.agent == 1:
            agents_to_run.append((1, "Agent 1 (Project Analyzer)", lambda: test_agent1(args.pdf)))
        elif args.agent == 2:
            agents_to_run.append((2, "Agent 2 (Task Allocator)", lambda: test_agent2(OUT / "agent1_analysis.json")))
        elif args.agent == 3:
            agents_to_run.append((3, "Agent 3 (Code Reviewer)", test_agent3))
        elif args.agent == 4:
            agents_to_run.append((4, "Agent 4 (Meeting Summarizer)", test_agent4))
        elif args.agent == 5:
            agents_to_run.append((5, "Agent 5 (Risk Predictor)", test_agent5))
        else:
            agents_to_run.append((6, "Agent 6 (Documentation Writer)", test_agent6))
    else:
        # Default: 2, 3, 4 (no PDF, no DB required for 5)
        agents_to_run = [
            (2, "Agent 2 (Task Allocator)", lambda: test_agent2(OUT / "agent1_analysis.json")),
            (3, "Agent 3 (Code Reviewer)", test_agent3),
            (4, "Agent 4 (Meeting Summarizer)", test_agent4),
        ]
        if args.all:
            agents_to_run.insert(0, (1, "Agent 1 (Project Analyzer)", lambda: test_agent1(args.pdf)))
            agents_to_run.append((5, "Agent 5 (Risk Predictor)", test_agent5))
            agents_to_run.append((6, "Agent 6 (Documentation Writer)", test_agent6))

    for num, name, test_fn in agents_to_run:
        print(f"\n{'='*60}\nTesting {name}\n{'='*60}", flush=True)
        ok, out = test_fn()
        if ok:
            print("[PASS]", flush=True)
            if out.strip():
                # Show last few lines of output
                lines = out.strip().splitlines()
                for line in lines[-15:]:
                    print(line)
        else:
            print("[FAIL]", flush=True)
            print(out[:2000] or "No output", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
