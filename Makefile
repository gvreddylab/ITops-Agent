# ── Policy RAG Agent – convenience commands ───────────────────────────────────
# Usage: make <target>
# Requires: Ollama running  |  pip install -e .

PYTHON := python
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.PHONY: help install install-dev index serve ui mcp all clean

help:
	@echo ""
	@echo "  make install     Install all dependencies into .venv"
	@echo "  make index       Build / rebuild the ChromaDB vector index"
	@echo "  make serve       Start the FastAPI server  (port 8000)"
	@echo "  make ui          Start the Streamlit UI    (port 8501)"
	@echo "  make mcp         Start the MCP stdio server for IDE integration"
	@echo "  make all         index → serve (foreground)"
	@echo "  make clean       Remove __pycache__ and .pyc files"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	@echo ""
	@echo "✅  Dependencies installed."
	@echo "   Copy .env.example → .env and adjust settings if needed."

# ── Core commands ─────────────────────────────────────────────────────────────
index:
	$(PY) -m src.build_index

serve:
	$(PY) -m uvicorn src.rag_api:app --host 127.0.0.1 --port 8000

ui:
	$(PY) -m streamlit run ui_streamlit.py

mcp:
	$(PY) -m src.mcp_server

# ── Compound ──────────────────────────────────────────────────────────────────
all: index serve

# ── Housekeeping ──────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -not -path './.venv/*' -delete 2>/dev/null; true
	@echo "🧹  Cleaned."
