"""
RAG orchestration core.

Improvements over v1:
  - Module-level ChromaDB singleton (no reconnect per query)
  - Distance-threshold filtering (drops low-relevance chunks)
  - Conversation history injected into prompt (multi-turn coherence)
  - Streaming-ready: query_rag_stream() yields tokens
  - Cleaner, more structured system prompt
"""
from __future__ import annotations

import re
from typing import Any, Dict, Generator, List, Optional, Tuple

import chromadb
from chromadb.config import Settings

from .common import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBED_MODEL,
    CHAT_MODEL,
    TOP_K,
    CONTEXT_CHUNKS_TO_LLM,
    DISTANCE_THRESHOLD,
)
from .ollama_client import ollama_embed, ollama_generate, ollama_stream
from .checklists import load_checklist
from .incident_helper import detect_incident_intent, extract_incident_fields


# ── ChromaDB singleton ────────────────────────────────────────────────────────

_chroma_client: Optional[chromadb.PersistentClient] = None


def _get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an IT Policies & Procedures Assistant for the organisation's IT team.

═══ STRICT RULES ════════════════════════════════════════════════════════════
1. Answer ONLY using the CONTEXT provided below. Never use outside knowledge.
2. If the answer is not in CONTEXT, say exactly:
   "Not found in the provided procedures/policies."
3. Answer ONLY what the user asked. Do not add unrequested sections.

═══ CITATIONS ═══════════════════════════════════════════════════════════════
• Every factual claim MUST include an inline citation in this exact format:
  [SOURCE: filename.ext | chunk_id=N]
• Do NOT cite sources you did not use.

═══ INCIDENT / GOVERNANCE SAFETY ════════════════════════════════════════════
• If missing_details is not empty, do NOT finalise severity, priority, or
  regulatory notifications. Instead explain what the policy requires and ask
  the next clarifying questions.
• Do NOT invent regulatory notifications. Mention notifying SAMA only when
  the CONTEXT explicitly states the condition – and include the citation.
• Present conditional actions as: "If Sev1, then …"
"""


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    question: str,
    contexts: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    interactive_mode: bool = False,
    next_questions: Optional[List[Dict[str, str]]] = None,
) -> str:
    # Context block
    ctx_parts = []
    for c in contexts:
        meta = c["meta"]
        ctx_parts.append(
            f"[SOURCE: {meta.get('source_file')} | chunk_id={meta.get('chunk_id')}]\n{c['text']}"
        )
    context_block = "\n\n---\n\n".join(ctx_parts)

    # Conversation history block
    history_block = ""
    if history:
        lines = []
        for turn in history:
            role = turn.get("role", "user").upper()
            lines.append(f"{role}: {turn['content']}")
        history_block = "\n\nCONVERSATION HISTORY (for context only – do not answer old turns):\n" + "\n".join(lines)

    # Interactive mode extra instructions
    interactive_block = ""
    if interactive_mode and next_questions:
        qs = "\n".join(f"  - {q['question']}" for q in next_questions)
        interactive_block = (
            "\n\nIMPORTANT – missing_details exist:\n"
            "• Do NOT assume or decide severity/priority/regulatory actions.\n"
            "• End your response by asking these questions verbatim:\n" + qs
        )

    return (
        f"{_SYSTEM_PROMPT}"
        f"{history_block}\n\n"
        f"CONTEXT:\n\n{context_block}\n\n"
        f"USER QUESTION:\n{question}"
        f"{interactive_block}\n\n"
        "Return your answer now."
    )


# ── Citation helpers ──────────────────────────────────────────────────────────

def _parse_citations(answer: str) -> set[tuple[str, int]]:
    used: set[tuple[str, int]] = set()
    for m in re.finditer(r"\[SOURCE:\s*(.*?)\s*\|\s*chunk_id\s*=\s*(\d+)\]", answer):
        used.add((m.group(1).strip(), int(m.group(2))))
    return used


def _build_citation_list(
    contexts: List[Dict[str, Any]],
    used: set[tuple[str, int]],
    fallback: bool = False,
) -> List[Dict[str, Any]]:
    out = []
    for c in contexts:
        sf  = c["meta"].get("source_file")
        cid = int(c["meta"].get("chunk_id"))
        if fallback or (sf, cid) in used:
            out.append({
                "source_file": sf,
                "chunk_id":    cid,
                "snippet":     c["text"][:200].replace("\n", " ").strip(),
            })
    return out


# ── Incident helper ───────────────────────────────────────────────────────────

def _incident_details(question: str) -> Tuple[List[Dict], List[Dict]]:
    try:
        if not detect_incident_intent(question):
            return [], []
        checklist = load_checklist("incident")
        required = checklist.get("required_fields", {})
        if isinstance(required, list):
            required = {f: f"Please provide: {f}" for f in required}
        provided = extract_incident_fields(question)
        missing = [
            {"field": field, "question": q}
            for field, q in required.items()
            if field not in provided
        ]
        return missing, missing[:3]
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("incident_details failed: %s", exc)
        return [], []


# ── Retrieval ─────────────────────────────────────────────────────────────────

def _retrieve(question: str) -> List[Dict[str, Any]]:
    """Embed query → ChromaDB search → filter + dedupe."""
    q_vec = ollama_embed([question], model=EMBED_MODEL)[0]
    col   = _get_chroma().get_collection(COLLECTION_NAME)

    res  = col.query(
        query_embeddings=[q_vec],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )
    docs  = res.get("documents",  [[]])[0]
    metas = res.get("metadatas",  [[]])[0]
    dists = res.get("distances",  [[]])[0]

    hits: List[Dict[str, Any]] = []
    seen: set = set()
    for text, meta, dist in zip(docs, metas, dists):
        if not text or not text.strip():
            continue
        if dist > DISTANCE_THRESHOLD:
            continue                          # drop low-relevance chunks
        key = (meta.get("source_file"), meta.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        hits.append({"text": text, "meta": meta, "distance": dist})

    # Sort by distance (ascending = most similar first)
    hits.sort(key=lambda h: h["distance"])
    return hits


# ── Public query functions ────────────────────────────────────────────────────

def query_rag(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Full blocking RAG query. Returns structured dict."""
    missing, next_qs  = _incident_details(question)
    interactive       = bool(missing)

    hits     = _retrieve(question)
    contexts = hits[:CONTEXT_CHUNKS_TO_LLM]

    prompt = _build_prompt(
        question=question,
        contexts=contexts,
        history=history,
        interactive_mode=interactive,
        next_questions=next_qs,
    )
    answer = ollama_generate(prompt, model=CHAT_MODEL).strip()

    used      = _parse_citations(answer)
    citations = _build_citation_list(contexts, used, fallback=not used)

    return {
        "answer":          answer,
        "citations":       citations,
        "missing_details": missing,
        "next_questions":  next_qs,
        "retrieved": [
            {
                "source_file": h["meta"].get("source_file"),
                "chunk_id":    int(h["meta"].get("chunk_id")),
                "distance":    round(h["distance"], 4),
            }
            for h in hits
        ],
    }


def query_rag_stream(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Generator[str, None, None]:
    """
    Streaming variant – yields LLM tokens as they arrive.
    Suitable for FastAPI StreamingResponse / SSE.
    """
    missing, next_qs = _incident_details(question)
    hits     = _retrieve(question)
    contexts = hits[:CONTEXT_CHUNKS_TO_LLM]

    prompt = _build_prompt(
        question=question,
        contexts=contexts,
        history=history,
        interactive_mode=bool(missing),
        next_questions=next_qs,
    )
    yield from ollama_stream(prompt, model=CHAT_MODEL)
