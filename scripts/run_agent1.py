#!/usr/bin/env python3
"""
Run Agent 1 (Project Analyzer) on a PDF spec.

Usage:
  python scripts/run_agent1.py                    → prompts: "PDF path: " (paste path, Enter)
  python scripts/run_agent1.py path/to/file.pdf → runs directly on that PDF

No need to change any path in the script. Result is printed and saved to out/agent1_analysis.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Project root = parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env so GROQ_API_KEY is set (run from project root: cd gestion-project-agents)
from dotenv import load_dotenv
load_dotenv()
load_dotenv(PROJECT_ROOT / ".env")

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Agent 1 on a project-spec PDF. Pass path as argument or you will be prompted."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        type=str,
        default=None,
        help="Path to the PDF. If omitted, you will be prompted to paste or type it.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output JSON file (default: out/agent1_analysis.json)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not pdf_path or not pdf_path.strip():
        print("PDF path: ", end="", flush=True)
        pdf_path = (sys.stdin.readline() or "").strip()
    if not pdf_path:
        print("Error: No PDF path given.", file=sys.stderr)
        return 1
    pdf_path = Path(pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    # Import after path is set
    from src.rag.ingestion_advanced import ingest_pdf_advanced
    from src.agents.agent1 import run_agent1

    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key or not key.startswith("gsk_") or len(key) < 30:
        print("Error: GROQ_API_KEY in .env is missing or invalid (must start with gsk_ and be a long string).", file=sys.stderr)
        print("Edit .env in the project root. Get a key at https://console.groq.com/keys", file=sys.stderr)
        return 1

    print("Ingesting PDF...", flush=True)
    # Use qdrant_data; if locked by another process, use qdrant_data_run
    qdrant_path = PROJECT_ROOT / "qdrant_data"
    try:
        ingest_pdf_advanced(pdf_path, path=str(qdrant_path))
    except RuntimeError as e:
        if "already accessed" in str(e) or "AlreadyLocked" in str(type(e).__name__):
            qdrant_path = PROJECT_ROOT / "qdrant_data_run"
            ingest_pdf_advanced(pdf_path, path=str(qdrant_path))
        else:
            raise

    # Load PDF text so the synthesizer has full content even if RAG returns little (e.g. scanned PDF)
    from langchain_community.document_loaders import PyPDFLoader
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()
    pdf_text = "\n\n".join(d.page_content for d in docs if getattr(d, "page_content", None)).strip()
    pdf_text = pdf_text[:14_000] + ("…" if len(pdf_text) > 14_000 else "")

    print("Running Agent 1...", flush=True)
    user_message = (
        "Extract the full project specification from the document below. "
        "Keep the project name and language as in the document. Fill every field of ProjectAnalysis; preserve wording.\n\n"
        "--- Document ---\n" + (pdf_text or "(No text could be extracted from the PDF.)") + "\n--- End ---"
    )
    result = run_agent1(user_message)

    if result is None:
        print("Error: Agent returned no analysis. Check the traceback above (e.g. GROQ_API_KEY, rate limit, or LLM output format).", file=sys.stderr)
        return 1

    out_json = result.model_dump_json(indent=2)
    print(out_json)

    out_path = args.output or PROJECT_ROOT / "out" / "agent1_analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\nSaved to {out_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
