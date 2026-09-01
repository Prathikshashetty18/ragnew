import os
import re
import pickle
import threading
import uuid
import math
from collections import Counter
import numpy as np
import faiss
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer, CrossEncoder
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
    NLI_CONTRADICTION_THRESHOLD
)
from app.nli_validator import validate_response_with_nli, filter_citations_by_permission

# Global variables to store models and indices in memory
_models_lock = threading.Lock()
_vector_store_lock = threading.Lock()

_embedding_model = None
_cross_encoder_model = None
_faiss_index = None
_chunks_metadata = []
_embeddings_array = None

def get_embedding_model():
    global _embedding_model
    with _models_lock:
        if _embedding_model is None:
            print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return _embedding_model

def get_cross_encoder_model():
    global _cross_encoder_model
    with _models_lock:
        if _cross_encoder_model is None:
            print(f"Loading Cross-Encoder model: {RERANK_MODEL_NAME}...")
            _cross_encoder_model = CrossEncoder(RERANK_MODEL_NAME)
        return _cross_encoder_model

def get_vector_store():
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

def save_vector_store(index, metadata):
    with _vector_store_lock:
        index_path = os.path.join(VECTOR_STORE_DIR, "vector_store.index")
        metadata_path = os.path.join(VECTOR_STORE_DIR, "chunks.pkl")
        
        faiss.write_index(index, index_path)
        with open(metadata_path, "wb") as f:
            pickle.dump(metadata, f)
        print("Saved FAISS index and metadata to disk.")

def remove_document_from_vector_store(doc_id: int):
    """Removes all chunks belonging to a document from the FAISS vector store and rebuilds the index."""
    global _faiss_index, _chunks_metadata, _embeddings_array
    with _vector_store_lock:
        _, metadata, _ = get_vector_store()
        
        retained_chunks = [c for c in metadata if c.get("document_id") != doc_id]
        if len(retained_chunks) == len(metadata):
            return  # No chunks removed
            
        print(f"Removing document ID {doc_id} from vector store. Rebuilding FAISS index with {len(retained_chunks)} chunks...")
        dimension = 384
        new_index = faiss.IndexFlatIP(dimension)
        
        if retained_chunks:
            embedder = get_embedding_model()
            texts = [c["text"] for c in retained_chunks]
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

def split_into_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]

def chunk_text(text, pdf_name, page_number, chunk_size=500, chunk_overlap=100, doc_id=None, scope="knowledge_base", patient_id=None, version="1.0", document_type="Guideline"):
    chunks = []
    clean_text = re.sub(r'\s+', ' ', text).strip()
    
    start = 0
    while start < len(clean_text):
        end = start + chunk_size
        chunk_content = clean_text[start:end]
        
        if end < len(clean_text):
            last_space = chunk_content.rfind(' ')
            if last_space != -1 and last_space > (chunk_size // 2):
                end = start + last_space
                chunk_content = clean_text[start:end]
        
        chunks.append({
            "id": str(uuid.uuid4()),
            "text": chunk_content,
            "pdf_name": pdf_name,
            "page_number": page_number,
            "document_id": doc_id,
            "scope": scope,
            "patient_id": patient_id,
            "version": version,
            "document_type": document_type,
            "status": "ACTIVE"
        })
        
        start += (chunk_size - chunk_overlap)
        if start >= len(clean_text) or chunk_size >= len(clean_text):
            break
            
    return chunks

def process_pdf(file_path: str, filename: str, doc_id: int = None, scope: str = "knowledge_base", patient_id: str = None, version: str = "1.0", document_type: str = "Guideline") -> int:
    """Extracts text page-by-page, chunks it, embeds it, and stores in FAISS with metadata."""
    print(f"Processing PDF: {filename} from {file_path} (scope={scope}, patient={patient_id}, version={version})")
    reader = PdfReader(file_path)
    all_chunks = []
    
    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        page_text = page.extract_text() or ""
        if page_text.strip():
            page_chunks = chunk_text(
                page_text,
                filename,
                page_num,
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
        
    print(f"Extracted {len(all_chunks)} chunks from {filename}.")
    
    embedder = get_embedding_model()
    texts = [chunk["text"] for chunk in all_chunks]
    
    embeddings = embedder.encode(texts, show_progress_bar=False)
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
    return len(all_chunks)

def call_groq_llm(prompt: str) -> str:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a hospital clinical decision support system. Answer the medical question using the provided context. Be precise, professional, and base your answers strictly on the context provided."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API call failed: {e}")
        raise e

def call_gemini_fallback(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("No Gemini/Google API Key found.")
        
    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "You are a clinical decision support system. Answer the medical question using the provided context. Be precise, professional, and base your answers strictly on the context provided.\n\n" + prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1024
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

def generate_mock_answer(query: str, retrieved_chunks: list) -> str:
    sentences = []
    for chunk in retrieved_chunks:
        sentences.extend(split_into_sentences(chunk["text"]))
        
    query_words = set(re.findall(r'\w+', query.lower()))
    matched_sentences = []
    for s in sentences:
        s_words = set(re.findall(r'\w+', s.lower()))
        common = query_words.intersection(s_words)
        if common:
            matched_sentences.append((len(common), s))
            
    matched_sentences.sort(key=lambda x: x[0], reverse=True)
    
    if matched_sentences:
        answer_parts = [item[1] for item in matched_sentences[:3]]
        answer = "Based on the verified clinical reference documents: " + " ".join(answer_parts)
    else:
        answer = "No matching reference was found in the authorized clinical documents. Please consult hospital protocols."
        
    return answer

class BM25Retriever:
    def __init__(self, corpus_chunks, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus = [re.findall(r'\w+', chunk["text"].lower()) for chunk in corpus_chunks]
        self.N = len(self.corpus)
        self.doc_lens = [len(doc) for doc in self.corpus]
        self.avgdl = sum(self.doc_lens) / self.N if self.N > 0 else 0
        self.doc_freqs = []
        self.idf = {}
        self.initialize()

    def initialize(self):
        nd = {}
        for doc in self.corpus:
            frequencies = Counter(doc)
            self.doc_freqs.append(frequencies)
            for word in frequencies:
                nd[word] = nd.get(word, 0) + 1
        
        for word, freq in nd.items():
            self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query_terms):
        scores = []
        for i, doc_freq in enumerate(self.doc_freqs):
            score = 0.0
            doc_len = self.doc_lens[i]
            for word in query_terms:
                if word in doc_freq:
                    freq = doc_freq[word]
                    idf_val = self.idf.get(word, 0.0)
                    numerator = freq * (self.k1 + 1)
                    denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                    score += idf_val * numerator / denominator
            scores.append(score)
        return scores

def query_pipeline(query: str, filters: dict = None, direct_llm: bool = False, user_role: str = "DOCTOR", active_doc_ids: set = None) -> dict:
    """Executes search (FAISS Top 20 + BM25, RRF hybrid), Cross-Encoder reranking (Top 5), Llama 3.3 70B generation, NLI validation, and permission-aware citations."""
    index, metadata, embeddings_array = get_vector_store()
    
    if len(metadata) == 0 and not direct_llm:
        return {
            "answer": "No active clinical documents have been indexed in the system yet. Please upload hospital guidelines to enable Retrieval-Augmented Generation.",
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "evidence": [],
            "verification_results": []
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
                        answer = "Direct LLM Mode: Groq/Gemini APIs are currently unavailable."
                        using_mock = True
                else:
                    answer = "Direct LLM Mode: Groq/Gemini APIs are currently unavailable."
                    using_mock = True
        else:
            gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if gemini_key:
                try:
                    answer = call_gemini_fallback(prompt)
                except Exception:
                    answer = "Direct LLM Mode: Gemini API is currently unavailable."
                    using_mock = True
            else:
                answer = "Direct LLM Mode: No API keys configured. LLM generation unavailable."
                using_mock = True
                
        return {
            "answer": answer,
            "confidence_level": "High" if not using_mock else "Low",
            "confidence_score": 1.0 if not using_mock else 0.0,
            "evidence": [],
            "verification_results": [],
            "using_mock": using_mock
        }

    # STRICT RAG Mode with Scoped & Active Document Filtering
    filtered_chunks_with_indices = []
    for idx, chunk in enumerate(metadata):
        # Lifecycle check: Ensure document is active if active_doc_ids filter is provided
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
            "evidence": [],
            "verification_results": []
        }

    # 2. FAISS Top 20 Candidates
    embedder = get_embedding_model()
    query_vector = embedder.encode([query])
    query_vector = np.array(query_vector).astype("float32")
    faiss.normalize_L2(query_vector)

    filtered_indices = [idx for idx, _ in filtered_chunks_with_indices]
    
    if embeddings_array is None:
        try:
            embeddings_array = index.reconstruct_n(0, index.ntotal)
        except AttributeError:
            embeddings_array = np.array([index.reconstruct(i) for i in range(index.ntotal)]).astype("float32")

    if embeddings_array is not None and len(filtered_indices) > 0:
        filtered_embeddings = embeddings_array[filtered_indices]
        semantic_scores = np.dot(filtered_embeddings, query_vector[0])
    else:
        semantic_scores = np.zeros(len(filtered_indices))

    # 3. BM25 Keyword Search
    query_terms = re.findall(r'\w+', query.lower())
    filtered_chunks = [item[1] for item in filtered_chunks_with_indices]
    bm25 = BM25Retriever(filtered_chunks)
    bm25_scores = bm25.get_scores(query_terms)

    # 4. RRF Fusion (Top 20 candidate pool)
    semantic_rank_indices = np.argsort(semantic_scores)[::-1]
    bm25_rank_indices = np.argsort(bm25_scores)[::-1]

    semantic_ranks = {idx: rank + 1 for rank, idx in enumerate(semantic_rank_indices)}
    bm25_ranks = {idx: rank + 1 for rank, idx in enumerate(bm25_rank_indices)}

    rrf_scores = []
    for idx in range(len(filtered_chunks)):
        bm25_rank = bm25_ranks[idx] if bm25_scores[idx] > 0 else 1e9
        sem_rank = semantic_ranks[idx]
        rrf_score = 1.0 / (60 + sem_rank) + 1.0 / (60 + bm25_rank)
        rrf_scores.append(rrf_score)

    sorted_indices = np.argsort(rrf_scores)[::-1]
    top_candidates_indices = sorted_indices[:min(20, len(sorted_indices))]
    
    candidate_chunks = []
    for idx in top_candidates_indices:
        chunk = filtered_chunks[idx].copy()
        chunk["retrieval_score"] = float(semantic_scores[idx])
        chunk["bm25_score"] = float(bm25_scores[idx])
        candidate_chunks.append(chunk)

    # 5. Cross-Encoder Reranking -> Select Top 5
    cross_encoder = get_cross_encoder_model()
    pairs = [[query, c["text"]] for c in candidate_chunks]
    rerank_scores = cross_encoder.predict(pairs)
    
    for i, score in enumerate(rerank_scores):
        candidate_chunks[i]["rerank_score"] = float(score)
        
    candidate_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
    top_chunks = candidate_chunks[:5]
    
    # 6. Context synthesis & Llama 3.3 70B generation
    context_passages = []
    for c in top_chunks:
        scope_label = "PATIENT RECORD" if c.get("scope") == "patient" else "HOSPITAL GUIDELINE"
        version_str = f" (Edition/Version: {c.get('version', '1.0')})" if c.get("version") else ""
        passage = f"[{scope_label}] Source: {c['pdf_name']}{version_str}, Page {c['page_number']}\nContent: {c['text']}"
        context_passages.append(passage)
        
    context_text = "\n\n".join(context_passages)
    
    prompt = f"""Use the following medical context passages to answer the user's clinical query.
Your answer must be accurate, clinical, and directly supported by the context.
Do not introduce outside knowledge or exaggerate findings. If the context does not contain the answer, state that clearly.

---
CONTEXT:
{context_text}
---
USER MEDICAL QUERY:
{query}

CLINICAL RESPONSE:"""

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
                    answer = generate_mock_answer(query, top_chunks)
                    using_mock = True
            else:
                answer = generate_mock_answer(query, top_chunks)
                using_mock = True
    else:
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if gemini_key:
            try:
                answer = call_gemini_fallback(prompt)
            except Exception:
                answer = generate_mock_answer(query, top_chunks)
                using_mock = True
        else:
            answer = generate_mock_answer(query, top_chunks)
            using_mock = True

    # 7. NLI Fact-Verification Engine
    nli_results = validate_response_with_nli(
        answer=answer,
        context_chunks=top_chunks,
        embedder=embedder,
        cross_encoder=cross_encoder,
        similarity_threshold_entailment=SIMILARITY_THRESHOLD_SUPPORTED,
        similarity_threshold_partial=SIMILARITY_THRESHOLD_PARTIAL
    )
    
    # 8. Role-Based Citation Filtering
    permitted_evidence = filter_citations_by_permission(nli_results["evidence"], user_role)
    
    # Fallback if Low confidence or contradictions detected
    final_answer = answer
    if nli_results["confidence_level"] == "Low" and not using_mock:
        if nli_results.get("contradiction_count", 0) > 0:
            final_answer = "The retrieved evidence contained conflicting or contradictory findings regarding this question. Please review the official hospital guideline documents directly."
        else:
            final_answer = "I do not have sufficient evidence in the retrieved documents to answer this question reliably. (Clinical safety safeguard: ungrounded claims are suppressed.)"
            
    return {
        "answer": final_answer,
        "confidence_level": nli_results["confidence_level"],
        "confidence_score": nli_results["confidence_score"],
        "evidence": permitted_evidence,
        "verification_results": nli_results["verification_results"],
        "using_mock": using_mock,
        "entailment_count": nli_results.get("entailment_count", 0),
        "neutral_count": nli_results.get("neutral_count", 0),
        "contradiction_count": nli_results.get("contradiction_count", 0)
    }
