# What to Install Before Coding — Gestion of Project Agents

Follow these steps on your laptop. Order matters.

---

## 1. Check Python (3.10 or higher)

Open Terminal and run:

```bash
python3 --version
```

You need **3.10, 3.11, or 3.12**. If you see 3.9 or lower (or "command not found"), install Python:

- **macOS (easy):** [python.org/downloads](https://www.python.org/downloads/) — download the macOS installer for 3.11 or 3.12.
- **Or with Homebrew:** `brew install python@3.11`

Check again:

```bash
python3 --version
```

---

## 2. Open the project folder in Terminal

```bash
cd /Users/certideal/gestion-project-agents
```

(Or drag the `gestion-project-agents` folder into Terminal and press Enter.)

---

## 3. Create a virtual environment (recommended)

This keeps project packages separate from the rest of your system.

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

You should see `(.venv)` at the start of your prompt. **You must activate the venv before running `pip install`** — otherwise you may get `command not found: pip`.

Use this same `source .venv/bin/activate` whenever you open a new terminal to work on the project.

---

## 4. Upgrade pip (optional but good)

```bash
pip install --upgrade pip
```

---

## 5. Install project dependencies

With the virtual environment **activated** (step 3), run:

```bash
pip install -r requirements.txt
```

This installs LangChain, LangGraph, Qdrant, HuggingFace embeddings, Groq, Pydantic, PDF support, and related packages. It may take a few minutes the first time (especially `sentence-transformers`).

---

## 6. Get a Groq API key (for the LLM)

We use **Groq** (Llama) as the LLM. You need a free API key:

1. Go to [console.groq.com](https://console.groq.com).
2. Sign up or log in.
3. Open **API Keys** and create a new key.
4. Copy the key (it looks like `gsk_...`).

Create a file named `.env` in the project root (`gestion-project-agents/.env`) and add:

```
GROQ_API_KEY=gsk_your_actual_key_here
```

**Important:** Add `.env` to `.gitignore` so the key is never committed. (We’ll add that when we create the repo.)

---

## 7. (Optional) Install Git

If you plan to use version control:

```bash
git --version
```

If it’s not installed, on macOS you can install Xcode Command Line Tools (includes Git) or run `brew install git`.

---

## Quick checklist

| Step | What | Command / action |
|------|------|-------------------|
| 1 | Python 3.10+ | `python3 --version` |
| 2 | Go to project | `cd /Users/certideal/gestion-project-agents` |
| 3 | Virtual env | `python3 -m venv .venv` then `source .venv/activate` |
| 4 | Upgrade pip | `pip install --upgrade pip` |
| 5 | Install deps | `pip install -r requirements.txt` |
| 6 | Groq key | Create at console.groq.com → put in `.env` as `GROQ_API_KEY=...` |
| 7 | (Optional) Git | `git --version` or install |

---

## Verify installation

With `.venv` activated, run:

```bash
python3 -c "
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_groq import ChatGroq
from pydantic import BaseModel
print('All core imports OK')
"
```

If you see **`All core imports OK`**, you’re ready to start coding.

If you see an error, copy the full message and we can fix it.
