"""
Agent 3 (Code Reviewer) — Reflection/Critique dual-loop.

Flow: reviewer (draft review) -> critic (additional findings) -> merge -> CodeReviewResult.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.retrievers import BaseRetriever
from langchain_groq import ChatGroq

from .models import CodeReviewResult, CritiqueOutput, Finding

GROQ_MODEL = "llama-3.3-70b-versatile"


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


class Agent3State(TypedDict, total=False):
    """State for Agent 3 graph."""

    code_or_diff: str
    retrieved_code_context: str
    draft_review: CodeReviewResult | None
    critique: CritiqueOutput | None
    final_output: CodeReviewResult | None


def _retrieval_node(state: Agent3State, *, retriever: BaseRetriever | None = None) -> dict:
    """RAG: retrieve relevant code chunks from the codebase for context (GraphRAG-style)."""
    if retriever is None:
        return {"retrieved_code_context": ""}
    code = state.get("code_or_diff") or ""
    docs = retriever.invoke(code[:2000])
    def _fmt(doc: Any) -> str:
        src = doc.metadata.get("source", "?")
        cls = doc.metadata.get("class") or ""
        fn = doc.metadata.get("function") or ""
        parts = [src]
        if cls:
            parts.append(f"class={cls}")
        if fn:
            parts.append(f"function={fn}")
        header = " | ".join(parts)
        return f"[{header}]\n{doc.page_content}"

    context = "\n\n---\n\n".join(_fmt(d) for d in docs) if docs else ""
    return {"retrieved_code_context": context}


def _reviewer_node(state: Agent3State) -> dict:
    """First pass: produce a draft code review (findings + summary), with optional RAG context from state."""
    code = state.get("code_or_diff") or ""
    context = state.get("retrieved_code_context") or ""
    llm = _get_llm(temperature=0.2)
    structured = llm.with_structured_output(CodeReviewResult)
    prompt_parts = [
        "You are a senior developer and security specialist. Review the following code or diff. ",
        "Identify bugs, security issues, and style violations. ",
        "For each finding provide: category (bug|security|style), severity (low|medium|high|critical), ",
        "file_path and line_start if applicable, message, and suggestion. ",
        "End with a short summary. Output a complete CodeReviewResult (findings list + summary).",
    ]
    if context:
        prompt_parts.append(
            "\n\nRelevant context from the codebase (for dependency/usage context):\n" + context[:6000]
        )
    prompt_parts.append("\n\nCode/diff to review:\n" + code)
    prompt = "".join(prompt_parts)
    try:
        draft = structured.invoke([HumanMessage(content=prompt)])
        return {"draft_review": draft}
    except Exception as e:
        import traceback
        traceback.print_exc(file=__import__("sys").stderr)
        return {"draft_review": CodeReviewResult(summary=f"Review failed: {e}")}


def _critic_node(state: Agent3State) -> dict:
    """Second pass: critique the draft review and suggest missed findings."""
    code = state.get("code_or_diff") or ""
    draft = state.get("draft_review")
    if not draft:
        return {"critique": CritiqueOutput(comment="No draft review to critique.")}
    llm = _get_llm(temperature=0.3)
    structured = llm.with_structured_output(CritiqueOutput)
    draft_text = draft.model_dump_json(indent=2) if hasattr(draft, "model_dump_json") else str(draft)
    prompt = (
        "You are a critical reviewer. A first reviewer produced this code review. "
        "Check if they missed any bugs, security issues, or style problems. "
        "Output additional_findings (only what was missed) and a short comment on the draft. "
        "If the draft is thorough, additional_findings can be empty.\n\n"
        "Original code/diff:\n" + code[:4000] + "\n\nDraft review:\n" + draft_text
    )
    try:
        critique = structured.invoke([HumanMessage(content=prompt)])
        return {"critique": critique}
    except Exception as e:
        import traceback
        traceback.print_exc(file=__import__("sys").stderr)
        return {"critique": CritiqueOutput(comment=str(e))}


def _merge_node(state: Agent3State) -> dict:
    """Merge draft review + critic's additional findings into final CodeReviewResult."""
    draft = state.get("draft_review")
    critique = state.get("critique")
    if not draft:
        return {"final_output": CodeReviewResult(summary="No review produced.")}
    findings = list(draft.findings) if draft.findings else []
    if critique and critique.additional_findings:
        findings = findings + critique.additional_findings
    summary = draft.summary or ""
    if critique and critique.comment:
        summary = summary.rstrip() + "\n\nCritic: " + critique.comment
    return {
        "final_output": CodeReviewResult(
            findings=findings,
            summary=summary,
        )
    }


def build_review_graph(code_retriever: BaseRetriever | None = None):
    """Build retrieval -> reviewer -> critic -> merge graph. Use code_retriever for RAG context."""
    from langgraph.graph import END, START, StateGraph
    workflow = StateGraph(Agent3State)
    workflow.add_node(
        "retrieval",
        lambda s: _retrieval_node(s, retriever=code_retriever),
    )
    workflow.add_node("reviewer", _reviewer_node)
    workflow.add_node("critic", _critic_node)
    workflow.add_node("merge", _merge_node)
    workflow.add_edge(START, "retrieval")
    workflow.add_edge("retrieval", "reviewer")
    workflow.add_edge("reviewer", "critic")
    workflow.add_edge("critic", "merge")
    workflow.add_edge("merge", END)
    return workflow.compile()


def run_agent3(
    code_or_diff: str,
    code_retriever: BaseRetriever | None = None,
) -> CodeReviewResult | None:
    """Run Agent 3 on a code snippet or diff. Optionally pass code_retriever for RAG context."""
    graph = build_review_graph(code_retriever=code_retriever)
    initial: Agent3State = {"code_or_diff": code_or_diff}
    result = graph.invoke(initial)
    return result.get("final_output")
