#!/usr/bin/env python3
"""
Run Agent 5 (Risk Predictor) on Jira history in PostgreSQL.

Usage:
  python scripts/run_agent5.py
  python scripts/run_agent5.py --rag --pdf path/to/spec.pdf   # RAG: ground risks in project docs
  python scripts/run_agent5.py --db-url "postgresql+psycopg2://..."

Requires: PostgreSQL with jira_history (run python -m src.infrastructure.setup_postgres first).
RAG: --rag uses Agent 5's own index (risk_docs); --pdf ingests that PDF into risk_docs.
Output: prints RiskReport JSON and saves to out/agent5_risk_report.json
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
    from src.agents.agent5 import run_agent5

    parser = argparse.ArgumentParser(description="Run Agent 5 (Risk Predictor)")
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="PostgreSQL URL (default: from DATABASE_URL or localhost:5433/agent_platform)",
    )
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Use RAG: ground risk report in project docs (ingest --pdf or use existing project_specs)",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="PDF to ingest for RAG (implies --rag). Use project spec or requirements doc.",
    )
    args = parser.parse_args()

    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key or not key.startswith("gsk_") or len(key) < 30:
        print("Error: GROQ_API_KEY in .env is missing or invalid.", file=sys.stderr)
        return 1

    project_retriever = None
    if args.rag or args.pdf is not None:
        from src.rag.agent5_ingestion import ingest_pdf_for_agent5, get_agent5_retriever
        if args.pdf is not None and args.pdf.exists():
            print("Ingesting PDF for Agent 5 RAG (risk_docs)...", flush=True)
            project_retriever = ingest_pdf_for_agent5(args.pdf)
        else:
            project_retriever = get_agent5_retriever()
        if args.pdf is not None and not args.pdf.exists():
            print("Warning: --pdf file not found; using existing Agent 5 index if any.", file=sys.stderr)
        print("Running Agent 5 (analytics → retrieval → predict)...", flush=True)
    else:
        print("Running Agent 5 (analytics → predict)...", flush=True)

    db_url = args.db_url or os.environ.get("DATABASE_URL", "").strip()
    result = run_agent5(database_url=db_url or None, project_retriever=project_retriever)
    if result is None:
        print("Error: Agent returned no result.", file=sys.stderr)
        return 1

    out_json = result.model_dump_json(indent=2)
    print(out_json)
    out_path = args.output or PROJECT_ROOT / "out" / "agent5_risk_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\nSaved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
