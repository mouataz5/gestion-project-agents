#!/usr/bin/env python3
"""
Run Agent 3 (Code Reviewer) on a diff or code snippet.

Usage:
  python scripts/run_agent3.py path/to/code.py
  python scripts/run_agent3.py path/to/code.py --codebase src/   # RAG: index src/ and use as context

Output: prints CodeReviewResult JSON and saves to out/agent3_review.json
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
    from src.agents.agent3 import run_agent3
    from src.rag.code_ingestion import ingest_code_directory, get_code_retriever

    parser = argparse.ArgumentParser(description="Run Agent 3 (Code Reviewer)")
    parser.add_argument("file_path", nargs="?", type=Path, default=None, help="Path to code or diff file")
    parser.add_argument(
        "--codebase", "-c",
        type=Path,
        default=None,
        help="Index this directory for RAG context (e.g. src/)",
    )
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()

    code_or_diff: str
    path = args.file_path
    if path is not None and str(path).strip():
        path = Path(path).expanduser().resolve()
        if path.exists():
            code_or_diff = path.read_text(encoding="utf-8", errors="replace")
        else:
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 1
    else:
        print("Path to diff/code file (or Enter to paste; end with Ctrl+D or empty line): ", end="", flush=True)
        first = (sys.stdin.readline() or "").strip()
        if first:
            path = Path(first).expanduser().resolve()
            if path.exists():
                code_or_diff = path.read_text(encoding="utf-8", errors="replace")
            else:
                print(f"Error: File not found: {path}", file=sys.stderr)
                return 1
        else:
            lines = []
            try:
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    lines.append(line)
            except EOFError:
                pass
            code_or_diff = "".join(lines) if lines else ""
    if not code_or_diff.strip():
        print("Error: No code or diff provided.", file=sys.stderr)
        return 1

    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key or not key.startswith("gsk_") or len(key) < 30:
        print("Error: GROQ_API_KEY in .env is missing or invalid.", file=sys.stderr)
        return 1

    code_retriever = None
    if args.codebase is not None and args.codebase.exists() and args.codebase.is_dir():
        print("Indexing codebase for RAG...", flush=True)
        code_retriever = ingest_code_directory(args.codebase)
        print("Running Agent 3 (retrieval → reviewer → critic → merge)...", flush=True)
    else:
        if args.codebase is not None:
            print("Warning: --codebase path not found or not a directory; running without RAG.", file=sys.stderr)
        print("Running Agent 3 (reviewer → critic → merge)...", flush=True)
    if code_retriever is None:
        code_retriever = get_code_retriever()
    result = run_agent3(code_or_diff, code_retriever=code_retriever)
    if result is None:
        print("Error: Agent returned no result.", file=sys.stderr)
        return 1

    out_json = result.model_dump_json(indent=2)
    print(out_json)
    out_path = args.output or PROJECT_ROOT / "out" / "agent3_review.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\nSaved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
