# Gestion of Project Agents

AI agents for project management: analysis, allocation, review, summarization, risk prediction, and documentation.

## Agents

| Agent | Role | Usage |
|-------|------|--------|
| **1** | Project Analyzer | PDF specs → structured analysis (actors, user stories, constraints, risks). RAG + Pydantic. |
| **2** | Task Allocator | Allocates tasks to developers from Agent 1 output + PostgreSQL `developers`. |
| **3** | Code Reviewer | AST-aware RAG over code → review feedback. |
| **4** | Summary Writer | Summarizes Agent 2/3 outputs. |
| **5** | Risk Predictor | Jira-style analytics (delays, budget, team workload) → risk report, mitigations, alerts. |
| **6** | Documentation Writer | ReAct over codebase → README + API docs, coverage %, obsolete warnings, i18n (EN/FR/ES). |

## Setup

1. **Clone and venv**
   ```bash
   git clone https://github.com/YOUR_USERNAME/gestion-project-agents.git
   cd gestion-project-agents
   python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment**
   - Copy `.env.example` to `.env` and set `GROQ_API_KEY` (get one at [console.groq.com](https://console.groq.com/keys)).

3. **PostgreSQL (Agents 2, 5)**
   ```bash
   docker compose -p agentdata up -d
   python -m src.infrastructure.setup_postgres
   ```

4. **Qdrant (Agent 1 PDF RAG, Agent 3 code RAG, Agent 5 optional RAG)**  
   Uses local `qdrant_data/` by default or set `QDRANT_URL` / `QDRANT_API_KEY` in `.env`.

## Run

```bash
# Agent 1 — analyze a project spec PDF
python scripts/run_agent1.py path/to/spec.pdf

# Agent 2 — allocations (needs Agent 1 output + DB)
python scripts/run_agent2.py

# Agent 3 — code review
python scripts/run_agent3.py path/to/code

# Agent 4 — summary
python scripts/run_agent4.py

# Agent 5 — risk report (DB must be up)
python scripts/run_agent5.py
python scripts/run_agent5.py --rag --pdf path/to/spec.pdf   # with RAG

# Agent 6 — docs (coverage, obsolete, language)
python scripts/run_agent6.py src
python scripts/run_agent6.py src --lang fr
```

Outputs go to `out/` (e.g. `agent1_analysis.json`, `agent5_risk_report.json`, `agent6_docs.json`).

## Tech stack

- **Framework:** LangGraph  
- **LLM:** ChatGroq (Llama 3.3 70B)  
- **Vector DB:** Qdrant  
- **DB:** PostgreSQL (Docker) for developers and Jira-style history  
- **Validation:** Pydantic v2  

See `PROJECT_CONTEXT.md` for full architecture and conventions.
