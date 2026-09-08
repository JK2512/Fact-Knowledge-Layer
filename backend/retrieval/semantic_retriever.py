"""
Lexical and lightweight local semantic search over compact fact-evidence representations.
Uses TF-IDF and BM25 token weighting over structured fact summaries and evidence quotes.
No cloud vector database required.
"""

import re
import math
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
from backend.database import get_db, get_all_documents, get_all_facts
from backend.retrieval.schemas import RetrievedFact


class SemanticRetriever:
    """Local, lightweight lexical and n-gram similarity retriever over fact-evidence cards."""

    def __init__(self):
        self._doc_cache = {}
        self._fact_cards = []
        self._idf = {}
        self._avg_dl = 0.0
        self._indexed = False

    def build_index(self, facts: Optional[List[Dict[str, Any]]] = None):
        """Build the in-memory BM25 index over compact fact cards."""
        try:
            docs = get_all_documents()
            self._doc_cache = {d["id"]: d for d in docs}
        except Exception:
            self._doc_cache = {}

        if facts is None:
            facts = get_all_facts()

        self._fact_cards = []
        doc_freqs = Counter()
        total_len = 0

        for f in facts:
            doc = self._doc_cache.get(f["document_id"], {})
            doc_name = doc.get("filename", "")
            
            # Compact fact-evidence representation
            card_text = (
                f"{f.get('subject', '')} | {f.get('predicate', '')} | {f.get('value', '')} "
                f"{f.get('unit', '')} | {f.get('time_period', '')} | {doc_name} | "
                f"Page {f.get('source_page', 0)} | {f.get('source_text', '')} | {f.get('context', '')}"
            )
            tokens = self._tokenize(card_text)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                doc_freqs[t] += 1

            total_len += len(tokens)
            self._fact_cards.append({
                "fact": f,
                "doc_name": doc_name,
                "doc_title": doc.get("title", doc_name),
                "tokens": tokens,
                "tf": Counter(tokens),
                "length": len(tokens),
                "text": card_text,
            })

        n_docs = len(self._fact_cards)
        self._avg_dl = (total_len / n_docs) if n_docs > 0 else 1.0
        self._idf = {}
        for term, df in doc_freqs.items():
            self._idf[term] = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))

        self._indexed = True

    STOP_WORDS = {
        "the", "and", "for", "with", "that", "this", "what", "was", "were", "are", "from",
        "sources", "available", "documents", "show", "tell", "does", "did", "how", "much",
        "many", "give", "find", "which", "across", "differ", "why", "value", "safely", "interpreted",
        "can", "figures", "report", "reports", "document", "information", "do", "is", "in", "of",
        "to", "on", "by", "at", "an", "be", "or", "as", "into"
    }

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words and filter stop tokens."""
        words = re.findall(r'[a-zA-Z0-9_\.]+', text.lower())
        return [w for w in words if len(w) > 1 and w not in self.STOP_WORDS]

    def search(self, query: str, top_k: int = 30) -> List[RetrievedFact]:
        """Search facts using BM25 scoring."""
        if not self._indexed or not self._fact_cards:
            self.build_index()

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        # BM25 parameters
        k1 = 1.5
        b = 0.75

        scores = []
        for idx, item in enumerate(self._fact_cards):
            score = 0.0
            tf_map = item["tf"]
            doc_len = item["length"]

            for token in q_tokens:
                if token in tf_map:
                    tf = tf_map[token]
                    idf = self._idf.get(token, 0.5)
                    numerator = tf * (k1 + 1.0)
                    denominator = tf + k1 * (1.0 - b + b * (doc_len / self._avg_dl))
                    score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, idx in scores[:top_k]:
            item = self._fact_cards[idx]
            f = item["fact"]
            results.append(RetrievedFact(
                id=f["id"],
                document_id=f["document_id"],
                document_filename=item["doc_name"],
                document_title=item["doc_title"],
                fact_type=f["fact_type"],
                subject=f["subject"],
                predicate=f["predicate"],
                value=f["value"],
                numeric_value=f["numeric_value"],
                unit=f["unit"],
                time_period=f["time_period"],
                confidence=f["confidence"],
                source_page=f["source_page"],
                source_text=f["source_text"],
                context=f["context"],
                normalized_subject=f["normalized_subject"],
                normalized_predicate=f["normalized_predicate"],
                normalized_period=f["normalized_period"],
                normalized_value=f["normalized_value"],
                retrieval_score=score,
                retrieval_source="lexical",
            ))

        return results
