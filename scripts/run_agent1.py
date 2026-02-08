#!/usr/bin/env python3
"""
Run Agent 1 (Project Analyzer) on a PDF spec.

Usage:
  export GROQ_API_KEY="your-key"
  python scripts/run_agent1.py [path/to/spec.pdf]

If no path is given, uses the default below.
Output: prints ProjectAnalysis as JSON and saves to out/agent1_analysis.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Project root = parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Default PDF path
DEFAULT_PDF_PATH = Path("/Users/certideal/Downloads/cahier_des_charges_final.pdf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Agent 1 on a project-spec PDF")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        type=Path,
        default=DEFAULT_PDF_PATH,
        help=f"Path to the PDF (default: {DEFAULT_PDF_PATH})",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output JSON file (default: out/agent1_analysis.json)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    # Import after path is set
    from src.rag.ingestion_advanced import ingest_pdf_advanced
    from src.agents.agent1 import run_agent1

    print("Ingesting PDF...", flush=True)
    ingest_pdf_advanced(pdf_path)
    print("Running Agent 1...", flush=True)

    result = run_agent1(
        "Analyse le cahier des charges et extrais: nom du projet, résumé, acteurs, "
        "exigences fonctionnelles (user stories), contraintes techniques et risques identifiés. "
        "Output a complete ProjectAnalysis in the required schema."
    )

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
