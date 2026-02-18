"""
FastAPI application – Policy RAG API.

Endpoints:
  POST /query          – blocking RAG query (JSON response)
  POST /query/stream   – streaming RAG query (text/event-stream)
  GET  /health         – checks API + Ollama health
  POST /reindex        – re-build the ChromaDB index from raw_docs
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .rag_core import query_rag, query_rag_stream
from .ollama_client import ollama_health
from .common import API_HOST, API_PORT

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Policy & Procedure RAG Agent",
    description="Local RAG over IT policy documents using Ollama + ChromaDB.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class Turn(BaseModel):
    role: str    # "user" | "assistant"
    content: str

class QueryIn(BaseModel):
    question: str
    history: Optional[List[Turn]] = None

class ReindexResponse(BaseModel):
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
def health():
    ollama = ollama_health()
    return {
        "api":    "ok",
        "ollama": ollama,
    }


@app.post("/query", tags=["rag"])
def query(req: QueryIn):
    try:
        history = [t.model_dump() for t in req.history] if req.history else None
        return query_rag(req.question, history=history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query/stream", tags=["rag"])
def query_stream(req: QueryIn):
    """
    Server-sent events (SSE) streaming endpoint.
    Each token is sent as:  data: <token>\n\n
    Terminated with:        data: [DONE]\n\n
    """
    history = [t.model_dump() for t in req.history] if req.history else None

    def _event_stream():
        try:
            for token in query_rag_stream(req.question, history=history):
                # SSE format
                yield f"data: {token}\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@app.post("/reindex", tags=["ops"])
def reindex():
    """Trigger a full re-index of documents in data/raw_docs."""
    try:
        from .build_index import main as _build
        _build()
        return ReindexResponse(status="ok", message="Index rebuilt successfully.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Entry point for `rag-serve` script ───────────────────────────────────────

def serve():
    import uvicorn
    uvicorn.run(
        "src.rag_api:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    serve()
