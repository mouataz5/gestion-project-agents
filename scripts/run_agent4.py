#!/usr/bin/env python3
"""
Run Agent 4 (Meeting Summarizer) on a transcript.

Usage:
  python scripts/run_agent4.py path/to/transcript.txt
  python scripts/run_agent4.py path/to/transcript.txt --rag --pdf path/to/spec.pdf   # RAG from project docs
  python scripts/run_agent4.py -   # read from stdin

RAG: use --rag to ground the summary in project context. With --pdf, ingest that PDF first (Agent 1 style).
Without --pdf, uses existing project_specs index if Agent 1 was run previously.

Output: prints MeetingSummary JSON and saves to out/agent4_summary.json
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
    from src.agents.agent4 import run_agent4

    parser = argparse.ArgumentParser(description="Run Agent 4 (Meeting Summarizer)")
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to transcript file, or '-' for stdin",
    )
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Use RAG: ground summary in project docs (ingest --pdf or use existing project_specs)",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="PDF to ingest for RAG (implies --rag). Use project spec or requirements doc.",
    )
    args = parser.parse_args()

    transcript: str
    if args.input == "-" or (args.input is None and not sys.stdin.isatty()):
        transcript = sys.stdin.read()
    elif args.input:
        path = Path(args.input).expanduser().resolve()
        if not path.exists():
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 1
        transcript = path.read_text(encoding="utf-8", errors="replace")
    else:
        print("Path to transcript file (or '-' for stdin): ", end="", flush=True)
        line = (sys.stdin.readline() or "").strip()
        if line == "-":
            transcript = sys.stdin.read()
        elif line:
            path = Path(line).expanduser().resolve()
            if not path.exists():
                print(f"Error: File not found: {path}", file=sys.stderr)
                return 1
            transcript = path.read_text(encoding="utf-8", errors="replace")
        else:
            print("Error: No transcript provided.", file=sys.stderr)
            return 1

    if not transcript.strip():
        print("Error: Transcript is empty.", file=sys.stderr)
        return 1

    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key or not key.startswith("gsk_") or len(key) < 30:
        print("Error: GROQ_API_KEY in .env is missing or invalid.", file=sys.stderr)
        return 1

    project_retriever = None
    if args.rag or args.pdf is not None:
        from src.rag.ingestion_advanced import ingest_pdf_advanced, get_advanced_retriever
        if args.pdf is not None and args.pdf.exists():
            print("Ingesting PDF for RAG...", flush=True)
            project_retriever = ingest_pdf_advanced(args.pdf)
        else:
            project_retriever = get_advanced_retriever()
        if args.pdf is not None and not args.pdf.exists():
            print("Warning: --pdf file not found; using existing index if any.", file=sys.stderr)
        print("Running Agent 4 (chunk → retrieval → map → reduce)...", flush=True)
    else:
        print("Running Agent 4 (chunk → map → reduce)...", flush=True)
    result = run_agent4(transcript, project_retriever=project_retriever)
    if result is None:
        print("Error: Agent returned no result.", file=sys.stderr)
        return 1

    out_json = result.model_dump_json(indent=2)
    print(out_json)
    out_path = args.output or PROJECT_ROOT / "out" / "agent4_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\nSaved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
