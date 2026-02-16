"""
Agent 5 (Risk Predictor) — Jira history analytics + optional RAG + LLM risk interpretation.

Flow: analytics -> [optional RAG over project docs] -> predict -> RiskReport.
When project_retriever is set, retrieved context grounds risk factors and recommendations in project requirements.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langchain_core.retrievers import BaseRetriever
from langchain_groq import ChatGroq
from sqlalchemy import text
from sqlalchemy import create_engine

from .models import Alert, DelayPrediction, MitigationPlan, RiskFactor, RiskReport

GROQ_MODEL = "llama-3.3-70b-versatile"

# Same DB as infrastructure (jira_history); override with DATABASE_URL env if needed
DEFAULT_DATABASE_URL = "postgresql+psycopg2://admin:password123@localhost:5433/agent_platform"


def _get_db_url() -> str:
    return os.getenv("DATABASE_URL", "").strip() or DEFAULT_DATABASE_URL


def _get_llm(temperature: float = 0.2) -> ChatGroq:
    """Build ChatGroq LLM. Uses GROQ_API_KEY from environment or .env."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        _root = Path(__file__).resolve().parent.parent.parent.parent
        load_dotenv(_root / ".env")
    except Exception:
        pass
    raw = os.getenv("GROQ_API_KEY") or ""
    api_key = raw.strip().strip('"').strip("'").strip("\r\n")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Create .env in the project root. "
            "Get a key at https://console.groq.com/keys"
        )
    return ChatGroq(model=GROQ_MODEL, temperature=temperature, api_key=api_key)


class Agent5State(TypedDict, total=False):
    """State for Agent 5 graph."""

    database_url: str
    analytics_text: str
    delay_predictions: list[DelayPrediction]
    retrieved_project_context: str  # RAG: project specs/requirements for grounding
    risk_report: RiskReport | None


def _fetch_analytics(state: Agent5State) -> dict:
    """OF5.1/5.2: Query jira_history — by-category and overall delays; OF5.3/5.4: team workload and budget."""
    url = state.get("database_url") or _get_db_url()
    engine = create_engine(url, future=True)
    delay_predictions: list[DelayPrediction] = []
    lines: list[str] = []

    try:
        conn = engine.connect()
    except Exception as e:
        raise RuntimeError(
            "Cannot connect to PostgreSQL. Start the DB (e.g. docker compose -p agentdata up -d) "
            "and run python -m src.infrastructure.setup_postgres."
        ) from e
    with conn:
        # By category
        rows = conn.execute(
            text("""
                SELECT category,
                       AVG(estimated_hours)::FLOAT AS avg_est,
                       AVG(actual_hours)::FLOAT AS avg_actual,
                       COUNT(*)::INT AS cnt
                FROM jira_history
                GROUP BY category
                ORDER BY avg_actual DESC
            """)
        ).fetchall()
        for row in rows:
            cat, avg_est, avg_actual, cnt = row
            ratio = avg_actual / avg_est if avg_est and avg_est > 0 else 1.0
            delay_predictions.append(
                DelayPrediction(
                    category=cat,
                    avg_estimated_hours=round(avg_est, 2),
                    avg_actual_hours=round(avg_actual, 2),
                    delay_ratio=round(ratio, 2),
                    ticket_count=cnt,
                )
            )
            lines.append(f"  {cat}: avg estimated={avg_est:.1f}h, avg actual={avg_actual:.1f}h, ratio={ratio:.2f}x, count={cnt}")

        # Overall
        row = conn.execute(
            text("""
                SELECT AVG(estimated_hours)::FLOAT, AVG(actual_hours)::FLOAT, COUNT(*)::INT
                FROM jira_history
            """)
        ).fetchone()
        if row and row[2]:
            avg_est, avg_actual, cnt = row
            ratio = avg_actual / avg_est if avg_est and avg_est > 0 else 1.0
            delay_predictions.append(
                DelayPrediction(
                    category="Overall",
                    avg_estimated_hours=round(avg_est, 2),
                    avg_actual_hours=round(avg_actual, 2),
                    delay_ratio=round(ratio, 2),
                    ticket_count=cnt,
                )
            )
            lines.append(f"  Overall: avg estimated={avg_est:.1f}h, avg actual={avg_actual:.1f}h, ratio={ratio:.2f}x, count={cnt}")

        # OF5.4: Per-developer workload (if assignee_id present)
        try:
            workload_rows = conn.execute(
                text("""
                    SELECT d.id, d.name, d.role,
                           COALESCE(SUM(j.actual_hours), 0)::FLOAT AS total_hours,
                           COUNT(j.ticket_id)::INT AS ticket_count
                    FROM developers d
                    LEFT JOIN jira_history j ON j.assignee_id = d.id
                    GROUP BY d.id, d.name, d.role
                    ORDER BY total_hours DESC
                """)
            ).fetchall()
            lines.append("\nTeam workload (actual hours per developer):")
            for r in workload_rows:
                dev_id, name, role, total_h, tc = r
                lines.append(f"  dev {dev_id} ({name}, {role}): {total_h:.0f}h, {tc} tickets")
        except Exception:
            lines.append("\nTeam workload: assignee_id not available (skip OF5.4).")

        # OF5.3: Budget (estimated vs actual cost using hourly_rate)
        try:
            budget_row = conn.execute(
                text("""
                    SELECT
                        SUM(j.estimated_hours * d.hourly_rate)::FLOAT AS estimated_cost,
                        SUM(j.actual_hours * d.hourly_rate)::FLOAT AS actual_cost
                    FROM jira_history j
                    JOIN developers d ON d.id = j.assignee_id
                """)
            ).fetchone()
            if budget_row and budget_row[0]:
                est_cost, act_cost = budget_row
                overrun_pct = ((act_cost - est_cost) / est_cost * 100) if est_cost else 0
                lines.append(f"\nBudget: estimated cost={est_cost:.0f}, actual cost={act_cost:.0f}, overrun={overrun_pct:.1f}%")
            else:
                lines.append("\nBudget: no assignee data (skip OF5.3).")
        except Exception:
            lines.append("\nBudget: assignee_id not available (skip OF5.3).")

    analytics_text = "Project metrics (Jira history — estimated vs actual hours, team workload, budget):\n" + "\n".join(lines)
    return {"analytics_text": analytics_text, "delay_predictions": delay_predictions}


class _RiskInterpretation(BaseModel):
    """LLM output for OF5.1–OF5.8: summary, risks (with probability/impact), mitigations, alerts, budget/team/dependency risks."""
    summary: str
    risk_factors: list[RiskFactor]
    recommendations: list[str]
    mitigation_plans: list[MitigationPlan] = []
    alerts: list[Alert] = []
    budget_risks: list[str] = []
    team_overload_risks: list[str] = []
    dependency_risks: list[str] = []


def _retrieval_node(
    state: Agent5State,
    *,
    retriever: BaseRetriever | None = None,
) -> dict:
    """RAG: retrieve relevant project context (specs, requirements) to ground risk analysis."""
    if retriever is None:
        return {"retrieved_project_context": ""}
    analytics_text = (state.get("analytics_text") or "")[:2500]
    query = analytics_text or "project risks delays requirements"
    docs = retriever.invoke(query)
    context = "\n\n---\n\n".join(d.page_content for d in docs[:5]) if docs else ""
    return {"retrieved_project_context": context[:4000]}


def _predict_node(state: Agent5State) -> dict:
    """LLM interprets analytics (OF5.1–OF5.8); merge with DB delay_predictions into RiskReport."""
    analytics_text = state.get("analytics_text") or ""
    delay_predictions = state.get("delay_predictions") or []
    project_context = (state.get("retrieved_project_context") or "").strip()

    llm = _get_llm(temperature=0.2)
    structured = llm.with_structured_output(_RiskInterpretation)
    prompt = (
        "You are a project risk analyst. Use the following project metrics (OF5.1 real-time-style metrics from Jira history) "
        "to produce a full risk report.\n\n"
        "Output:\n"
        "(1) summary — short overall risk summary.\n"
        "(2) risk_factors — list of {factor, description, severity, probability (0–1), impact (low/medium/high), evidence}. "
        "OF5.6: estimate probability and impact for each risk.\n"
        "(3) recommendations — concrete actions to reduce delay risk.\n"
        "(4) mitigation_plans — OF5.7: list of {action, owner_suggestion, priority} for automatic mitigation.\n"
        "(5) alerts — OF5.8: list of {level: info|warning|critical, message, suggested_action} to trigger corrective actions.\n"
        "(6) budget_risks — OF5.3: from analytics budget overrun data, list budget overrun risks (or empty if no data).\n"
        "(7) team_overload_risks — OF5.4: from team workload (total hours per developer), identify overload/burnout risks (or empty if no data).\n"
        "(8) dependency_risks — OF5.5: from project context or general knowledge, list blocking technical dependency risks (or empty).\n\n"
    )
    if project_context:
        prompt += "Relevant project context:\n" + project_context + "\n\n"
    prompt += "--- Analytics ---\n" + analytics_text
    try:
        out = structured.invoke([HumanMessage(content=prompt)])
        report = RiskReport(
            summary=out.summary,
            risk_factors=out.risk_factors,
            delay_predictions=delay_predictions,
            recommendations=out.recommendations,
            mitigation_plans=out.mitigation_plans,
            alerts=out.alerts,
            budget_risks=out.budget_risks,
            team_overload_risks=out.team_overload_risks,
            dependency_risks=out.dependency_risks,
        )
        return {"risk_report": report}
    except Exception as e:
        import traceback
        traceback.print_exc(file=__import__("sys").stderr)
        return {
            "risk_report": RiskReport(
                summary="Analysis failed: " + str(e),
                delay_predictions=delay_predictions,
            )
        }


def build_risk_graph(
    database_url: str | None = None,
    project_retriever: BaseRetriever | None = None,
):
    """Build analytics -> [retrieval] -> predict graph. Optionally pass project_retriever for RAG."""
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(Agent5State)

    def _analytics_node(s: Agent5State) -> dict:
        if database_url:
            s = {**s, "database_url": database_url}
        return _fetch_analytics(s)

    workflow.add_node("analytics", _analytics_node)
    workflow.add_node(
        "retrieval",
        lambda s: _retrieval_node(s, retriever=project_retriever),
    )
    workflow.add_node("predict", _predict_node)
    workflow.add_edge(START, "analytics")
    workflow.add_edge("analytics", "retrieval")
    workflow.add_edge("retrieval", "predict")
    workflow.add_edge("predict", END)

    return workflow.compile()


def run_agent5(
    database_url: str | None = None,
    project_retriever: BaseRetriever | None = None,
) -> RiskReport | None:
    """Run Agent 5: fetch Jira analytics, optionally RAG over project docs, then LLM risk report."""
    graph = build_risk_graph(database_url=database_url, project_retriever=project_retriever)
    result = graph.invoke({})
    return result.get("risk_report")
