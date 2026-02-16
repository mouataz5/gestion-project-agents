"""
PostgreSQL + pgvector schema and seed script (SQLAlchemy Core / raw SQL).

Run after Docker is up: python -m src.infrastructure.setup_postgres
"""

from __future__ import annotations

import json
import random
import sys
from faker import Faker
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

# Use port 5433 when running via Docker (host map); 5432 if Postgres is local
DATABASE_URL = "postgresql+psycopg2://admin:password123@localhost:5433/agent_platform"

# Roles and correlated skills (Backend = Python/Go, Frontend = React/JS, etc.)
ROLE_SKILLS: dict[str, dict[str, float]] = {
    "Backend": {"Python": 0.92, "Go": 0.75, "SQL": 0.88, "API": 0.9, "Docker": 0.6},
    "Frontend": {"React": 0.9, "JavaScript": 0.95, "TypeScript": 0.85, "CSS": 0.88, "HTML": 0.9},
    "DevOps": {"Docker": 0.95, "Kubernetes": 0.85, "CI/CD": 0.9, "Terraform": 0.7, "Linux": 0.9},
    "Full Stack": {"Python": 0.7, "React": 0.8, "JavaScript": 0.85, "SQL": 0.75, "Docker": 0.65},
    "QA": {"Selenium": 0.85, "Python": 0.6, "API Testing": 0.9, "Jira": 0.95, "Test Design": 0.9},
}
SENIORITIES = ["Junior", "Mid", "Senior"]
JIRA_CATEGORIES = ["Database", "Backend", "Frontend", "DevOps", "QA", "Security"]
COMPLEXITIES = ["Low", "Medium", "High"]
STATUSES = ["Done", "In Progress", "To Do"]


def get_engine(url: str = DATABASE_URL) -> Engine:
    """Create SQLAlchemy engine. Connection errors surface on first use."""
    return create_engine(url, future=True)


def enable_pgvector(engine: Engine) -> None:
    """Enable pgvector extension."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()


def drop_and_create_tables(engine: Engine) -> None:
    """Drop tables if exist and create fresh schema (project_docs, developers, jira_history)."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS project_docs CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS developers CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS jira_history CASCADE;"))
        conn.commit()

    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE project_docs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT,
                metadata JSONB,
                embedding vector(384)
            );
            """)
        )
        conn.execute(
            text("""
            CREATE TABLE developers (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                seniority TEXT NOT NULL,
                skills JSONB NOT NULL,
                hourly_rate INT NOT NULL,
                reliability_score FLOAT NOT NULL
            );
            """)
        )
        conn.execute(
            text("""
            CREATE TABLE jira_history (
                ticket_id VARCHAR(64) PRIMARY KEY,
                category TEXT NOT NULL,
                complexity TEXT NOT NULL,
                estimated_hours INT NOT NULL,
                actual_hours INT NOT NULL,
                status TEXT NOT NULL,
                assignee_id INT REFERENCES developers(id)
            );
            """)
        )
        conn.commit()


def seed_developers(engine: Engine, count: int = 15) -> None:
    """Generate developers with role-correlated skills (Faker names, realistic rates)."""
    fake = Faker()
    Faker.seed(42)
    random.seed(42)

    roles = list(ROLE_SKILLS.keys())
    with engine.connect() as conn:
        for i in range(count):
            role = roles[i % len(roles)]
            skills = ROLE_SKILLS[role].copy()
            # Slight variance in skill levels
            skills = {k: round(min(1.0, max(0.1, v + random.uniform(-0.1, 0.1))), 2) for k, v in skills.items()}
            seniority = random.choice(SENIORITIES)
            # Hourly rate by seniority (rough)
            base_rate = {"Junior": 45, "Mid": 75, "Senior": 120}[seniority]
            hourly_rate = base_rate + random.randint(-5, 15)
            reliability_score = round(random.uniform(0.7, 0.99), 2)
            name = fake.name()
            conn.execute(
                text("""
                INSERT INTO developers (name, role, seniority, skills, hourly_rate, reliability_score)
                VALUES (:name, :role, :seniority, CAST(:skills AS jsonb), :hourly_rate, :reliability_score)
                """),
                {
                    "name": name,
                    "role": role,
                    "seniority": seniority,
                    "skills": json.dumps(skills),
                    "hourly_rate": hourly_rate,
                    "reliability_score": reliability_score,
                },
            )
        conn.commit()


def seed_jira_history(engine: Engine, count: int = 500) -> None:
    """Generate Jira tickets; Database tasks take ~1.5x estimated_hours (hidden pattern). Assignees 1–15."""
    random.seed(43)
    developer_ids = list(range(1, 16))  # 15 developers

    with engine.connect() as conn:
        for i in range(1, count + 1):
            ticket_id = f"PROJ-{i}"
            category = random.choice(JIRA_CATEGORIES)
            complexity = random.choice(COMPLEXITIES)
            estimated_hours = random.randint(1, 40)
            # Hidden pattern: Database tasks take ~1.5x longer than estimated
            if category == "Database":
                actual_hours = int(estimated_hours * 1.5 + random.uniform(-2, 5))
                actual_hours = max(1, actual_hours)
            else:
                actual_hours = int(estimated_hours * random.uniform(0.7, 1.3))
                actual_hours = max(1, actual_hours)
            status = random.choice(STATUSES)
            assignee_id = random.choice(developer_ids)
            conn.execute(
                text("""
                INSERT INTO jira_history (ticket_id, category, complexity, estimated_hours, actual_hours, status, assignee_id)
                VALUES (:ticket_id, :category, :complexity, :estimated_hours, :actual_hours, :status, :assignee_id)
                """),
                {
                    "ticket_id": ticket_id,
                    "category": category,
                    "complexity": complexity,
                    "estimated_hours": estimated_hours,
                    "actual_hours": actual_hours,
                    "status": status,
                    "assignee_id": assignee_id,
                },
            )
        conn.commit()


def main() -> int:
    """Connect, enable extension, create tables, seed developers and jira_history."""
    try:
        engine = get_engine()
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        print("Ensure PostgreSQL is running (e.g. docker compose up -d).", file=sys.stderr)
        return 1
    try:
        with engine.connect() as _:
            pass
    except Exception as e:
        print(f"Cannot connect to DB: {e}", file=sys.stderr)
        return 1

    def _out(msg: str) -> None:
        print(msg, flush=True)

    _out("Enabling pgvector extension...")
    enable_pgvector(engine)
    _out("Dropping and creating tables...")
    drop_and_create_tables(engine)
    _out("Seeding 15 developers...")
    seed_developers(engine, 15)
    _out("Seeding 500 Jira tickets...")
    seed_jira_history(engine, 500)
    _out("")
    _out("Done. Tables: project_docs, developers (15 rows), jira_history (500 rows).")
    _out("Verify: python -m src.infrastructure.check_db")
    _out("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
