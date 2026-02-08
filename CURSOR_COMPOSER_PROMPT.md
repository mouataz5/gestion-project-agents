# Prompt to paste into Cursor Composer (Cmd+I)

Copy the block below and paste it into Cursor Composer when you start a new session or want to give full project context.

---

```
We are building **Gestion of Project Agents**. The first agent is Agent 1 (Project Analyzer): it takes project-spec PDFs and outputs structured analysis (JSON) via RAG + LangGraph.

**Tech stack:** LangGraph (stateful agent), ChatGroq / Llama-3-70B, Qdrant (vector DB), SQLite (state), Pydantic v2. RAG uses ParentDocumentRetriever: child chunks 400 chars (for matching), parent chunks 2000 chars (for LLM context). Embeddings: HuggingFaceEmbeddings (e.g. all-MiniLM-L6-v2).

**Data model (Pydantic):** ProjectAnalysis contains project_name, summary, actors (Actor: name, description), functional_requirements (UserStory: id, actor, action, goal, priority), technical_constraints (category, requirement), identified_risks. All in src/agents/agent1/models.py.

**RAG:** src/rag/ingestion_advanced.py — get_advanced_retriever(), ingest_pdf_advanced(pdf_path). PDF → parent/child split → Qdrant + InMemoryStore docstore.

**Agent flow (LangGraph):** StateGraph with (1) Planner node — break request into steps, (2) Retrieval node — use RAG for current step, (3) Synthesizer node — produce ProjectAnalysis via .with_structured_output(ProjectAnalysis). State: messages, plan, final_output. File: src/agents/agent1/graph.py.

**Conventions:** Strict typing (Python 3.10+), Pydantic for all structured LLM output, separate State/Nodes/Graph in LangGraph. Prefer ParentDocumentRetriever over simple retrieval.

Use @PROJECT_CONTEXT.md for the full project brief. When implementing or refactoring, follow this architecture and file structure.
```

---

Use this whenever you open the project or start a big task so Cursor has full context.
