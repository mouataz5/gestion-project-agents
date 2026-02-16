"""
Agent 4 (Meeting Summarizer) — Map-Reduce summarization + optional RAG.

Flow: chunk -> [optional RAG over project docs] -> map -> reduce -> MeetingSummary.
When project_retriever is provided, retrieved context grounds the summary in project requirements.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.retrievers import BaseRetriever
from langchain_groq import ChatGroq

from .models import ChunkSummary, MeetingSummary

GROQ_MODEL = "llama-3.3-70b-versatile"

# Chunk size for map step (chars); overlap to avoid cutting mid-sentence
CHUNK_SIZE = 3000
CHUNK_OVERLAP = 300


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


class Agent4State(TypedDict, total=False):
    """State for Agent 4 Map-Reduce graph."""

    transcript: str
    chunks: list[str]
    retrieved_project_context: str  # RAG: project specs/requirements for grounding
    map_summaries: list[ChunkSummary]
    final_output: MeetingSummary | None


def _split_into_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split transcript into overlapping chunks for map step."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Prefer breaking at newline
        if end < len(text):
            last_nl = text.rfind("\n", start, end + 1)
            if last_nl > start:
                end = last_nl + 1
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else len(text)
    return [c for c in chunks if c]


def _retrieval_node(
    state: Agent4State,
    *,
    retriever: BaseRetriever | None = None,
) -> dict:
    """RAG: retrieve relevant project context (specs, requirements) to ground the meeting summary."""
    if retriever is None:
        return {"retrieved_project_context": ""}
    transcript = (state.get("transcript") or "")[:3000]
    if not transcript.strip():
        return {"retrieved_project_context": ""}
    docs = retriever.invoke(transcript)
    context = "\n\n---\n\n".join(
        (d.page_content for d in docs[:5])
    ) if docs else ""
    return {"retrieved_project_context": context[:4000]}


def _map_node(state: Agent4State) -> dict:
    """Map: summarize each chunk into ChunkSummary (key_points + action_items)."""
    chunks = state.get("chunks") or []
    if not chunks:
        return {"map_summaries": []}
    llm = _get_llm(temperature=0.2)
    structured = llm.with_structured_output(ChunkSummary)
    summaries: list[ChunkSummary] = []
    for i, chunk in enumerate(chunks):
        prompt = (
            "You are a meeting secretary. From the following transcript segment, extract:\n"
            "1. key_points: list of main discussion points or decisions in this segment.\n"
            "2. action_items: list of action items (assignee if mentioned, task, due_date if mentioned).\n"
            "Output a ChunkSummary with key_points and action_items. Be concise.\n\n"
            f"--- Segment {i + 1} ---\n{chunk[:4000]}"
        )
        try:
            out = structured.invoke([HumanMessage(content=prompt)])
            summaries.append(out)
        except Exception as e:
            import traceback
            traceback.print_exc(file=__import__("sys").stderr)
            summaries.append(ChunkSummary(key_points=[], action_items=[]))
    return {"map_summaries": summaries}


def _reduce_node(state: Agent4State) -> dict:
    """Reduce: merge map summaries into one MeetingSummary; use transcript start for title/participants/date."""
    transcript = state.get("transcript") or ""
    map_summaries = state.get("map_summaries") or []
    llm = _get_llm(temperature=0.2)
    structured = llm.with_structured_output(MeetingSummary)

    parts = []
    for i, s in enumerate(map_summaries):
        pts = " ".join(s.key_points) if s.key_points else "(none)"
        actions = " | ".join(a.task for a in s.action_items) if s.action_items else "(none)"
        parts.append(f"Segment {i + 1}: Points: {pts}. Actions: {actions}.")
    context = "\n".join(parts)
    # Prepend start of transcript so LLM can infer title, date, participants
    transcript_head = transcript[:2000].strip() if transcript else ""
    project_context = (state.get("retrieved_project_context") or "").strip()

    prompt = (
        "You are a meeting secretary. Merge the segment summaries below into ONE meeting summary.\n"
        "From the 'Transcript start' extract title, date (if any), and participants (names).\n"
        "Output a MeetingSummary: title, date, participants, key_points (merged/deduplicated), "
        "action_items (merged/deduplicated; assignee and due_date when known).\n\n"
    )
    if project_context:
        prompt += "Relevant project context (use to align terminology and link action items to requirements):\n" + project_context + "\n\n"
    if transcript_head:
        prompt += "--- Transcript start ---\n" + transcript_head + "\n\n"
    prompt += "--- Segment summaries ---\n" + context
    try:
        final = structured.invoke([HumanMessage(content=prompt)])
        return {"final_output": final}
    except Exception as e:
        import traceback
        traceback.print_exc(file=__import__("sys").stderr)
        return {
            "final_output": MeetingSummary(
                title="Meeting",
                key_points=[p for s in map_summaries for p in s.key_points],
                action_items=[a for s in map_summaries for a in s.action_items],
            )
        }


def build_summary_graph(project_retriever: BaseRetriever | None = None):
    """Build map-reduce graph. If project_retriever is set, add RAG node after chunk."""
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(Agent4State)

    def _chunk_node(s: Agent4State) -> dict:
        chunks = _split_into_chunks(s.get("transcript") or "")
        return {"chunks": chunks}

    workflow.add_node("chunk", _chunk_node)
    workflow.add_node(
        "retrieval",
        lambda s: _retrieval_node(s, retriever=project_retriever),
    )
    workflow.add_node("map", _map_node)
    workflow.add_node("reduce", _reduce_node)

    workflow.add_edge(START, "chunk")
    workflow.add_edge("chunk", "retrieval")
    workflow.add_edge("retrieval", "map")
    workflow.add_edge("map", "reduce")
    workflow.add_edge("reduce", END)

    return workflow.compile()


def run_agent4(
    transcript: str,
    project_retriever: BaseRetriever | None = None,
) -> MeetingSummary | None:
    """Run Agent 4 on a transcript. Optionally pass project_retriever for RAG (project specs)."""
    graph = build_summary_graph(project_retriever=project_retriever)
    initial: Agent4State = {"transcript": transcript}
    result = graph.invoke(initial)
    return result.get("final_output")
