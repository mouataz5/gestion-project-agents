# Gestion of Project Agents — Full Project Context

Use this document to onboard Cursor (Composer/Chat) or any developer. Reference it with `@PROJECT_CONTEXT.md` when starting a task.

---

## 1. Vision & Goal

This project is **Gestion of Project Agents**: a system of AI agents for project management. The first agent we are building is **Agent 1: Project Analyzer** — an AI agent that:

- **Input:** Project specification documents (e.g. PDFs) — requirements, briefs, RFPs.
- **Output:** Structured analysis (JSON) suitable for storage and downstream agents: project name, summary, actors, user stories, technical constraints, and risks.
- **Principle:** We are **architecting**, not just coding. Data structures and clear pipelines come first.

The agent uses **RAG (Retrieval-Augmented Generation)** to ground the LLM in the document, then **structured output (Pydantic)** so the result is always valid, storable JSON — not free-form chat.

---

## 2. Tech Stack

| Layer | Technology |
|-------|------------|
| **Agent framework** | LangGraph (stateful, multi-node graphs) |
| **LLM** | ChatGroq with Llama-3-70B |
| **Vector DB** | Qdrant (local path or remote) |
| **State / persistence** | SQLite (for agent state, not vector store) |
| **Validation & output** | Pydantic v2 (strict structured output) |
| **RAG** | LangChain + ParentDocumentRetriever |
| **Embeddings** | HuggingFaceEmbeddings (e.g. `all-MiniLM-L6-v2`) |
| **Language** | Python 3.10+ with full type hints |

---

## 3. Data Model (The “Brain Structure”)

All structured output from Agent 1 conforms to these Pydantic models. The LLM is instructed to **fill this schema**, not to summarize in prose.

- **Actor** — A user role: `name`, `description`.
- **UserStory** — One requirement in “who / what / why” form: `id`, `actor`, `action`, `goal`, `priority` (High/Medium/Low).
- **TechnicalConstraint** — A non-functional or technical requirement: `category` (e.g. Database, Security), `requirement` (text).
- **ProjectAnalysis** — Root output: `project_name`, `summary` (short), `actors`, `functional_requirements` (UserStory list), `technical_constraints`, `identified_risks` (list of strings).

Location: `src/agents/agent1/models.py`. Every LLM call that produces “the analysis” must use `.with_structured_output(ProjectAnalysis)`.

---

## 4. RAG Strategy: Parent–Child Chunks

We use **ParentDocumentRetriever**, not simple chunk retrieval:

- **Child chunks:** Small (e.g. 400 chars). Used for **matching** (good for keywords and precise hits).
- **Parent chunks:** Larger (e.g. 2000 chars). **Returned to the LLM** as context (enough to understand requirements).

Flow: index child chunks in Qdrant; store parent docs in a docstore (e.g. `InMemoryStore` for dev; Redis in production). On query, retrieve by child, then return the corresponding parent(s).

- **Components:** `RecursiveCharacterTextSplitter` for both sizes, Qdrant as vector store, HuggingFaceEmbeddings.
- **Location:** `src/rag/ingestion_advanced.py` — functions like `get_advanced_retriever()` and `ingest_pdf_advanced(pdf_path)`.

---

### 4.1 Agent 3: AST-Aware RAG (Structure-based Splitting)

We do **not** use standard character-based chunking for code. Arbitrary 500-character chunks make the reviewer see a function without knowing which class it belongs to or which files call it (“spooky action at a distance”).

**Chosen approach (Sprint 1 — “Repo Map”):**

- **AST-aware RAG (structure-based splitting).** We split code by **functions and classes** (semantic units), not by character count.
- **Tooling:** Python’s built-in `ast` module to parse each `.py` file; we derive one chunk per top-level function and per top-level class (or per method if we need finer granularity). Optional: `langchain_text_splitters.Language.PYTHON` with `RecursiveCharacterTextSplitter.from_language()` for language-aware boundaries.
- **Metadata in Qdrant:** Every chunk carries `file`, `file_path`, `class`, `function`, and **imports** (list of imported modules/symbols). This lets the retriever and the LLM know where the code lives and how files relate (e.g. “this file imports `database`”).
- **Result:** Agent 3 can reason about “this function is in class X” and “file A imports file B,” reducing isolated-snippet reviews and enabling logic-aware feedback.

**Future (Sprint 2 — full GraphRAG):** Move to a true dependency graph (e.g. Microsoft GraphRAG or Neo4j) for deep “who calls what” and “who inherits from what” queries. For now, structure-based chunks + import metadata in Qdrant is the senior-engineer compromise.

**Location:** `src/rag/code_ingestion.py` — `ingest_code_directory()` uses AST-derived chunks and metadata.

---

## 5. Agent Flow (LangGraph)

Agent 1 is a **plan-and-solve** graph with three logical steps:

1. **Planner node** — Reads the user request and produces a plan (e.g. “1. Find actors, 2. Find functional requirements, 3. Find technical constraints”).
2. **Retrieval node** — Uses the RAG retriever (from ingestion) to fetch relevant parent chunks for the current plan step.
3. **Synthesizer node** — Consumes plan + retrieved context and produces the final **ProjectAnalysis** via `.with_structured_output(ProjectAnalysis)`.

**State** should carry at least: `messages`, `plan`, and `final_output` (the ProjectAnalysis when done).

**Location:** `src/agents/agent1/graph.py` — define `StateGraph`, nodes, and edges.

---

## 6. File & Folder Structure

```
gestion-project-agents/
├── .cursor/
│   └── rules/           # Cursor rules (e.g. project-analyzer-agent.mdc)
├── PROJECT_CONTEXT.md   # This file
├── src/
│   ├── agents/
│   │   └── agent1/
│   │       ├── models.py    # Pydantic: Actor, UserStory, TechnicalConstraint, ProjectAnalysis
│   │       └── graph.py     # LangGraph: StateGraph, planner → retrieval → synthesizer
│   └── rag/
│       └── ingestion_advanced.py   # ParentDocumentRetriever, Qdrant, PDF ingestion
├── qdrant_data/        # Local Qdrant persistence (created at runtime)
└── requirements.txt    # Dependencies
```

---

## 7. Conventions for Cursor / Developers

- **Typing:** Use Python type hints everywhere.
- **Structured output:** Always use Pydantic for LLM outputs that must be stored or parsed; no ad-hoc JSON.
- **LangGraph:** Keep State, Nodes, and Graph definition separate and readable.
- **RAG:** Prefer ParentDocumentRetriever over a single chunk size for this use case.
- **Clean code:** Modular, testable functions; constants for chunk sizes, collection names, paths.

---

## 8. Current Phase & Next Steps

- **Done:** Agent 1 (Project Analyzer) end-to-end:
  - Data models (`src/agents/agent1/models.py`), RAG with ParentDocumentRetriever + Qdrant (`src/rag/ingestion_advanced.py`), LangGraph (`src/agents/agent1/graph.py`), run script (`scripts/run_agent1.py`).
  - Groq model: `llama-3.3-70b-versatile` (replaces decommissioned `llama3-70b-8192`). NumPy pinned to `<2` for PyTorch/sentence-transformers.
- **Next:** Polish (optional checkpointer, error handling) or start Agent 2 (Task Allocator).

When implementing or refactoring, keep this context in mind and align new code with the structure and stack above.
