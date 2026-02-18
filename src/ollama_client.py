"""
Ollama HTTP client with:
  - Concurrent batch embedding via ThreadPoolExecutor
  - Exponential-backoff retry for transient failures
  - Streaming text generation
"""
import time
import json
import logging
from typing import Generator, List

import httpx

from .common import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

_MAX_RETRIES  = 3
_RETRY_DELAY  = 2.0   # seconds (doubles on each retry)
_EMBED_TIMEOUT = 180  # seconds per embed call
_GEN_TIMEOUT   = 300  # seconds for full generation


# ── low-level helpers ────────────────────────────────────────────────────────

def _embed_one(text: str, model: str) -> List[float]:
    """Embed a single text with retry."""
    delay = _RETRY_DELAY
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=_EMBED_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise
            logger.warning("Embed attempt %d failed (%s) – retrying in %.1fs", attempt, exc, delay)
            time.sleep(delay)
            delay *= 2


# ── public API ───────────────────────────────────────────────────────────────

def ollama_embed(texts: List[str], model: str) -> List[List[float]]:
    """
    Embed a list of texts concurrently (up to 8 threads).
    Returns embeddings in the same order as the input.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: List[List[float]] = [None] * len(texts)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=8) as pool:
        future_to_idx = {
            pool.submit(_embed_one, text, model): i
            for i, text in enumerate(texts)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()   # propagates exceptions

    return results


def ollama_generate(prompt: str, model: str) -> str:
    """Blocking full-response generation."""
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=_GEN_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def ollama_stream(prompt: str, model: str) -> Generator[str, None, None]:
    """
    Streaming generation – yields text tokens as they arrive.
    Use inside a FastAPI StreamingResponse or print directly.
    """
    with httpx.stream(
        "POST",
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": True},
        timeout=_GEN_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            token = chunk.get("response", "")
            if token:
                yield token
            if chunk.get("done"):
                break


def ollama_health() -> dict:
    """Return {'ok': bool, 'models': [...]} – used by /health endpoint."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {"ok": True, "models": models}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
