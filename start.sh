#!/usr/bin/env bash
# ── Policy RAG Agent – start all services ────────────────────────────────────
# Starts:  FastAPI API  (port 8000)
#          Streamlit UI (port 8501)
#
# Usage:
#   ./start.sh           → starts both, Ctrl-C to stop all
#   ./start.sh api       → API only
#   ./start.sh ui        → UI only
#   NOTE: MCP server is started automatically by Cursor/VS Code – do NOT run it manually
set -euo pipefail

source .venv/bin/activate 2>/dev/null || true

MODE="${1:-all}"

_start_api() {
    echo "[api] Starting FastAPI on http://127.0.0.1:8000 …"
    python -m uvicorn src.rag_api:app --host 127.0.0.1 --port 8000 &
    API_PID=$!
}

_start_ui() {
    echo "[ui]  Starting Streamlit on http://localhost:8501 …"
    python -m streamlit run ui_streamlit.py \
        --server.address 127.0.0.1 \
        --server.port 8501 \
        --browser.gatherUsageStats false &
    UI_PID=$!
}

_wait_api() {
    # Wait until the API is responding (max 30s)
    for i in $(seq 1 30); do
        if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
            echo "[api] Ready ✓"
            return 0
        fi
        sleep 1
    done
    echo "[warn] API did not respond within 30s"
}

cleanup() {
    echo ""
    echo "Shutting down …"
    kill "${API_PID:-}" "${UI_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

case "$MODE" in
    api)
        _start_api
        wait $API_PID
        ;;
    ui)
        _start_ui
        wait $UI_PID
        ;;
    mcp)
        echo "[ERROR] Do not start the MCP server manually."
        echo "        Cursor/VS Code starts it automatically via .vscode/mcp.json"
        echo "        See: https://docs.cursor.com/context/model-context-protocol"
        exit 1
        ;;
    all|*)
        _start_api
        _wait_api
        _start_ui
        echo ""
        echo "  API → http://127.0.0.1:8000"
        echo "  UI  → http://localhost:8501"
        echo "  Press Ctrl-C to stop."
        wait
        ;;
esac
