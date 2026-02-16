"""
Agent 1 (Project Analyzer) — LangGraph state machine.

Plan-and-solve flow: planner → retrieval → synthesizer.
State carries messages, plan, retrieved context, and final ProjectAnalysis.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .models import ProjectAnalysis

# Groq model (llama3-70b-8192 was decommissioned; use current 70B)
GROQ_MODEL = "llama-3.3-70b-versatile"


class Agent1State(TypedDict, total=False):
    """State for Agent 1 graph. All fields optional so nodes can return partial updates."""

    messages: Annotated[list[BaseMessage], add_messages]
    plan: list[str]
    retrieved_context: str
    final_output: ProjectAnalysis | None


def _get_llm(temperature: float = 0.2) -> ChatGroq:
    """Build ChatGroq LLM. Uses GROQ_API_KEY from environment or .env."""
    try:
        from pathlib import Path
        from dotenv import load_dotenv
        load_dotenv()  # from current working directory
        _root = Path(__file__).resolve().parent.parent.parent.parent
        load_dotenv(_root / ".env")
    except Exception:
        pass
    raw = os.getenv("GROQ_API_KEY") or ""
    api_key = raw.strip().strip('"').strip("'").strip("\r\n")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Create .env in the project root with:\n"
            "  GROQ_API_KEY=gsk_your_key\n"
            "Get a key at https://console.groq.com/keys"
        )
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=temperature,
        api_key=api_key,
    )


def _planner_node(state: Agent1State) -> dict:
    """Produce an extraction plan from the user request."""
    messages = state.get("messages") or []
    last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    _user_text = last.content if last and hasattr(last, "content") else "Analyze the project specification."

    plan = [
        "Identify project name, summary, and full description (comprehensive narrative).",
        "Extract objectives, scope, deliverables, timeline, and assumptions.",
        "Extract all actors with descriptions and responsibilities.",
        "Extract every functional requirement as user stories (with acceptance criteria and notes).",
        "Extract technical constraints with rationale when stated.",
        "Identify all risks (preserve full wording).",
        "Extract key terms and definitions; capture any additional notes.",
    ]
    return {"plan": plan}


# Multiple queries to retrieve more of the document (objectives, scope, requirements, risks, etc.)
RETRIEVAL_QUERIES = [
    "project objectives goals scope description",
    "functional requirements user stories acceptance criteria",
    "technical constraints non-functional requirements",
    "risks assumptions deliverables timeline",
    "actors roles stakeholders responsibilities",
    "key terms glossary definitions",
]


def _retrieval_node(
    state: Agent1State,
    *,
    retriever=None,
) -> dict:
    """Fetch relevant document chunks using multiple queries to get full context."""
    if retriever is None:
        from src.rag.ingestion_advanced import get_advanced_retriever  # noqa: PLC0415
        retriever = get_advanced_retriever()

    seen: set[str] = set()
    parts: list[str] = []
    for q in RETRIEVAL_QUERIES:
        docs = retriever.invoke(q)
        for d in docs or []:
            text = (d.page_content or "").strip()
            if text and text not in seen:
                seen.add(text)
                parts.append(text)
    context = "\n\n---\n\n".join(parts) if parts else ""
    # Cap total context so the model has room for the structured response (~16k context window)
    max_context_len = 14_000
    if len(context) > max_context_len:
        context = context[:max_context_len] + "\n\n[Document truncated for length.]"
    if not context.strip():
        context = "[Aucun extrait du document n'a été récupéré. Vérifiez que le PDF a bien été ingéré.]"
    return {"retrieved_context": context}


def _synthesizer_node(state: Agent1State) -> dict:
    """Produce ProjectAnalysis from plan + retrieved context. Extract all details, do not summarize away content."""
    plan = state.get("plan") or []
    context = state.get("retrieved_context") or ""
    messages = state.get("messages") or []
    last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    user_text = last.content if last and hasattr(last, "content") else "Analyze the project."

    llm = _get_llm()
    structured_llm = llm.with_structured_output(ProjectAnalysis)

    prompt = (
        "You are a project analyst. The 'Document context' block below contains excerpts from a project specification PDF. "
        "Extract ALL details from it into the ProjectAnalysis schema. Preserve the document's wording and language (e.g. if French, keep French). "
        "Use the exact project name as in the document (e.g. 'SmartOps Logistique' if that appears). "
        "Do not describe the analysis task; only extract what is in the document. For any point not in the document, leave the field empty or minimal.\n\n"
        "Extract exhaustively: full_description (full narrative), objectives, scope, deliverables, timeline, assumptions, "
        "actors (with responsibilities), every functional requirement (with acceptance_criteria and notes), "
        "technical_constraints (with rationale when stated), all risks, key_terms/glossary, and additional_notes.\n\n"
        f"Plan:\n" + "\n".join(f"- {s}" for s in plan)
        + f"\n\n--- Document context (PDF content – extract everything from here) ---\n{context}\n--- End ---\n\nUser request: {user_text}"
    )

    try:
        analysis = structured_llm.invoke([HumanMessage(content=prompt)])
        # Fallback if the model returned empty required fields despite having context
        if (analysis and not (analysis.project_name or analysis.summary).strip() and len(context) > 100):
            analysis.project_name = "Projet (voir full_description)"
            analysis.summary = (context[:500] + "…") if len(context) > 500 else context
        return {"final_output": analysis}
    except Exception as e:
        import traceback
        traceback.print_exc(file=__import__("sys").stderr)
        return {"final_output": None}


def build_graph(
    *,
    retriever=None,
    checkpointer: Any = None,
):
    """
    Build and compile the Agent 1 LangGraph.

    Optional retriever: if not provided, uses get_advanced_retriever().
    Optional checkpointer: e.g. SqliteSaver from langgraph.checkpoint.sqlite.
    """
    if retriever is None:
        from src.rag.ingestion_advanced import get_advanced_retriever  # noqa: PLC0415
        retriever = get_advanced_retriever()

    workflow = StateGraph(Agent1State)

    workflow.add_node("planner", _planner_node)
    workflow.add_node(
        "retrieval",
        lambda s: _retrieval_node(s, retriever=retriever),
    )
    workflow.add_node("synthesizer", _synthesizer_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "retrieval")
    workflow.add_edge("retrieval", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile(checkpointer=checkpointer)


def run_agent1(
    user_message: str,
    *,
    retriever=None,
    config: RunnableConfig | None = None,
) -> ProjectAnalysis | None:
    """
    Run Agent 1 on a single user message. Returns ProjectAnalysis or None on failure.
    """
    graph = build_graph(retriever=retriever)
    initial: Agent1State = {
        "messages": [HumanMessage(content=user_message)],
    }
    result = graph.invoke(initial, config=config or {})
    return result.get("final_output")
