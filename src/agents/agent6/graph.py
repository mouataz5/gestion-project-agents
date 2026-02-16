"""
Agent 6 (Documentation Writer) — ReAct with file browsing tools, then generate README + API docs.

Flow: agent (with list_directory, read_file) <-> tools loop until done -> generate -> DocumentationResult.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .models import DocumentationResult
from .tools import get_doc_tools

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


class Agent6State(TypedDict, total=False):
    """State for Agent 6 ReAct graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    final_output: DocumentationResult | None


def _agent_node(
    state: Agent6State,
    *,
    llm_with_tools: ChatGroq,
) -> dict:
    """ReAct agent: invoke LLM with tools; returns new messages."""
    messages = state.get("messages") or []
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def _tools_node(
    state: Agent6State,
    *,
    tools: list[BaseTool],
) -> dict:
    """Execute tool calls from last AIMessage and return ToolMessages."""
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}
    tool_by_name = {t.name: t for t in tools}
    tool_messages = []
    for tc in last.tool_calls:
        name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
        args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
        tid = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
        if name not in tool_by_name:
            tool_messages.append(ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tid))
            continue
        try:
            result = tool_by_name[name].invoke(args)
            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tid))
        except Exception as e:
            tool_messages.append(ToolMessage(content=f"Error: {e}", tool_call_id=tid))
    return {"messages": tool_messages}


def _should_continue(state: Agent6State) -> str:
    """Route to tools if last message has tool_calls, else to generate."""
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "generate"


def _generate_node(state: Agent6State) -> dict:
    """Produce DocumentationResult from conversation (no tools)."""
    messages = state.get("messages") or []
    llm = _get_llm(temperature=0.2)
    structured = llm.with_structured_output(DocumentationResult)
    # Summarize conversation for context (last N messages or full)
    context_parts = []
    for m in messages[-20:]:
        if hasattr(m, "content") and m.content:
            context_parts.append(f"{type(m).__name__}: {str(m.content)[:2000]}")
    context = "\n\n".join(context_parts)[:12000]
    prompt = (
        "You are a technical writer. Based on the following exploration of a codebase (directory listings, file contents, project_stats, file_modified_time), "
        "produce a DocumentationResult:\n"
        "1. readme_content: A README (overview, setup/install, usage, project structure).\n"
        "2. api_docs: List of APIModuleDoc (module_path, description, functions with name, signature, description). "
        "OF6.1: API docs from source. OF6.2: Include any JSDoc/TSDoc or docstrings in function descriptions.\n"
        "3. documentation_coverage_pct (OF6.8): 0–100. If project_stats was used, coverage = (number of modules you documented / total code files) * 100; else estimate.\n"
        "4. obsolete_doc_warnings (OF6.7): List warnings if some docs are older than code (from file_modified_time) or key files are missing from docs.\n"
        "5. language (OF6.6): 'en', 'fr', or 'es' — language of readme_content and api_docs.\n\n"
        "--- Exploration ---\n" + context
    )
    try:
        result = structured.invoke([HumanMessage(content=prompt)])
        return {"final_output": result}
    except Exception as e:
        import traceback
        traceback.print_exc(file=__import__("sys").stderr)
        return {"final_output": DocumentationResult(readme_content=f"Generation failed: {e}")}


def build_docs_graph(root_path: Path):
    """Build ReAct graph: agent <-> tools -> generate -> END. Tools are scoped to root_path."""
    workflow = StateGraph(Agent6State)
    tools = get_doc_tools(Path(root_path))
    llm = _get_llm(temperature=0.2)
    llm_with_tools = llm.bind_tools(tools)

    workflow.add_node(
        "agent",
        lambda s: _agent_node(s, llm_with_tools=llm_with_tools),
    )
    workflow.add_node(
        "tools",
        lambda s: _tools_node(s, tools=tools),
    )
    workflow.add_node("generate", _generate_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", _should_continue, {"tools": "tools", "generate": "generate"})
    workflow.add_edge("tools", "agent")
    workflow.add_edge("generate", END)

    return workflow.compile()


def run_agent6(
    project_path: str | Path,
    language: str = "en",
) -> DocumentationResult | None:
    """Run Agent 6 on a project directory: ReAct exploration then generate README + API docs (OF6.6: language en/fr/es)."""
    root = Path(project_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {project_path}")
    lang_instruction = ""
    if language and language != "en":
        lang_instruction = f" Output the final documentation in language '{language}' (set the 'language' field to '{language}'). "
    graph = build_docs_graph(root)
    initial: Agent6State = {
        "messages": [
            HumanMessage(
                content=f"Generate a README and API documentation for this project. Root path: {root.name}. "
                "Start by listing the root directory, then read key files (README if any, main modules, package structure). "
                "Use project_stats to count code files (for documentation coverage). Use file_modified_time on README or key files to detect obsolete docs. "
                f"{lang_instruction}"
                "When you have enough context, you will be asked to produce the final documentation (including coverage_pct and obsolete_doc_warnings)."
            )
        ]
    }
    result = graph.invoke(initial)
    return result.get("final_output")
