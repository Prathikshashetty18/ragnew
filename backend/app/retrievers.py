"""
Multi-Retrieval Engine: Dense FAISS, Persistent BM25, Reciprocal Rank Fusion,
Cross-Encoder Reranker, and Evidence Deduplicator.
"""

import os
import re
import math
import pickle
import threading
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np
import faiss
from sentence_transformers import CrossEncoder

from app.config import (
    RAG_DENSE_TOP_K,
    RAG_BM25_TOP_K,
    RAG_RRF_TOP_K,
    RAG_RRF_K,
    RAG_RERANK_TOP_K,
    RAG_RERANKER_MODEL,
    RAG_ENABLE_BM25,
    RAG_ENABLE_RERANKER,
    RAG_BM25_INDEX_PATH
)

# Thread-safe locks
_bm25_lock = threading.Lock()
_reranker_lock = threading.Lock()
_cross_encoder_instance = None


def tokenize_clinical_text(text: str) -> List[str]:
    """
    Clinical tokenizer preserving:
    - Dosages & units: '1g', '500mg', '100mg', '10.2g/dl', '48.5mg/l', '14000/ul'
    - Acronyms & scores: 'curb-65', 'afb', 'xpert', 'mtb/rif', 'cbc', 'crp', 'esr', 'dka', 'hhs'
    - Hyphenated medications: 'ampicillin-sulbactam', 'amoxicillin-clavulanate'
    """
    clean = text.lower()
    # Replace slashes in lab units or ratios with underscores so they stay as one token
    clean = re.sub(r'(\d+)\s*/\s*(ul|l|dl)', r'\1_\2', clean)
    clean = re.sub(r'(g|mg|mmol|meq)\s*/\s*(dl|l)', r'\1_\2', clean)
    # Tokenize clinical terms, alphanumerics, and hyphenated expressions
    tokens = re.findall(r'[a-z0-9]+(?:[-_][a-z0-9]+)*', clean)
    return [t for t in tokens if len(t) > 1 or t in ("g", "u")]


class PersistentBM25Index:
    """
    Persistent and incrementally updatable BM25 index for the clinical corpus.
    Avoids re-tokenizing and re-indexing the entire document collection on each query.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, storage_path: str = RAG_BM25_INDEX_PATH):
        self.k1 = k1
        self.b = b
        self.storage_path = storage_path
        self.doc_ids: List[str] = []
        self.corpus_tokens: List[List[str]] = []
        self.doc_lens: List[int] = []
        self.doc_freqs: List[Counter] = []
        self.idf: Dict[str, float] = {}
        self.N: int = 0
        self.avgdl: float = 0.0

    def build_index(self, chunks: List[Dict[str, Any]]):
        with _bm25_lock:
            self.doc_ids = [c["id"] for c in chunks]
            # Use contextualized_text for indexing when available to match structural terms
            self.corpus_tokens = [
                tokenize_clinical_text(c.get("contextualized_text") or c["text"])
                for c in chunks
            ]
            self.N = len(self.corpus_tokens)
            self.doc_lens = [len(doc) for doc in self.corpus_tokens]
            self.avgdl = (sum(self.doc_lens) / self.N) if self.N > 0 else 0.0
            self.doc_freqs = [Counter(doc) for doc in self.corpus_tokens]

            nd: Dict[str, int] = {}
            for freqs in self.doc_freqs:
                for word in freqs:
                    nd[word] = nd.get(word, 0) + 1

            self.idf = {}
            for word, freq in nd.items():
                self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

            self.save_to_disk()

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """Incrementally adds new chunks and recomputes stats."""
        with _bm25_lock:
            for c in new_chunks:
                tokens = tokenize_clinical_text(c.get("contextualized_text") or c["text"])
                self.doc_ids.append(c["id"])
                self.corpus_tokens.append(tokens)
                self.doc_lens.append(len(tokens))
                self.doc_freqs.append(Counter(tokens))

            self.N = len(self.corpus_tokens)
            self.avgdl = (sum(self.doc_lens) / self.N) if self.N > 0 else 0.0

            nd: Dict[str, int] = {}
            for freqs in self.doc_freqs:
                for word in freqs:
                    nd[word] = nd.get(word, 0) + 1

            self.idf = {}
            for word, freq in nd.items():
                self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

            self.save_to_disk()

    def remove_by_doc_id(self, document_id: int, all_metadata: List[Dict[str, Any]]):
        """Rebuilds index excluding removed document chunks."""
        retained = [c for c in all_metadata if c.get("document_id") != document_id]
        self.build_index(retained)

    def search(self, query: str, candidate_indices: Optional[List[int]] = None, top_k: int = RAG_BM25_TOP_K) -> List[Tuple[int, float]]:
        """
        Calculates BM25 scores for query across corpus or restricted candidate indices.
        Returns sorted list of (chunk_idx, score).
        """
        if self.N == 0:
            return []

        query_tokens = tokenize_clinical_text(query)
        if not query_tokens:
            return []

        target_indices = candidate_indices if candidate_indices is not None else list(range(self.N))
        scores: List[Tuple[int, float]] = []

        for idx in target_indices:
            if idx >= self.N:
                continue
            score = 0.0
            doc_freq = self.doc_freqs[idx]
            doc_len = self.doc_lens[idx]

            for token in query_tokens:
                if token in doc_freq:
                    freq = doc_freq[token]
                    idf_val = self.idf.get(token, 0.0)
                    numerator = freq * (self.k1 + 1)
                    denominator = freq + self.k1 * (1 - self.b + self.b * (doc_len / (self.avgdl or 1.0)))
                    score += idf_val * (numerator / denominator)

            if score > 0.0:
                scores.append((idx, float(score)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def save_to_disk(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "wb") as f:
                pickle.dump({
                    "doc_ids": self.doc_ids,
                    "corpus_tokens": self.corpus_tokens,
                    "doc_lens": self.doc_lens,
                    "doc_freqs": self.doc_freqs,
                    "idf": self.idf,
                    "N": self.N,
                    "avgdl": self.avgdl
                }, f)
        except Exception as e:
            print(f"Warning: Failed to save BM25 index to disk: {e}")

    @classmethod
    def load_from_disk(cls, storage_path: str = RAG_BM25_INDEX_PATH, fallback_chunks: Optional[List[Dict[str, Any]]] = None) -> "PersistentBM25Index":
        instance = cls(storage_path=storage_path)
        if os.path.exists(storage_path):
            try:
                with open(storage_path, "rb") as f:
                    data = pickle.load(f)
                    instance.doc_ids = data["doc_ids"]
                    instance.corpus_tokens = data["corpus_tokens"]
                    instance.doc_lens = data["doc_lens"]
                    instance.doc_freqs = data["doc_freqs"]
                    instance.idf = data["idf"]
                    instance.N = data["N"]
                    instance.avgdl = data["avgdl"]
                return instance
            except Exception as e:
                print(f"Warning: Could not read BM25 index from disk: {e}. Reinitializing.")

        if fallback_chunks:
            instance.build_index(fallback_chunks)
        return instance


class DenseRetriever:
    """Executes dense normalized semantic search via FAISS."""

    @staticmethod
    def search(
        query_vector: np.ndarray,
        faiss_index: faiss.Index,
        embeddings_array: Optional[np.ndarray],
        filtered_indices: List[int],
        top_k: int = RAG_DENSE_TOP_K
    ) -> List[Tuple[int, float]]:
        """
        Searches filtered dense vectors using normalized inner product (cosine similarity).
        Returns sorted list of (chunk_idx, cosine_similarity).
        """
        if faiss_index is None or len(filtered_indices) == 0:
            return []

        if embeddings_array is not None and len(embeddings_array) > 0:
            filtered_embeddings = embeddings_array[filtered_indices]
            # Ensure 2D float32 normalized vectors
            scores = np.dot(filtered_embeddings, query_vector[0])
            scored_candidates = [(filtered_indices[i], float(scores[i])) for i in range(len(filtered_indices))]
        else:
            # Fallback direct FAISS search
            k_search = min(top_k * 2, faiss_index.ntotal)
            if k_search <= 0:
                return []
            D, I = faiss_index.search(query_vector, k_search)
            scored_candidates = []
            target_set = set(filtered_indices)
            for dist, idx in zip(D[0], I[0]):
                if idx in target_set:
                    scored_candidates.append((int(idx), float(dist)))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:top_k]


class ReciprocalRankFusion:
    """Combines dense and lexical rankings using Reciprocal Rank Fusion."""

    @staticmethod
    def fuse(
        dense_results: List[Tuple[int, float]],
        bm25_results: List[Tuple[int, float]],
        k: int = RAG_RRF_K,
        top_k: int = RAG_RRF_TOP_K,
        dense_weight: float = 1.0,
        bm25_weight: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        score(doc) = dense_weight * 1/(k + dense_rank) + bm25_weight * 1/(k + bm25_rank)
        """
        dense_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(dense_results)}
        dense_score_map = {idx: score for idx, score in dense_results}

        bm25_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(bm25_results)}
        bm25_score_map = {idx: score for idx, score in bm25_results}

        all_candidate_indices = set(dense_ranks.keys()).union(set(bm25_ranks.keys()))
        fused = []

        for idx in all_candidate_indices:
            dense_rank = dense_ranks.get(idx)
            bm25_rank = bm25_ranks.get(idx)

            rrf_dense = (dense_weight / (k + dense_rank)) if dense_rank is not None else 0.0
            rrf_bm25 = (bm25_weight / (k + bm25_rank)) if bm25_rank is not None else 0.0
            rrf_score = rrf_dense + rrf_bm25

            fused.append({
                "chunk_index": idx,
                "rrf_score": float(rrf_score),
                "dense_score": float(dense_score_map.get(idx, 0.0)),
                "bm25_score": float(bm25_score_map.get(idx, 0.0)),
                "dense_rank": dense_rank,
                "bm25_rank": bm25_rank
            })

        fused.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused[:top_k]


def get_cross_encoder_model():
    """Thread-safe singleton loader for CrossEncoder."""
    global _cross_encoder_instance
    with _reranker_lock:
        if _cross_encoder_instance is None:
            try:
                print(f"Loading Cross-Encoder model: {RAG_RERANKER_MODEL}...")
                _cross_encoder_instance = CrossEncoder(RAG_RERANKER_MODEL)
            except Exception as e:
                print(f"Warning: Failed to load Cross-Encoder {RAG_RERANKER_MODEL}: {e}. Reranking fallback enabled.")
                _cross_encoder_instance = False
        return _cross_encoder_instance


class CrossEncoderReranker:
    """Scores candidate passages with cross-encoder attention and source authority weighting."""

    @staticmethod
    def rerank(
        query: str,
        candidates: List[Dict[str, Any]],
        chunks_metadata: List[Dict[str, Any]],
        top_k: int = RAG_RERANK_TOP_K
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        prepared = []
        for cand in candidates:
            idx = cand["chunk_index"]
            chunk = chunks_metadata[idx].copy()
            chunk["rrf_score"] = cand["rrf_score"]
            chunk["dense_score"] = cand["dense_score"]
            chunk["bm25_score"] = cand["bm25_score"]
            chunk["dense_rank"] = cand["dense_rank"]
            chunk["bm25_rank"] = cand["bm25_rank"]
            prepared.append(chunk)

        cross_encoder = get_cross_encoder_model() if RAG_ENABLE_RERANKER else None

        if cross_encoder and cross_encoder is not False:
            try:
                pairs = [[query, c.get("contextualized_text") or c.get("text", "")] for c in prepared]
                raw_scores = cross_encoder.predict(pairs)

                for i, score in enumerate(raw_scores):
                    authority = prepared[i].get("authority_score", 0.8)
                    # Sigmoid-normalized score adjusted by authority
                    norm_score = float(1.0 / (1.0 + math.exp(-score)))
                    adjusted_score = norm_score * (0.85 + 0.15 * authority)
                    prepared[i]["rerank_score"] = float(adjusted_score)
                    prepared[i]["raw_rerank_score"] = float(score)

                prepared.sort(key=lambda x: x["rerank_score"], reverse=True)
            except Exception as e:
                print(f"Reranking error: {e}. Falling back to RRF rank order.")
                for i, c in enumerate(prepared):
                    c["rerank_score"] = c["rrf_score"]
        else:
            # Fallback directly to RRF score
            for i, c in enumerate(prepared):
                c["rerank_score"] = c["rrf_score"]

        return prepared[:top_k]


class EvidenceDeduplicator:
    """Removes redundant and near-identical chunks while preserving diverse evidence."""

    @staticmethod
    def _compute_jaccard(tokens_a: Set[str], tokens_b: Set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def deduplicate(
        cls,
        chunks: List[Dict[str, Any]],
        similarity_threshold: float = 0.82,
        max_chunks: int = RAG_RERANK_TOP_K
    ) -> List[Dict[str, Any]]:
        deduped = []
        seen_token_sets: List[Set[str]] = []
        seen_exact_texts = set()

        for chunk in chunks:
            text = chunk.get("text", "").strip()
            if text in seen_exact_texts:
                continue

            tokens = set(re.findall(r'\w+', text.lower()))
            is_duplicate = False

            for existing_tokens in seen_token_sets:
                sim = cls._compute_jaccard(tokens, existing_tokens)
                if sim >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_exact_texts.add(text)
                seen_token_sets.append(tokens)
                deduped.append(chunk)

            if len(deduped) >= max_chunks:
                break

        return deduped
