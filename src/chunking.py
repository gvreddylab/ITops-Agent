"""
Sentence-aware token chunking.

Strategy:
  1. Split the raw text into sentences (simple regex – no NLTK download needed).
  2. Greedily accumulate sentences until the token budget is reached.
  3. Slide the window back by CHUNK_OVERLAP tokens for each new chunk.

This guarantees that no sentence is ever split in the middle, which is
critical for preserving policy rules and numbered requirements.
"""
import re
from typing import Dict, List, Tuple

import tiktoken

from .common import CHUNK_TOKENS, CHUNK_OVERLAP

_ENC = tiktoken.get_encoding("cl100k_base")


def _sentence_split(text: str) -> List[str]:
    """
    Split on sentence-ending punctuation followed by whitespace or newline.
    Also preserve paragraph breaks as natural sentence boundaries.
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split on ". / ! / ?" followed by whitespace/newline, or on blank lines
    parts = re.split(r'(?<=[.!?])\s+|\n{2,}', text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, base_meta: Dict) -> List[Tuple[str, Dict]]:
    """
    Token-budgeted, sentence-aware chunking.
    Returns list of (chunk_text, metadata) pairs.
    """
    sentences   = _sentence_split(text)
    sent_tokens = [_ENC.encode(s) for s in sentences]

    chunks: List[Tuple[str, Dict]] = []
    chunk_id  = 0
    start_tok = 0   # absolute token offset into the flattened token stream
    buf_sents: List[int] = []   # sentence indices in current buffer
    buf_len   = 0               # current buffer size in tokens

    def _flush(buf_sents: List[int], chunk_id: int, start_tok: int):
        tokens_combined = []
        for si in buf_sents:
            tokens_combined.extend(sent_tokens[si])
        chunk_str = _ENC.decode(tokens_combined).strip()
        if not chunk_str:
            return None
        meta = dict(base_meta)
        meta["chunk_id"]          = chunk_id
        meta["chunk_token_start"] = start_tok
        meta["chunk_token_end"]   = start_tok + len(tokens_combined)
        return chunk_str, meta

    i = 0
    while i < len(sentences):
        s_len = len(sent_tokens[i])

        # Edge case: single sentence exceeds CHUNK_TOKENS → hard-split it
        if s_len > CHUNK_TOKENS:
            # Flush whatever is in the buffer first
            if buf_sents:
                result = _flush(buf_sents, chunk_id, start_tok)
                if result:
                    chunks.append(result)
                    chunk_id += 1
                start_tok += buf_len
                buf_sents, buf_len = [], 0

            # Hard-split the oversized sentence into token windows
            toks = sent_tokens[i]
            offset = 0
            while offset < len(toks):
                window = toks[offset: offset + CHUNK_TOKENS]
                chunk_str = _ENC.decode(window).strip()
                if chunk_str:
                    meta = dict(base_meta)
                    meta["chunk_id"]          = chunk_id
                    meta["chunk_token_start"] = start_tok + offset
                    meta["chunk_token_end"]   = start_tok + offset + len(window)
                    chunks.append((chunk_str, meta))
                    chunk_id += 1
                offset = max(0, offset + CHUNK_TOKENS - CHUNK_OVERLAP)
            start_tok += len(toks)
            i += 1
            continue

        # Normal path: accumulate sentences
        if buf_len + s_len > CHUNK_TOKENS and buf_sents:
            # Flush current chunk
            result = _flush(buf_sents, chunk_id, start_tok)
            if result:
                chunks.append(result)
                chunk_id += 1

            # Compute overlap: keep trailing sentences whose tokens ≤ CHUNK_OVERLAP
            overlap_sents: List[int] = []
            overlap_len = 0
            for si in reversed(buf_sents):
                if overlap_len + len(sent_tokens[si]) <= CHUNK_OVERLAP:
                    overlap_sents.insert(0, si)
                    overlap_len += len(sent_tokens[si])
                else:
                    break

            start_tok += buf_len - overlap_len
            buf_sents = overlap_sents
            buf_len   = overlap_len

        buf_sents.append(i)
        buf_len += s_len
        i += 1

    # Flush remaining buffer
    if buf_sents:
        result = _flush(buf_sents, chunk_id, start_tok)
        if result:
            chunks.append(result)

    return chunks
