#!/usr/bin/env bash
# ── Policy RAG Agent – one-shot setup ────────────────────────────────────────
# Run this once on any machine to install, pull models, and build the index.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
#
# Requirements (install via command prompt first):
#   - Python 3.10+
#   - Ollama  (https://ollama.ai)
set -euo pipefail

YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()  { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── 1. Python check ───────────────────────────────────────────────────────────
log "Checking Python …"
python3 --version || die "Python 3 not found. Install Python 3.10+ and add it to PATH."

# ── 2. Virtual environment ────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    log "Creating virtual environment …"
    python3 -m venv .venv
fi

source .venv/bin/activate
log "Virtual environment active: $(which python)"

# ── 3. Install dependencies ───────────────────────────────────────────────────
log "Installing Python dependencies …"
pip install --upgrade pip -q
pip install -e . -q
# sseclient-py for streaming in Streamlit UI
pip install sseclient-py -q

# ── 4. .env file ──────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env created from .env.example – edit it to customise models/settings."
fi

# ── 5. Ollama check ───────────────────────────────────────────────────────────
log "Checking Ollama …"
if ! command -v ollama &>/dev/null; then
    die "Ollama not found.\nInstall from https://ollama.ai and re-run this script."
fi

log "Pulling embedding model: nomic-embed-text"
ollama pull nomic-embed-text

CHAT_MODEL="${CHAT_MODEL:-llama3.1:8b}"
log "Pulling chat model: ${CHAT_MODEL}"
ollama pull "${CHAT_MODEL}"

# ── 6. Build index ────────────────────────────────────────────────────────────
log "Building ChromaDB vector index …"
python -m src.build_index

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup complete! Start the system:           ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  ./start.sh          (API + UI together)     ║${NC}"
echo -e "${GREEN}║  make serve          (API only)              ║${NC}"
echo -e "${GREEN}║  make ui             (Streamlit UI only)     ║${NC}"
echo -e "${GREEN}║  make mcp            (MCP server for IDE)    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
