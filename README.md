# ITops Assistant — Local AI Policy & Procedures Agent

> **A fully local, private AI assistant that answers questions from your IT policy documents — no cloud, no data leakage, no subscriptions.**

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [Why Does This Matter?](#2-why-does-this-matter)
3. [How It Works — Architecture](#3-how-it-works--architecture)
4. [Tools Used & Why](#4-tools-used--why)
5. [Prerequisites — Install Once](#5-prerequisites--install-once)
6. [Project Structure](#6-project-structure)
7. [Step-by-Step: First-Time Setup](#7-step-by-step-first-time-setup)
8. [Step-by-Step: Daily Use](#8-step-by-step-daily-use)
9. [Adding New Policy Documents](#9-adding-new-policy-documents)
10. [Cursor IDE Integration (MCP)](#10-cursor-ide-integration-mcp)
11. [API Reference](#11-api-reference)
12. [Configuration Reference](#12-configuration-reference)
13. [Troubleshooting](#13-troubleshooting)
14. [Who Benefits & How](#14-who-benefits--how)

---

## 1. What Is This?

**ITops Assistant** is a **Retrieval-Augmented Generation (RAG)** agent that runs entirely on your local machine. You give it your organisation's IT policy and procedure documents (Word/PDF), and it becomes an intelligent assistant that can:

- Answer precise questions like *"What is the process for raising a Sev1 incident?"*
- Guide staff through incident reporting step by step
- Cite the exact document and section it sourced the answer from
- Detect missing information and ask follow-up questions
- Work inside your IDE (Cursor) as an AI tool

**Everything runs locally** — your documents never leave your machine.

---

## 2. Why Does This Matter?

### The Problem

IT teams maintain dozens of policy documents. In practice:

- Staff don't read them until something goes wrong
- Finding the right section takes too long during an incident
- New joiners don't know what procedures exist
- Compliance audits require proof that policies are followed

### The Solution

This assistant makes policies **instantly queryable** in plain English. Instead of searching a SharePoint folder, a staff member types:

> *"How do I raise a critical incident for a payment system outage?"*

And gets a step-by-step answer with citations — in seconds.

### Why Local AI?

| Concern | This System |
|---|---|
| Sensitive policy data | Never leaves your machine |
| Subscription cost | Zero — fully open source |
| Internet dependency | Works offline |
| Data sovereignty / SAMA compliance | Fully controlled |

---

## 3. How It Works — Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ITops Assistant                          │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────┐  │
│  │ Policy Docs  │───▶│  Build Index    │───▶│   ChromaDB    │  │
│  │ (.docx/.pdf) │    │  (chunking +    │    │ (vector store)│  │
│  └──────────────┘    │   embedding)    │    └───────┬───────┘  │
│                      └─────────────────┘            │          │
│                                                      │ retrieve │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────▼───────┐  │
│  │  User Query  │───▶│   FastAPI RAG   │◀───│  Ollama LLM   │  │
│  │ (UI or IDE)  │    │   Orchestrator  │    │  llama3.1:8b  │  │
│  └──────────────┘    └────────┬────────┘    └───────────────┘  │
│                               │                                 │
│              ┌────────────────┼────────────────┐               │
│              ▼                ▼                 ▼               │
│       Streamlit UI       MCP Server       REST API             │
│       (Browser)         (Cursor IDE)    (port 8000)            │
└─────────────────────────────────────────────────────────────────┘
```

**Query flow:**
1. User asks a question (UI, API, or IDE)
2. The question is embedded into a vector using `nomic-embed-text`
3. ChromaDB finds the most relevant policy chunks by vector similarity
4. Low-relevance chunks are filtered out by distance threshold
5. The top chunks + conversation history are sent to `llama3.1:8b` as context
6. The LLM generates a grounded answer with citations
7. The response is returned with citations and any missing incident details

---

## 4. Tools Used & Why

| Tool | Role | Why This Tool |
|---|---|---|
| **Ollama** | Runs LLMs locally | Single binary, no Docker, runs on CPU or GPU, free |
| **llama3.1:8b** | Chat / reasoning model | Strong instruction-following, fits in 8 GB RAM |
| **nomic-embed-text** | Text embedding model | High-quality embeddings, lightweight (274 MB), fast |
| **ChromaDB** | Vector database | No server needed, persists to disk, pure Python |
| **FastAPI** | REST API layer | Fast, async, auto-generates API docs at `/docs` |
| **Streamlit** | Web chat UI | No frontend code required, instant browser UI |
| **MCP** | IDE integration protocol | Exposes the RAG agent as a native Cursor AI tool |
| **tiktoken** | Token counting | Accurate chunking aligned to LLM token budgets |
| **python-dotenv** | Config management | All settings via `.env` — no code changes needed |
| **httpx** | HTTP client | Async-capable, used for streaming Ollama responses |

### Why RAG and not just uploading to ChatGPT?

- **Privacy** — your policies may contain internal procedures, system names, compliance data
- **Accuracy** — the LLM is constrained to only use your documents; it cannot hallucinate from general knowledge
- **Citations** — every answer references the exact source document and chunk
- **Cost** — zero per-query cost after setup

---

## 5. Prerequisites — Install Once

These are installed once at the OS / machine level. The project itself handles the rest.

### 5.1 Python 3.10 or higher

**Windows / WSL:**
```bash
python3 --version   # must show 3.10+
```
If not installed: [python.org/downloads](https://www.python.org/downloads/)

### 5.2 Ollama

Ollama is the local LLM runtime.

**Linux / WSL:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:** Download the installer from [ollama.ai](https://ollama.ai)

After installing, start Ollama (it runs in the background):
```bash
ollama serve   # or it starts automatically on macOS/Windows
```

---

## 6. Project Structure

```
policy-rag-agent/
│
├── data/
│   └── raw_docs/               ← PUT YOUR POLICY DOCUMENTS HERE (.docx / .pdf)
│       ├── (your policy documents go here)
│       └── (not committed to git — see .gitignore)
│
├── index/                      ← ChromaDB vector index (auto-generated)
│
├── checklists/
│   └── incident.yaml           ← Required fields for incident queries
│
├── src/
│   ├── common.py               ← Central config (reads from .env)
│   ├── loaders.py              ← PDF and DOCX document loaders
│   ├── chunking.py             ← Sentence-aware text chunking
│   ├── ollama_client.py        ← Ollama HTTP client (embed + generate)
│   ├── build_index.py          ← Index builder (run once, or after new docs)
│   ├── rag_core.py             ← RAG orchestration logic
│   ├── rag_api.py              ← FastAPI application
│   ├── mcp_server.py           ← MCP server for Cursor / VS Code
│   ├── checklists.py           ← Checklist loader
│   └── incident_helper.py      ← Incident intent detection
│
├── ui_streamlit.py             ← Streamlit chat UI
├── .env                        ← Your local config (not committed to git)
├── .env.example                ← Config template (committed to git)
├── requirements.txt            ← Python dependencies
├── pyproject.toml              ← Package definition
├── Makefile                    ← Convenience commands
├── setup.sh                    ← First-time setup script
└── start.sh                    ← Start API + UI
```

---

## 7. Step-by-Step: First-Time Setup

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd policy-rag-agent
```

### Step 2 — Pull the AI models

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

> `nomic-embed-text` is 274 MB. `llama3.1:8b` is 4.9 GB. Download once, reused forever.

You can verify they are ready:
```bash
ollama list
```
Expected output:
```
NAME                       SIZE
llama3.1:8b                4.9 GB
nomic-embed-text:latest    274 MB
```

### Step 3 — Create the Python virtual environment and install dependencies

```bash
python3 -m venv .venv

# Linux / macOS / WSL:
source .venv/bin/activate

# Windows Command Prompt:
.venv\Scripts\activate.bat

pip install -e .
```

### Step 4 — Configure environment

```bash
cp .env.example .env
```

The defaults work out of the box. Open `.env` only if you want to change models or ports:

```env
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
CHAT_MODEL=llama3.1:8b
API_HOST=127.0.0.1
API_PORT=8000
```

### Step 5 — Add your policy documents

Copy your `.docx` or `.pdf` files into:
```
data/raw_docs/
```

> Supported formats: `.pdf`, `.docx`, `.doc`

### Step 6 — Build the vector index

```bash
python -m src.build_index
```

This reads all documents, splits them into overlapping chunks, embeds each chunk using `nomic-embed-text`, and saves the vectors to ChromaDB.

Expected output:
```
[INFO] Loaded 6 document(s) from data/raw_docs
[INFO] 312 chunks created. Embedding with 8 workers …
[INFO] Embedded 312/312 (100%) …
[OK] Indexed 312/312 chunks (skipped: 0)
[OK] Chroma index: /path/to/index
```

> Re-run this command any time you add or update documents.

---

## 8. Step-by-Step: Daily Use

### Start the system

```bash
./start.sh
```

This starts:
- **FastAPI** on `http://127.0.0.1:8000`
- **Streamlit UI** on `http://localhost:8501`

Keep this terminal open. Press `Ctrl+C` to stop.

### Open the chat UI

Open your browser and go to:
```
http://localhost:8501
```

You'll see the **ITops Assistant** chat interface.

### Example questions to try

```
What is the incident severity classification criteria?
```
```
How do I raise a Sev1 incident for a core banking outage?
```
```
What are the backup retention requirements?
```
```
What are the steps for change management approval?
```
```
What KPIs are tracked for IT infrastructure?
```

### Streaming vs Blocking

Toggle **"Streaming response"** in the sidebar:
- **On** (default) — tokens appear word by word as the LLM generates them
- **Off** — waits for the full answer then displays it

### Health check

To verify the API and Ollama are running:
```bash
curl http://127.0.0.1:8000/health
```
```json
{
  "api": "ok",
  "ollama": {
    "ok": true,
    "models": ["llama3.1:8b", "nomic-embed-text:latest"]
  }
}
```

---

## 9. Adding New Policy Documents

1. Copy the new `.docx` or `.pdf` file into `data/raw_docs/`
2. Rebuild the index:
   ```bash
   python -m src.build_index
   ```
3. Restart the API:
   ```bash
   ./start.sh
   ```

That's it. The new document is now searchable.

You can also trigger a reindex without restarting via the API:
```bash
curl -X POST http://127.0.0.1:8000/reindex
```

---

## 10. Cursor IDE Integration (MCP)

**MCP (Model Context Protocol)** lets Cursor's AI chat call your local RAG agent as a tool — directly inside the IDE without switching windows.

### Setup (one time)

Add the `policy-rag` entry to `~/.cursor/mcp.json` (create the file if it does not exist).
Replace the paths with your actual machine paths:

```json
{
  "mcpServers": {
    "policy-rag": {
      "command": "/ABSOLUTE/PATH/TO/policy-rag-agent/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/ABSOLUTE/PATH/TO/policy-rag-agent"
    }
  }
}
```

To find your absolute path:
```bash
pwd   # run this inside the project folder
```

### Enable in Cursor

1. Open Cursor
2. Go to `Cursor Settings` → `MCP` tab
3. You will see **policy-rag** listed — toggle it **ON**
4. A green dot confirms it is connected

> **Important:** The FastAPI server (`./start.sh`) must be running for query results to work.

### Use it in Cursor AI chat

In any Cursor chat window, just ask normally:
```
What is the escalation path for a Sev2 incident?
```

Cursor will automatically invoke `query_policies`, retrieve from your local ChromaDB, and return an answer grounded in your policy documents — with citations.

### Available MCP tools

| Tool | Description |
|---|---|
| `query_policies` | Ask any question about your IT policies |
| `check_ollama_health` | Verify Ollama is running and list available models |

---

## 11. API Reference

The FastAPI server auto-generates interactive docs at:
```
http://127.0.0.1:8000/docs
```

### POST `/query` — Ask a question

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the RTO for critical systems?"}'
```

**Response:**
```json
{
  "answer": "According to the Backup Recovery policy, the RTO for critical systems is 4 hours [SOURCE: Backup Recovery.docx | chunk_id=7].",
  "citations": [
    {
      "source_file": "Backup Recovery.docx",
      "chunk_id": 7,
      "snippet": "Critical systems must be restored within 4 hours..."
    }
  ],
  "missing_details": [],
  "next_questions": [],
  "retrieved": [...]
}
```

### POST `/query/stream` — Streaming response

```bash
curl -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the change approval process?"}' \
  --no-buffer
```

Tokens stream as Server-Sent Events:
```
data: According
data:  to
data:  the
data:  Change
...
data: [DONE]
```

### POST `/query` — With conversation history

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What about for low priority changes?",
    "history": [
      {"role": "user", "content": "What is the change approval process?"},
      {"role": "assistant", "content": "High priority changes require CAB approval..."}
    ]
  }'
```

### GET `/health` — Health check

```bash
curl http://127.0.0.1:8000/health
```

### POST `/reindex` — Rebuild the index

```bash
curl -X POST http://127.0.0.1:8000/reindex
```

---

## 12. Configuration Reference

All settings are in `.env`. Copy `.env.example` to `.env` to get started.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server address |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `CHAT_MODEL` | `llama3.1:8b` | Chat/generation model name |
| `CHUNK_TOKENS` | `700` | Max tokens per document chunk |
| `CHUNK_OVERLAP` | `120` | Token overlap between adjacent chunks |
| `TOP_K` | `12` | Chunks retrieved from ChromaDB per query |
| `CONTEXT_CHUNKS_TO_LLM` | `6` | Top chunks actually sent to the LLM |
| `DISTANCE_THRESHOLD` | `1.2` | Max vector distance — higher values are dropped |
| `API_HOST` | `127.0.0.1` | FastAPI bind address |
| `API_PORT` | `8000` | FastAPI port |
| `HISTORY_TURNS` | `4` | Prior conversation turns included in LLM context |

### Tuning tips

| Goal | Change |
|---|---|
| More accurate, narrower answers | Lower `DISTANCE_THRESHOLD` to `0.9` |
| Broader answers across more docs | Raise `CONTEXT_CHUNKS_TO_LLM` to `8` |
| Faster responses (less context) | Lower `CONTEXT_CHUNKS_TO_LLM` to `4` |
| Larger documents / more detail | Raise `CHUNK_TOKENS` to `1000`, rebuild index |
| Use a different model | Change `CHAT_MODEL`, run `ollama pull <model>` first |

---

## 13. Troubleshooting

### "Ollama not running" / connection refused

```bash
# Start Ollama manually
ollama serve
```

### "Collection not found" error

The index has not been built yet. Run:
```bash
python -m src.build_index
```

### Streamlit UI shows "API error"

Make sure the FastAPI server is running:
```bash
./start.sh api
# or
python -m uvicorn src.rag_api:app --host 127.0.0.1 --port 8000
```

### MCP not appearing in Cursor

1. Check `~/.cursor/mcp.json` exists and contains the `policy-rag` entry
2. Verify the Python path is correct:
   ```bash
   ls /home/$USER/projects/policy-rag-agent/.venv/bin/python
   ```
3. Reload Cursor: `Ctrl+Shift+P` → `Reload Window`

### Answer quality is poor / "Not found in policies"

- The document may not be indexed — check it is in `data/raw_docs/` and re-run `python -m src.build_index`
- The query may be too vague — try including specific terms from the policy (e.g., "Sev1", "RTO", "CAB")
- Lower `DISTANCE_THRESHOLD` to `0.8` in `.env` to require stricter relevance

### Slow responses

- First query after startup is slower (model warm-up) — subsequent queries are faster
- On CPU-only machines, `llama3.1:8b` generates ~5–10 tokens/sec — this is normal
- To use a smaller/faster model: `CHAT_MODEL=llama3.2:3b` in `.env` and `ollama pull llama3.2:3b`

---

## 14. Who Benefits & How

### IT Operations Staff
- Instantly find the correct procedure during an incident without searching documents
- Guided step-by-step incident raising with automatic detection of missing information
- Reduces mean time to resolution (MTTR) by eliminating policy lookup delays

### IT Managers & Team Leads
- Staff self-service reduces repetitive policy questions
- Consistent, citation-backed answers ensure procedures are followed correctly
- Audit-ready: every answer cites the exact source document

### Compliance & Governance Teams
- Demonstrates that policies are accessible and actionable
- Supports SAMA IT Governance Framework adherence
- Documents are the single source of truth — the AI cannot invent rules

### New Joiners / Onboarding
- Learn organisational procedures by asking natural language questions
- No need to read 60-page documents to find one answer
- Safe to ask "basic" questions without bothering a senior colleague

### Developers (via MCP / API)
- Integrate policy Q&A into any internal tool via the REST API
- Use it inside Cursor IDE while writing runbooks or incident tickets
- Build on top of it: the API is fully documented at `/docs`

---

## Makefile Quick Reference

```bash
make install    # Create venv and install all dependencies
make index      # Build / rebuild the ChromaDB vector index
make serve      # Start FastAPI server (port 8000)
make ui         # Start Streamlit UI (port 8501)
make clean      # Remove __pycache__ files
```

---

## License

Internal use. Not for public distribution without approval.

---

*Built with Ollama · nomic-embed-text · ChromaDB · FastAPI · Streamlit · MCP*
