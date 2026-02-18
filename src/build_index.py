"""
Build (or rebuild) the ChromaDB vector index from raw_docs.

Improvements over v1:
  - Concurrent embedding (ThreadPoolExecutor via ollama_client)
  - Progress display with percentages
  - Graceful per-chunk error handling
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import chromadb
from chromadb.config import Settings

from .common import DOCS_DIR, CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL
from .loaders import load_docs
from .chunking import chunk_text
from .ollama_client import ollama_embed


_EMBED_WORKERS = 8   # concurrent embedding threads


def main():
    if not DOCS_DIR.exists():
        sys.exit(f"[ERROR] Docs folder not found: {DOCS_DIR}")

    # ── Load & chunk ──────────────────────────────────────────────────────────
    docs = load_docs(DOCS_DIR)
    print(f"[INFO] Loaded {len(docs)} document(s) from {DOCS_DIR}")

    all_texts, all_metas, all_ids = [], [], []
    for doc_text, meta in docs:
        for c_text, c_meta in chunk_text(doc_text, meta):
            all_texts.append(c_text)
            all_metas.append(c_meta)
            all_ids.append(f"{meta['source_file']}::chunk::{c_meta['chunk_id']}")

    total = len(all_texts)
    print(f"[INFO] {total} chunks created. Embedding with {_EMBED_WORKERS} workers …")

    # ── Concurrent embedding ──────────────────────────────────────────────────
    embeddings: list = [None] * total
    failed_indices:  set[int] = set()

    with ThreadPoolExecutor(max_workers=_EMBED_WORKERS) as pool:
        future_map = {
            pool.submit(ollama_embed, [all_texts[i]], EMBED_MODEL): i
            for i in range(total)
        }
        done = 0
        for future in as_completed(future_map):
            idx  = future_map[future]
            done += 1
            pct  = int(done / total * 100)
            try:
                embeddings[idx] = future.result()[0]
            except Exception as exc:
                failed_indices.add(idx)
                preview = all_texts[idx][:120].replace("\n", " ")
                print(f"\r[WARN] chunk {idx} failed: {exc}\n       Preview: {preview}")
            print(f"\r[INFO] Embedded {done}/{total} ({pct}%) …", end="", flush=True)

    print()   # newline after progress line

    # ── Build ChromaDB collection ─────────────────────────────────────────────
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    col = client.create_collection(COLLECTION_NAME)

    ok_ids    = [all_ids[i]    for i in range(total) if i not in failed_indices]
    ok_texts  = [all_texts[i]  for i in range(total) if i not in failed_indices]
    ok_metas  = [all_metas[i]  for i in range(total) if i not in failed_indices]
    ok_vecs   = [embeddings[i] for i in range(total) if i not in failed_indices]

    # Upsert in batches of 100
    BATCH = 100
    for i in range(0, len(ok_ids), BATCH):
        col.add(
            ids=ok_ids[i: i + BATCH],
            documents=ok_texts[i: i + BATCH],
            metadatas=ok_metas[i: i + BATCH],
            embeddings=ok_vecs[i: i + BATCH],
        )

    print(f"[OK] Indexed {len(ok_ids)}/{total} chunks (skipped: {len(failed_indices)})")
    print(f"[OK] Chroma index: {CHROMA_DIR}")
    print(f"[OK] Collection  : {COLLECTION_NAME}")


if __name__ == "__main__":
    main()
