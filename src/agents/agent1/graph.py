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
    """Build ChatGroq LLM. Uses GROQ_API_KEY from environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is required")
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
        "Identify the project name and write a short summary.",
        "Extract all actors (roles/stakeholders) with descriptions.",
        "Extract functional requirements as user stories (actor, action, goal, priority).",
        "Extract technical and non-functional constraints.",
        "Identify project risks.",
    ]
    return {"plan": plan}


def _retrieval_node(
    state: Agent1State,
    *,
    retriever=None,
) -> dict:
    """Fetch relevant document chunks for the current analysis using RAG."""
    if retriever is None:
        from src.rag.ingestion_advanced import get_advanced_retriever  # noqa: PLC0415
        retriever = get_advanced_retriever()

    messages = state.get("messages") or []
    last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    query = last.content if last and hasattr(last, "content") else "project specification requirements"

    docs = retriever.invoke(query)
    context = "\n\n".join(d.page_content for d in docs) if docs else ""
    return {"retrieved_context": context}


def _synthesizer_node(state: Agent1State) -> dict:
    """Produce ProjectAnalysis from plan + retrieved context via structured LLM output."""
    plan = state.get("plan") or []
    context = state.get("retrieved_context") or ""
    messages = state.get("messages") or []
    last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    user_text = last.content if last and hasattr(last, "content") else "Analyze the project."

    llm = _get_llm()
    structured_llm = llm.with_structured_output(ProjectAnalysis)

    prompt = (
        f"Plan:\n" + "\n".join(f"- {s}" for s in plan)
        + f"\n\nContext from documents:\n{context}\n\nUser request: {user_text}"
    )

    try:
        analysis = structured_llm.invoke([HumanMessage(content=prompt)])
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
