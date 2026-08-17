"""RAG advisory — HANYA teks SOP/standar, tidak pernah menghitung angka.

Pipeline: ingest (kb/*.md) -> chunk (per-seksi) -> embed -> retrieve (top-k).
Embedder default = TF-IDF (pure-Python, tanpa dependensi) agar selalu jalan.
Bisa di-upgrade ke sentence-transformers + FAISS bila terpasang.
"""
from __future__ import annotations
import math
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any

KB_DIR = Path(__file__).parent / "kb"

# stopword ringan (ID + EN) untuk TF-IDF
_STOP = set("""dan atau yang di ke dari pada untuk dengan dalam adalah ini itu para suatu
the a an of to in on for and or with is are be as at by from this that""".split())


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 2]


# --------------------------------------------------------------------------
# Ingestion + chunking
# --------------------------------------------------------------------------
def _parse_frontmatter(raw: str):
    meta, body = {}, raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body


def load_chunks(kb_dir: Path = KB_DIR) -> List[Dict[str, Any]]:
    """Chunk per seksi markdown (heading ## / paragraf), lampirkan metadata sumber."""
    chunks = []
    for fp in sorted(kb_dir.glob("*.md")):
        meta, body = _parse_frontmatter(fp.read_text(encoding="utf-8"))
        # pisah per paragraf (blok kosong), buang heading-only
        for i, para in enumerate(re.split(r"\n\s*\n", body)):
            text = para.strip()
            if len(text) < 40 or text.startswith("#") and len(text) < 80:
                continue
            text = re.sub(r"^#+\s*", "", text)
            chunks.append({
                "id": f"{fp.stem}#{i}",
                "text": text,
                "source": meta.get("source", fp.stem),
                "url": meta.get("url", ""),
                "commodity": meta.get("commodity", "umum"),
                "tier": meta.get("tier", ""),
            })
    return chunks


# --------------------------------------------------------------------------
# Embedder: TF-IDF pure-Python (default)
# --------------------------------------------------------------------------
class TfidfEmbedder:
    name = "tfidf"

    def fit(self, docs: List[str]):
        self.docs_tokens = [_tokenize(d) for d in docs]
        df = Counter()
        for toks in self.docs_tokens:
            for t in set(toks):
                df[t] += 1
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.doc_vecs = [self._vec(toks) for toks in self.docs_tokens]
        return self

    def _vec(self, toks: List[str]) -> Dict[str, float]:
        tf = Counter(toks)
        total = max(1, len(toks))
        return {t: (c / total) * self.idf.get(t, 0.0) for t, c in tf.items()}

    def embed_query(self, q: str) -> Dict[str, float]:
        return self._vec(_tokenize(q))


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


# --------------------------------------------------------------------------
# KnowledgeBase
# --------------------------------------------------------------------------
class KnowledgeBase:
    def __init__(self, kb_dir: Path = KB_DIR, embedder=None):
        self.chunks = load_chunks(kb_dir)
        self.embedder = embedder or TfidfEmbedder()
        self.embedder.fit([c["text"] for c in self.chunks])

    def retrieve(self, query: str, commodity: str = None,
                 top_k: int = 4, min_score: float = 0.05) -> List[Dict[str, Any]]:
        qv = self.embedder.embed_query(query)
        scored = []
        for c, dv in zip(self.chunks, self.embedder.doc_vecs):
            s = _cosine(qv, dv)
            # boost bila komoditas cocok
            if commodity and c["commodity"] in (commodity, "umum"):
                s *= 1.15
            scored.append((s, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = [{"text": c["text"], "source": c["source"], "url": c["url"],
                 "score": round(s, 4)} for s, c in scored[:top_k] if s >= min_score]
        return hits


def retrieve_advisory(kb: KnowledgeBase, commodity: str, risk_level: str,
                      top_k: int = 4) -> Dict[str, Any]:
    """Tool RAG. Query dibentuk dari komoditas + tingkat risiko (hasil L1)."""
    risk_terms = {"high": "risiko tinggi mitigasi percepat pendingin",
                  "medium": "penanganan menjaga suhu",
                  "low": "penyimpanan standar"}
    query = f"penanganan {commodity} {risk_terms.get(risk_level, '')}"
    snippets = kb.retrieve(query, commodity=commodity, top_k=top_k)
    if not snippets:
        return {"snippets": [], "fallback": True,
                "note": "tanpa sumber spesifik — jaga suhu sedekat mungkin 0-4 C, percepat pengiriman"}
    return {"snippets": snippets, "fallback": False}
