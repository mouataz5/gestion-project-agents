#!/usr/bin/env python3
"""
Run Agent 6 (Documentation Writer) on a project directory.

Usage:
  python scripts/run_agent6.py path/to/project
  python scripts/run_agent6.py .   # current directory

ReAct: agent explores with list_directory and read_file, then generates README + API docs.
Output: prints DocumentationResult JSON and saves to out/agent6_docs.json
"""

from __future__ import annotations

import argparse
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
    from src.agents.agent6 import run_agent6

    parser = argparse.ArgumentParser(description="Run Agent 6 (Documentation Writer)")
    parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        type=Path,
        help="Path to project directory to document (default: current directory)",
    )
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument(
        "--lang",
        choices=["en", "fr", "es"],
        default="en",
        help="OF6.6: Output language (en/fr/es)",
    )
    args = parser.parse_args()

    path = args.project_path.expanduser().resolve()
    if not path.is_dir():
        print(f"Error: Not a directory: {path}", file=sys.stderr)
        return 1

    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key or not key.startswith("gsk_") or len(key) < 30:
        print("Error: GROQ_API_KEY in .env is missing or invalid.", file=sys.stderr)
        return 1

    print("Running Agent 6 (ReAct: explore -> generate docs)...", flush=True)
    result = run_agent6(path, language=args.lang)
    if result is None:
        print("Error: Agent returned no result.", file=sys.stderr)
        return 1

    out_json = result.model_dump_json(indent=2)
    print(out_json)
    out_path = args.output or PROJECT_ROOT / "out" / "agent6_docs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\nSaved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
