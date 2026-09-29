"""Token-aware packing of Markdown blocks into retrieval chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

from .parse import Block

# cl100k_base is the tokenizer of text-embedding-3-* and ada-002.
ENC = tiktoken.get_encoding("cl100k_base")

MAX_TOKENS = 800  # body tokens per chunk, before the context header
MIN_TOKENS = 120  # merge a trailing chunk smaller than this into the previous one
OVERLAP_TOKENS = 120  # carry the previous block into the next chunk when this small


def ntokens(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


@dataclass
class Piece:
    text: str
    tokens: int
    kind: str


SENTENCE = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z(\"'])")


def _split_long_text(text: str, limit: int) -> list[str]:
    """Split an oversized paragraph at sentence boundaries, then by tokens."""
    out, cur = [], ""
    for sent in SENTENCE.split(text):
        cand = f"{cur} {sent}".strip() if cur else sent
        if ntokens(cand) <= limit:
            cur = cand
            continue
        if cur:
            out.append(cur)
        if ntokens(sent) <= limit:
            cur = sent
        else:
            toks = ENC.encode(sent, disallowed_special=())
            for i in range(0, len(toks), limit):
                out.append(ENC.decode(toks[i : i + limit]))
            cur = ""
    if cur:
        out.append(cur)
    return out


def to_pieces(blocks: list[Block], limit: int = MAX_TOKENS) -> list[Piece]:
    """Flatten blocks into pieces no larger than `limit` tokens each."""
    pieces: list[Piece] = []
    for b in blocks:
        t = ntokens(b.text)
        if t <= limit:
            pieces.append(Piece(b.text, t, b.kind))
        elif b.kind == "table" and b.table_rows:
            # Split by rows; each piece repeats the header so it stands alone.
            head = b.table_header
            ht = ntokens(head)
            rows: list[str] = []
            for row in b.table_rows:
                cand = head + "\n" + "\n".join(rows + [row])
                if rows and ntokens(cand) > limit:
                    txt = head + "\n" + "\n".join(rows)
                    pieces.append(Piece(txt, ntokens(txt), "table"))
                    rows = []
                if ht + ntokens(row) > limit:
                    for part in _split_long_text(row, limit - ht):
                        txt = head + "\n" + part
                        pieces.append(Piece(txt, ntokens(txt), "table"))
                    continue
                rows.append(row)
            if rows:
                txt = head + "\n" + "\n".join(rows)
                pieces.append(Piece(txt, ntokens(txt), "table"))
        else:
            indent = re.match(r"^\s*", b.text).group(0)
            for part in _split_long_text(b.text.strip(), limit):
                pieces.append(Piece(indent + part, ntokens(part), b.kind))
    return pieces


def pack(blocks: list[Block], limit: int = MAX_TOKENS) -> list[str]:
    """Greedily pack blocks into chunk bodies of at most `limit` tokens.

    When a chunk boundary falls inside a section, the last small block of the
    previous chunk is repeated at the top of the next one so a list item keeps
    its lead-in sentence.
    """
    pieces = to_pieces(blocks, limit)
    if not pieces:
        return []
    groups: list[list[Piece]] = [[]]
    size = 0
    for p in pieces:
        if groups[-1] and size + p.tokens > limit:
            prev = groups[-1][-1]
            carry = (
                [prev]
                if prev.tokens <= OVERLAP_TOKENS
                and prev.kind != "table"
                and prev.tokens + p.tokens <= limit
                else []
            )
            groups.append(carry)
            size = sum(x.tokens for x in carry)
        groups[-1].append(p)
        size += p.tokens
    # Fold a tiny tail into its predecessor when it fits comfortably.
    if len(groups) > 1:
        tail = sum(x.tokens for x in groups[-1])
        head = sum(x.tokens for x in groups[-2])
        if tail < MIN_TOKENS and head + tail <= limit * 1.25:
            last = [p for p in groups.pop() if p not in groups[-1]]
            groups[-1].extend(last)
    return ["\n\n".join(p.text for p in g) for g in groups]
