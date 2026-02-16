#!/usr/bin/env python3
"""
Run Agent 2 (Task Allocator) on tasks + developers.

Usage:
  python scripts/run_agent2.py                          → prompt for paths
  python scripts/run_agent2.py agent1_output.json      → use Agent 1 JSON (user stories → tasks)
  python scripts/run_agent2.py --tasks tasks.json --devs developers.json

Tasks JSON: list of {"id", "title", "complexity", "required_skills"}.
Developers JSON: list of {"id", "name", "skills", "capacity"}.
If omitted, uses default developers for demo.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()
load_dotenv(PROJECT_ROOT / ".env")


def main() -> int:
    import argparse
    from src.agents.agent2 import allocate_tasks, user_stories_to_tasks
    from src.agents.agent2.models import Developer, Task

    parser = argparse.ArgumentParser(description="Run Agent 2: assign tasks to developers")
    parser.add_argument(
        "agent1_json",
        nargs="?",
        type=Path,
        default=None,
        help="Path to Agent 1 output JSON (functional_requirements → tasks)",
    )
    parser.add_argument(
        "--devs", "--developers",
        type=Path,
        default=None,
        help="Path to developers JSON (default: use built-in demo developers)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output JSON file (default: out/agent2_allocations.json)",
    )
    args = parser.parse_args()

    # Resolve input path (prompt if needed)
    input_path = args.agent1_json
    if not input_path or not str(input_path).strip():
        print("Agent 1 output JSON path (or Enter to use demo tasks): ", end="", flush=True)
        line = (sys.stdin.readline() or "").strip()
        if line:
            input_path = Path(line).expanduser().resolve()
        else:
            input_path = None

    # Load or create tasks
    if input_path is not None:
        input_path = Path(input_path).expanduser().resolve()
    if input_path is not None and input_path.exists():
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if "functional_requirements" in data:
            tasks = user_stories_to_tasks(data["functional_requirements"])
        elif "tasks" in data:
            tasks = [Task.model_validate(t) for t in data["tasks"]]
        else:
            tasks = [Task.model_validate(t) for t in data] if isinstance(data, list) else []
    else:
        # Demo tasks
        tasks = [
            Task(id="US-01", title="Implement login API", complexity="High", required_skills=["API", "Security"]),
            Task(id="US-02", title="Add user profile page", complexity="Medium", required_skills=["Frontend"]),
            Task(id="US-03", title="Fix PDF export", complexity="Low", required_skills=["Python"]),
        ]

    # Load or create developers
    if args.devs and args.devs.exists():
        dev_data = json.loads(args.devs.read_text(encoding="utf-8"))
        developers = [Developer.model_validate(d) for d in dev_data]
    else:
        developers = [
            Developer(id="dev-1", name="Alice", skills=["API", "Security", "Python"], capacity=3),
            Developer(id="dev-2", name="Bob", skills=["Frontend", "API"], capacity=3),
            Developer(id="dev-3", name="Carol", skills=["Python", "Database"], capacity=2),
        ]

    result = allocate_tasks(tasks, developers)
    out_json = result.model_dump_json(indent=2)
    print(out_json)

    out_path = args.output or PROJECT_ROOT / "out" / "agent2_allocations.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\nSaved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
