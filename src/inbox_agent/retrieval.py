"""Corpus retrieval: markdown-section chunking + BM25 ranking.

Deliberately lexical (BM25) rather than embedding-based: the corpus is two
small documents, lexical retrieval is deterministic and dependency-free, and
the retrieval step still gets its own component eval (recall@k). Swapping in
an embedding store is a one-file change behind the same `search` interface.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    chunk_id: str   # e.g. "exec_preferences#3-delegation-rules"
    text: str


def _slugify(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def chunk_markdown(path: str | Path) -> list[Chunk]:
    """Split a markdown file into one chunk per ## section (stable ids)."""
    doc = Path(path).stem
    text = Path(path).read_text()
    chunks: list[Chunk] = []
    current_slug, current_lines = None, []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            if current_slug and current_lines:
                chunks.append(Chunk(f"{doc}#{current_slug}", "\n".join(current_lines).strip()))
            current_slug, current_lines = _slugify(m.group(1)), [line]
        elif current_slug:
            current_lines.append(line)
    if current_slug and current_lines:
        chunks.append(Chunk(f"{doc}#{current_slug}", "\n".join(current_lines).strip()))
    return chunks


_TOKEN = re.compile(r"[a-z0-9$]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Index:
    """Small, standard BM25 (k1=1.5, b=0.75). No dependencies, no surprises."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self._doc_tokens = [_tokens(c.text) for c in chunks]
        self._doc_len = [len(t) for t in self._doc_tokens]
        self._avg_len = (sum(self._doc_len) / len(chunks)) if chunks else 0.0
        self._tf = [Counter(t) for t in self._doc_tokens]
        df: Counter = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        q = _tokens(query)
        scores = []
        for i, chunk in enumerate(self.chunks):
            s = 0.0
            for term in q:
                if term not in self._tf[i]:
                    continue
                tf = self._tf[i][term]
                denom = tf + self.k1 * (1 - self.b + self.b * self._doc_len[i] / self._avg_len)
                s += self._idf.get(term, 0.0) * tf * (self.k1 + 1) / denom
            scores.append((chunk, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


def build_index(corpus_dir: str | Path = "corpus") -> BM25Index:
    chunks: list[Chunk] = []
    for md in sorted(Path(corpus_dir).glob("*.md")):
        chunks.extend(chunk_markdown(md))
    return BM25Index(chunks)
