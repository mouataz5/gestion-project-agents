"""
Verify PostgreSQL data layer: row counts and sample queries.

Run after setup: python -m src.infrastructure.check_db
"""

from __future__ import annotations

import sys
from sqlalchemy import text
from sqlalchemy import create_engine

DATABASE_URL = "postgresql+psycopg2://admin:password123@localhost:5433/agent_platform"


def _out(*args: object, **kwargs: object) -> None:
    """Print and flush so result always shows (e.g. in Docker/IDE)."""
    print(*args, **kwargs, flush=True)


def main() -> int:
    try:
        engine = create_engine(DATABASE_URL, future=True)
    except Exception as e:
        _out(f"Connection failed: {e}", file=sys.stderr)
        return 1

    try:
        with engine.connect() as conn:
            _out("")
            _out("========== DB Verification ==========")

            (dev_count,) = conn.execute(text("SELECT COUNT(*) FROM developers")).fetchone()
            (jira_count,) = conn.execute(text("SELECT COUNT(*) FROM jira_history")).fetchone()
            _out(f"  developers:   {dev_count} rows")
            _out(f"  jira_history: {jira_count} rows")
            _out("")

            # Query: average actual_hours FROM jira_history WHERE category='Database'
            row = conn.execute(
                text("""
                    SELECT AVG(actual_hours)::FLOAT AS avg_actual,
                           AVG(estimated_hours)::FLOAT AS avg_estimated
                    FROM jira_history WHERE category = 'Database'
                """)
            ).fetchone()
            avg_actual = row[0]
            avg_estimated = row[1]
            _out("  Query: SELECT average actual_hours FROM jira_history WHERE category='Database'")
            _out(f"  Result: average actual_hours = {avg_actual:.2f}")
            _out(f"  (avg estimated_hours = {avg_estimated:.2f}  →  Database tasks ~{avg_actual / avg_estimated:.2f}x estimated)")
            _out("")

            # Sample rows so something visible is returned
            _out("  Sample developers (first 3):")
            for r in conn.execute(text("SELECT id, name, role, seniority, hourly_rate FROM developers LIMIT 3")):
                _out(f"    id={r[0]}  {r[1]}  | {r[2]}  {r[3]}  | {r[4]} €/h")
            _out("")
            _out("  Sample jira_history (first 3):")
            for r in conn.execute(
                text("SELECT ticket_id, category, complexity, estimated_hours, actual_hours, status FROM jira_history LIMIT 3")
            ):
                _out(f"    {r[0]}  | {r[1]}  {r[2]}  | est={r[3]}h  actual={r[4]}h  | {r[5]}")
            _out("")
            _out("======================================")
            _out("")
    except Exception as e:
        _out(f"Query failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
