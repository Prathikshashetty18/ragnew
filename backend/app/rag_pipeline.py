"""
Upgraded Multi-RAG Pipeline for Clinical Decision Support System.

Architecture:
Clinical Query Understanding -> Query Expansion -> Deterministic Routing
-> Multi-Retrieval (Dense FAISS + Persistent BM25 + Exact Term)
-> Reciprocal Rank Fusion (RRF) -> Cross-Encoder Reranking + Authority Adjustment
-> Evidence Deduplication -> Parent-Child Context Assembly
-> Grounded Clinical LLM Generation -> NLI Fact-Verification -> Permission Citations
"""

import os
import re
import time
import pickle
import threading
import uuid
import math
from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np
import faiss
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from groq import Groq
import http.client
import json

from app.config import (
    UPLOAD_DIR,
    VECTOR_STORE_DIR,
    GROQ_API_KEY,
    GROQ_MODEL,
    EMBEDDING_MODEL_NAME,
    RERANK_MODEL_NAME,
    SIMILARITY_THRESHOLD_SUPPORTED,
    SIMILARITY_THRESHOLD_PARTIAL,
    NLI_ENTAILMENT_THRESHOLD,
    NLI_CONTRADICTION_THRESHOLD,
    RAG_DENSE_TOP_K,
    RAG_BM25_TOP_K,
    RAG_RRF_TOP_K,
    RAG_RRF_K,
    RAG_RERANK_TOP_K,
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
    RAG_ENABLE_QUERY_REWRITE,
    RAG_ENABLE_BM25,
    RAG_ENABLE_RERANKER,
    RAG_DEBUG,
    RAG_INSUFFICIENT_EVIDENCE_THRESHOLD,
    RAG_BM25_INDEX_PATH
)
from app.nli_validator import validate_response_with_nli, filter_citations_by_permission
from app.clinical_understanding import ClinicalEntityExtractor, ClinicalQueryExpander
from app.chunking import HierarchicalClinicalChunker, ContextualChunkEnricher
from app.retrievers import (
    DenseRetriever,
    PersistentBM25Index,
    ReciprocalRankFusion,
    CrossEncoderReranker,
    EvidenceDeduplicator,
    get_cross_encoder_model
)
from app.router import MultiRAGRouter

# Thread-safe locks
_models_lock = threading.Lock()
_vector_store_lock = threading.Lock()

_embedding_model = None
_faiss_index = None
_chunks_metadata: List[Dict[str, Any]] = []
_embeddings_array: Optional[np.ndarray] = None
_bm25_index: Optional[PersistentBM25Index] = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    with _models_lock:
        if _embedding_model is None:
            print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return _embedding_model


def get_vector_store() -> Tuple[faiss.Index, List[Dict[str, Any]], Optional[np.ndarray]]:
    global _faiss_index, _chunks_metadata, _embeddings_array
    with _vector_store_lock:
        if _faiss_index is None:
            index_path = os.path.join(VECTOR_STORE_DIR, "vector_store.index")
            metadata_path = os.path.join(VECTOR_STORE_DIR, "chunks.pkl")

            if os.path.exists(index_path) and os.path.exists(metadata_path):
                print("Loading FAISS index and metadata from disk...")
                try:
                    _faiss_index = faiss.read_index(index_path)
                    with open(metadata_path, "rb") as f:
                        _chunks_metadata = pickle.load(f)

                    if _faiss_index.ntotal > 0:
                        try:
                            _embeddings_array = _faiss_index.reconstruct_n(0, _faiss_index.ntotal)
                        except AttributeError:
                            _embeddings_array = np.array([_faiss_index.reconstruct(i) for i in range(_faiss_index.ntotal)]).astype("float32")
                    else:
                        _embeddings_array = None
                except Exception as e:
                    print(f"Error loading FAISS vector store: {e}. Reinitializing.")
                    _faiss_index = None
                    _chunks_metadata = []
                    _embeddings_array = None

            if _faiss_index is None:
                dimension = 384
                _faiss_index = faiss.IndexFlatIP(dimension)
                _chunks_metadata = []
                _embeddings_array = None

        return _faiss_index, _chunks_metadata, _embeddings_array


def get_bm25_index() -> PersistentBM25Index:
    global _bm25_index
    if _bm25_index is None:
        _, metadata, _ = get_vector_store()
        _bm25_index = PersistentBM25Index.load_from_disk(
            storage_path=RAG_BM25_INDEX_PATH,
            fallback_chunks=metadata
        )
    return _bm25_index


def save_vector_store(index: faiss.Index, metadata: List[Dict[str, Any]]):
    with _vector_store_lock:
        index_path = os.path.join(VECTOR_STORE_DIR, "vector_store.index")
        metadata_path = os.path.join(VECTOR_STORE_DIR, "chunks.pkl")

        faiss.write_index(index, index_path)
        with open(metadata_path, "wb") as f:
            pickle.dump(metadata, f)
        print("Saved FAISS index and metadata to disk.")


def remove_document_from_vector_store(doc_id: int):
    """Removes all chunks belonging to a document from both FAISS and BM25 store."""
    global _faiss_index, _chunks_metadata, _embeddings_array, _bm25_index
    with _vector_store_lock:
        _, metadata, _ = get_vector_store()

        retained_chunks = [c for c in metadata if c.get("document_id") != doc_id]
        if len(retained_chunks) == len(metadata):
            return

        print(f"Removing document ID {doc_id} from vector store. Rebuilding FAISS index with {len(retained_chunks)} chunks...")
        dimension = 384
        new_index = faiss.IndexFlatIP(dimension)

        if retained_chunks:
            embedder = get_embedding_model()
            texts = [c.get("contextualized_text") or c["text"] for c in retained_chunks]
            embeddings = embedder.encode(texts)
            embeddings = np.array(embeddings).astype("float32")
            faiss.normalize_L2(embeddings)
            new_index.add(embeddings)
            _embeddings_array = embeddings
        else:
            _embeddings_array = None

        _faiss_index = new_index
        _chunks_metadata = retained_chunks
        save_vector_store(_faiss_index, _chunks_metadata)

        # Update persistent BM25 index
        bm25 = get_bm25_index()
        bm25.remove_by_doc_id(doc_id, retained_chunks)


def split_into_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def process_pdf(
    file_path: str,
    filename: str,
    doc_id: Optional[int] = None,
    scope: str = "knowledge_base",
    patient_id: Optional[str] = None,
    version: str = "1.0",
    document_type: str = "Guideline"
) -> int:
    """
    Extracts text page-by-page, applies hierarchical chunking with structural context,
    embeds contextualized chunks into FAISS, and updates the persistent BM25 index.
    """
    print(f"Processing PDF (Multi-RAG): {filename} from {file_path} (scope={scope}, patient={patient_id}, version={version})")
    reader = PdfReader(file_path)
    all_chunks = []
    chunker = HierarchicalClinicalChunker(chunk_size=RAG_CHUNK_SIZE, chunk_overlap=RAG_CHUNK_OVERLAP)

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        page_text = page.extract_text() or ""
        if page_text.strip():
            page_chunks = chunker.chunk_document(
                text=page_text,
                pdf_name=filename,
                page_number=page_num,
                doc_id=doc_id,
                scope=scope,
                patient_id=patient_id,
                version=version,
                document_type=document_type
            )
            all_chunks.extend(page_chunks)

    if not all_chunks:
        print("No text extracted from PDF.")
        return 0

    print(f"Extracted {len(all_chunks)} hierarchical chunks from {filename}.")

    embedder = get_embedding_model()
    # Embed contextualized text so vectors encode section, guideline, and topic headers
    contextualized_texts = [chunk.get("contextualized_text") or chunk["text"] for chunk in all_chunks]

    embeddings = embedder.encode(contextualized_texts, show_progress_bar=False)
    embeddings = np.array(embeddings).astype("float32")
    faiss.normalize_L2(embeddings)

    index, metadata, embed_arr = get_vector_store()
    index.add(embeddings)
    metadata.extend(all_chunks)

    global _embeddings_array
    if _embeddings_array is None:
        _embeddings_array = embeddings
    else:
        _embeddings_array = np.vstack([_embeddings_array, embeddings])

    save_vector_store(index, metadata)

    # Update persistent BM25 index
    bm25 = get_bm25_index()
    bm25.add_chunks(all_chunks)

    return len(all_chunks)


DEFAULT_STRICT_RAG_SYSTEM_PROMPT = (
    "You are an expert Clinical Decision Support System (CDSS) assistant for hospital clinicians.\n"
    "STRICT EVIDENCE GROUNDING RULES:\n"
    "1. Answer the clinical question using ONLY the supplied retrieved evidence passages.\n"
    "2. Do NOT use any outside medical knowledge, external training assumptions, or unverified treatments.\n"
    "3. Do NOT invent facts, diagnoses, dosages, treatments, clinical values, drug regimens, or recommendations.\n"
    "4. Paraphrasing is permitted ONLY if the clinical meaning remains completely supported by the text.\n"
    "5. If the retrieved evidence does not adequately answer the question, return verbatim: "
    "\"Insufficient evidence in the hospital knowledge base to answer this question reliably.\"\n"
    "6. Do NOT guess or fill in missing clinical parameters with ungrounded assumptions.\n"
    "7. Annotate medical claims with their corresponding bracketed source reference, e.g., [1], [2]."
)


def call_groq_llm(prompt: str, max_tokens: int = 4096, system_prompt: Optional[str] = None) -> str:
    try:
        sys_content = system_prompt or DEFAULT_STRICT_RAG_SYSTEM_PROMPT
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": sys_content
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.05,
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API call failed: {e}")
        raise e


def call_gemini_fallback(prompt: str, system_prompt: Optional[str] = None) -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("No Gemini/Google API Key found.")

    sys_content = system_prompt or DEFAULT_STRICT_RAG_SYSTEM_PROMPT

    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{sys_content}\n\n{prompt}"
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.05,
            "maxOutputTokens": 2048
        }
    }

    try:
        conn.request("POST", f"/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}", json.dumps(payload), headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        response_json = json.loads(data)
        return response_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini API fallback failed: {e}")
        raise e


def generate_mock_answer(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """Generates an evidence-grounded response when external LLM APIs are unreachable."""
    if not retrieved_chunks:
        return "I could not find sufficient supporting evidence in the authorized clinical guidelines to answer this question."

    sentences = []
    for idx, chunk in enumerate(retrieved_chunks):
        c_sents = split_into_sentences(chunk.get("text", ""))
        for s in c_sents:
            sentences.append((s, chunk.get("pdf_name", "Guideline"), chunk.get("page_number", 1), idx + 1))

    query_words = set(re.findall(r'\w+', query.lower())) - {"what", "is", "are", "the", "for", "and", "in", "to", "of", "a", "an"}
    scored = []
    for s, src, page, ref_id in sentences:
        s_words = set(re.findall(r'\w+', s.lower()))
        common = query_words.intersection(s_words)
        if common:
            scored.append((len(common), f"{s} [{ref_id}]"))

    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        top_sentences = [item[1] for item in scored[:3]]
        answer = "Based on the verified clinical documents: " + " ".join(top_sentences)
    else:
        # Fallback to the first available clinical sentence from top chunk
        first_chunk = retrieved_chunks[0]
        first_sent = split_into_sentences(first_chunk.get("text", ""))[0] if first_chunk.get("text") else ""
        if first_sent:
            answer = f"According to {first_chunk.get('pdf_name', 'clinical guidelines')}: {first_sent} [1]"
        else:
            answer = "I could not find sufficient supporting evidence in the retrieved documents to answer this question reliably."

    return answer


def query_pipeline(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    direct_llm: bool = False,
    user_role: str = "DOCTOR",
    active_doc_ids: Optional[Set[int]] = None
) -> Dict[str, Any]:
    """
    Executes the full Multi-RAG pipeline:
    1. Clinical Entity Extraction & Query Understanding
    2. Query Rewriting / Expansion
    3. Multi-RAG Deterministic Routing
    4. Scope & Lifecycle Filtering
    5. Dense Vector Retrieval (FAISS Top 40)
    6. Persistent Lexical Retrieval (BM25 Top 40)
    7. Reciprocal Rank Fusion (RRF Top 40)
    8. Cross-Encoder Reranking + Source Authority Adjustment
    9. Evidence Deduplication (Top 5-8 chunks)
    10. Insufficient Evidence Detection
    11. Parent-Child Context Assembly
    12. Grounded Clinical Generation
    13. NLI Sentence-Level Fact Verification
    14. Permission-Aware Citation Formatting
    """
    t0 = time.time()
    index, metadata, embeddings_array = get_vector_store()

    if len(metadata) == 0 and not direct_llm:
        return {
            "answer": "No active clinical documents have been indexed in the system yet. Please upload hospital guidelines to enable Retrieval-Augmented Generation.",
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "grounding_level": "Not Supported",
            "grounding_coverage": "0 of 0 claims supported",
            "supported_claims": 0,
            "total_claims": 0,
            "evidence": [],
            "verification_results": [],
            "grounded": False,
            "citations": []
        }

    # DIRECT LLM Mode
    if direct_llm:
        prompt = f"""You are a clinical decision support assistant. Answer the medical question directly using general clinical knowledge.
IMPORTANT: Clearly label your answer as a direct unverified LLM response.

USER QUESTION:
{query}

CLINICAL RESPONSE (DIRECT LLM):"""

        answer = ""
        using_mock = False

        if GROQ_API_KEY:
            try:
                answer = call_groq_llm(prompt)
            except Exception:
                gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                if gemini_key:
                    try:
                        answer = call_gemini_fallback(prompt)
                    except Exception:
                        answer = "Direct LLM Mode: External APIs unavailable."
                        using_mock = True
                else:
                    answer = "Direct LLM Mode: External APIs unavailable."
                    using_mock = True
        else:
            gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if gemini_key:
                try:
                    answer = call_gemini_fallback(prompt)
                except Exception:
                    answer = "Direct LLM Mode: External API unavailable."
                    using_mock = True
            else:
                answer = "Direct LLM Mode: No API keys configured. LLM generation unavailable."
                using_mock = True

        return {
            "answer": answer,
            "confidence_level": "High" if not using_mock else "Low",
            "confidence_score": 1.0 if not using_mock else 0.0,
            "grounding_level": "Not Supported" if using_mock else "Partially Supported",
            "grounding_coverage": "Unverified direct LLM response",
            "supported_claims": 0,
            "total_claims": 0,
            "evidence": [],
            "verification_results": [],
            "using_mock": using_mock,
            "grounded": False,
            "citations": []
        }

    # 1. Clinical Query Understanding
    clinical_entities = ClinicalEntityExtractor.extract_entities(query)
    
    # 2. Query Rewriting / Expansion
    query_variants = ClinicalQueryExpander.expand_query(query, clinical_entities) if RAG_ENABLE_QUERY_REWRITE else [query]

    # 3. Deterministic Routing
    routing_decision = MultiRAGRouter.route_query(query, clinical_entities)
    dense_weight = routing_decision["dense_weight"]
    bm25_weight = routing_decision["bm25_weight"]

    # 4. Scope & Document Status Filtering
    filtered_chunks_with_indices: List[Tuple[int, Dict[str, Any]]] = []
    for idx, chunk in enumerate(metadata):
        doc_id = chunk.get("document_id")
        if active_doc_ids is not None and doc_id is not None and doc_id not in active_doc_ids:
            continue

        match = True
        if filters:
            scope = filters.get("scope")
            if scope == "knowledge_base":
                if chunk.get("scope") != "knowledge_base":
                    match = False
            elif scope == "patient":
                patient_id = filters.get("patient_id")
                if chunk.get("scope") != "patient" or chunk.get("patient_id") != patient_id:
                    match = False
            elif scope == "temporary":
                doc_id_filter = filters.get("document_id")
                if str(chunk.get("document_id")) != str(doc_id_filter):
                    match = False
            elif scope == "patient_and_kb":
                patient_id = filters.get("patient_id")
                is_kb = chunk.get("scope") == "knowledge_base"
                is_patient = chunk.get("scope") == "patient" and chunk.get("patient_id") == patient_id
                if not (is_kb or is_patient):
                    match = False

        if match:
            filtered_chunks_with_indices.append((idx, chunk))

    if not filtered_chunks_with_indices:
        scope_desc = filters.get("scope", "requested") if filters else "requested"
        return {
            "answer": f"No active documents could be retrieved for the {scope_desc} scope. Please check document approval status.",
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "grounding_level": "Not Supported",
            "grounding_coverage": "0 of 0 claims supported",
            "supported_claims": 0,
            "total_claims": 0,
            "evidence": [],
            "verification_results": [],
            "grounded": False,
            "citations": []
        }

    filtered_indices = [idx for idx, _ in filtered_chunks_with_indices]

    # 5. Dense FAISS Vector Search
    t_ret_start = time.time()
    embedder = get_embedding_model()
    query_vector = embedder.encode([query])
    query_vector = np.array(query_vector).astype("float32")
    faiss.normalize_L2(query_vector)

    dense_candidates = DenseRetriever.search(
        query_vector=query_vector,
        faiss_index=index,
        embeddings_array=embeddings_array,
        filtered_indices=filtered_indices,
        top_k=RAG_DENSE_TOP_K
    )

    # 6. Persistent BM25 Lexical Search (Original query + Variants)
    bm25 = get_bm25_index()
    bm25_candidates_map: Dict[int, float] = {}

    if RAG_ENABLE_BM25:
        # Search primary query
        p_results = bm25.search(query, candidate_indices=filtered_indices, top_k=RAG_BM25_TOP_K)
        for c_idx, score in p_results:
            bm25_candidates_map[c_idx] = max(bm25_candidates_map.get(c_idx, 0.0), score)

        # Search expanded variants with slight discount
        for v in query_variants[1:]:
            v_results = bm25.search(v, candidate_indices=filtered_indices, top_k=RAG_BM25_TOP_K // 2)
            for c_idx, score in v_results:
                bm25_candidates_map[c_idx] = max(bm25_candidates_map.get(c_idx, 0.0), score * 0.85)

    bm25_candidates = sorted(list(bm25_candidates_map.items()), key=lambda x: x[1], reverse=True)[:RAG_BM25_TOP_K]
    t_ret_end = time.time()

    # 7. Reciprocal Rank Fusion
    fused_candidates = ReciprocalRankFusion.fuse(
        dense_results=dense_candidates,
        bm25_results=bm25_candidates,
        k=RAG_RRF_K,
        top_k=RAG_RRF_TOP_K,
        dense_weight=dense_weight,
        bm25_weight=bm25_weight
    )

    # 8. Cross-Encoder Reranking
    t_rerank_start = time.time()
    reranked_chunks = CrossEncoderReranker.rerank(
        query=query,
        candidates=fused_candidates,
        chunks_metadata=metadata,
        top_k=RAG_RERANK_TOP_K * 2
    )
    t_rerank_end = time.time()

    # 9. Evidence Deduplication
    top_chunks = EvidenceDeduplicator.deduplicate(
        chunks=reranked_chunks,
        similarity_threshold=0.82,
        max_chunks=RAG_RERANK_TOP_K
    )

    # 10. Insufficient Evidence Detection
    # If the candidate pool is empty or Cross-Encoder/Dense retrieval scores are below safety thresholds
    max_dense_score = max([c.get("dense_score", 0.0) for c in top_chunks], default=0.0)
    max_bm25_score = max([c.get("bm25_score", 0.0) for c in top_chunks], default=0.0)
    max_rerank_score = max([c.get("rerank_score", 0.0) for c in top_chunks], default=0.0)
    max_raw_rerank = max([c.get("raw_rerank_score", -999.0) for c in top_chunks], default=-999.0)

    # Structured Backend Debug Logging: Retrieval & Candidates
    print(f"\n[CDSS DEBUG] Retrieved Chunks ({len(top_chunks)}):")
    for idx, c in enumerate(top_chunks):
        c_score = c.get("rerank_score", c.get("dense_score", 0.0))
        c_id = c.get("chunk_id") or c.get("id") or (idx + 1)
        print(f"  [{idx+1}] ID: {c_id} | PDF: {c.get('pdf_name')} (Page {c.get('page_number')}) | Score: {c_score:.3f}")
    print(f"[CDSS DEBUG] Retrieval Scores: Dense Max={max_dense_score:.3f}, BM25 Max={max_bm25_score:.3f}, Rerank Max={max_rerank_score:.3f}, Raw Logits Max={max_raw_rerank:.3f}")

    is_insufficient = False
    if not top_chunks:
        is_insufficient = True
    elif max_raw_rerank < -3.0 or max_rerank_score < 0.15:
        # Cross-encoder evaluated all candidate passages as completely non-matching (< -3.0 logits)
        is_insufficient = True
    elif max_dense_score < RAG_INSUFFICIENT_EVIDENCE_THRESHOLD and max_bm25_score < 1.0:
        is_insufficient = True

    print(f"[CDSS DEBUG] Evidence Quality Gate: {'FAILED (Insufficient Evidence)' if is_insufficient else 'PASSED'}")

    if is_insufficient:
        return {
            "answer": (
                "Insufficient evidence in the hospital knowledge base to answer this question reliably. "
                "Please consult hospital clinical protocols or an attending specialist directly."
            ),
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "grounding_level": "Not Supported",
            "grounding_coverage": "0 of 0 claims supported",
            "supported_claims": 0,
            "total_claims": 0,
            "evidence": [],
            "verification_results": [],
            "grounded": False,
            "citations": [],
            "retrieval": {
                "strategy": routing_decision["strategy"],
                "dense_candidates": len(dense_candidates),
                "bm25_candidates": len(bm25_candidates),
                "reranked_candidates": len(top_chunks),
                "retrieval_latency_ms": round((t_ret_end - t_ret_start) * 1000, 1),
                "rerank_latency_ms": round((t_rerank_end - t_rerank_start) * 1000, 1),
                "insufficient_evidence": True
            }
        }

    # 11. Parent-Child Context Assembly with Full Metadata
    context_passages = []
    structured_citations = []

    for idx, c in enumerate(top_chunks):
        ref_idx = idx + 1
        scope_label = "PATIENT RECORD" if c.get("scope") == "patient" else "HOSPITAL GUIDELINE"
        version_str = f" (Ver: {c.get('version', '1.0')})" if c.get("version") else ""
        section_str = f" | Section: {c.get('section', 'General')}" if c.get("section") else ""
        subsection_str = f" | Subsection: {c.get('subsection', 'Details')}" if c.get("subsection") else ""
        chunk_id_val = c.get("chunk_id") or c.get("id") or ref_idx
        chunk_id_str = f" | Chunk ID: #{chunk_id_val}"

        passage = (
            f"[{ref_idx}] [{scope_label}] Source: {c['pdf_name']}{version_str}{section_str}{subsection_str}{chunk_id_str}, Page {c['page_number']}\n"
            f"Context: {c.get('parent_section', c.get('disease', 'Clinical Protocol'))}\n"
            f"Content: {c['text']}"
        )
        context_passages.append(passage)

        structured_citations.append({
            "citation_id": ref_idx,
            "chunk_id": chunk_id_val,
            "pdf_name": c["pdf_name"],
            "page_number": c["page_number"],
            "section": c.get("section", "General"),
            "subsection": c.get("subsection", "Details"),
            "version": c.get("version", "1.0"),
            "document_type": c.get("document_type", "Guideline"),
            "authority_score": c.get("authority_score", 0.8)
        })

    context_text = "\n\n".join(context_passages)

    # 12. Grounded Clinical Generation Prompt
    prompt = f"""Use the following verified hospital evidence passages to answer the clinician's query.

STRICT CLINICAL GROUNDING DIRECTIVES:
1. Answer the clinical question using ONLY the supplied retrieved evidence passages.
2. Do NOT use outside medical knowledge, conjecture, or unverified treatments.
3. Do NOT invent facts, diagnoses, dosages, treatments, clinical values, or recommendations.
4. Paraphrasing is allowed IF AND ONLY IF the clinical meaning is preserved and fully supported.
5. If the retrieved evidence does not adequately answer the question, return verbatim:
"Insufficient evidence in the hospital knowledge base to answer this question reliably."
6. Do NOT guess or fill in missing clinical information.
7. Annotate medical claims with their corresponding bracketed source reference, e.g., [1], [2].

---
RETRIEVED HOSPITAL EVIDENCE PASSAGES:
{context_text}
---
CLINICIAN QUERY:
{query}

CLINICAL RESPONSE (STRICTLY GROUNDED CDSS):"""

    t_gen_start = time.time()
    answer = ""
    using_mock = False

    if GROQ_API_KEY:
        try:
            answer = call_groq_llm(prompt, system_prompt=DEFAULT_STRICT_RAG_SYSTEM_PROMPT)
        except Exception:
            gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if gemini_key:
                try:
                    answer = call_gemini_fallback(prompt, system_prompt=DEFAULT_STRICT_RAG_SYSTEM_PROMPT)
                except Exception:
                    answer = generate_mock_answer(query, top_chunks)
                    using_mock = True
            else:
                answer = generate_mock_answer(query, top_chunks)
                using_mock = True
    else:
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if gemini_key:
            try:
                answer = call_gemini_fallback(prompt, system_prompt=DEFAULT_STRICT_RAG_SYSTEM_PROMPT)
            except Exception:
                answer = generate_mock_answer(query, top_chunks)
                using_mock = True
        else:
            answer = generate_mock_answer(query, top_chunks)
            using_mock = True
    t_gen_end = time.time()

    # 13. NLI Sentence-Level Fact Verification Engine
    nli_results = validate_response_with_nli(
        answer=answer,
        context_chunks=top_chunks,
        embedder=embedder,
        cross_encoder=get_cross_encoder_model(),
        similarity_threshold_entailment=SIMILARITY_THRESHOLD_SUPPORTED,
        similarity_threshold_partial=SIMILARITY_THRESHOLD_PARTIAL
    )

    # 14. RBAC Permission Filtering for Evidence & Citations
    permitted_evidence = filter_citations_by_permission(nli_results["evidence"], user_role)

    final_answer = answer
    if nli_results.get("contradiction_count", 0) > 0:
        final_answer = (
            "The retrieved clinical evidence contains conflicting or contradictory findings regarding this question. "
            "Please review the official hospital guideline documents directly."
        )
    elif (
        nli_results.get("grounding_level") == "Not Supported"
        and nli_results.get("supported_claims", 0) == 0
        and nli_results.get("total_claims", 0) > 0
        and nli_results.get("confidence_score", 0.0) < 0.35
        and not using_mock
    ):
        final_answer = (
            "Insufficient evidence in the hospital knowledge base to answer this question reliably. "
            "(Clinical safety safeguard: ungrounded claims are suppressed.)"
        )

    total_latency_ms = round((time.time() - t0) * 1000, 1)

    telemetry = {
        "strategy": routing_decision["strategy"],
        "dense_candidates": len(dense_candidates),
        "bm25_candidates": len(bm25_candidates),
        "fused_candidates": len(fused_candidates),
        "reranked_candidates": len(top_chunks),
        "retrieval_latency_ms": round((t_ret_end - t_ret_start) * 1000, 1),
        "rerank_latency_ms": round((t_rerank_end - t_rerank_start) * 1000, 1),
        "generation_latency_ms": round((t_gen_end - t_gen_start) * 1000, 1),
        "total_latency_ms": total_latency_ms,
        "query_variants": query_variants if RAG_DEBUG else [],
        "entities": clinical_entities if RAG_DEBUG else {}
    }

    return {
        "answer": final_answer,
        "confidence_level": nli_results["confidence_level"],
        "confidence_score": nli_results["confidence_score"],
        "grounding_level": nli_results.get("grounding_level", "Partially Supported"),
        "grounding_coverage": nli_results.get("grounding_coverage", ""),
        "supported_claims": nli_results.get("supported_claims", 0),
        "total_claims": nli_results.get("total_claims", 0),
        "evidence": permitted_evidence,
        "verification_results": nli_results["verification_results"],
        "using_mock": using_mock,
        "entailment_count": nli_results.get("entailment_count", 0),
        "neutral_count": nli_results.get("neutral_count", 0),
        "contradiction_count": nli_results.get("contradiction_count", 0),
        "retrieval": telemetry,
        "grounded": (nli_results.get("grounding_level") in ["Strongly Supported", "Partially Supported"]),
        "citations": structured_citations
    }
