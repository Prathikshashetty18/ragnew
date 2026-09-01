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
    SIMILARITY_THRESHOLD_PARTIAL
)

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
                    
                    # Reconstruct embeddings array in memory
                    if _faiss_index.ntotal > 0:
                        print(f"Reconstructing {_faiss_index.ntotal} embeddings from FAISS...")
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
                # Initialize new L2 or Inner Product index. We'll use Inner Product with normalized vectors (cosine similarity).
                # all-MiniLM-L6-v2 dimension is 384
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

# Simple utility to split text into sentences
def split_into_sentences(text):
    # Regex splits by . ! ? followed by space and capital letter or end of string
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]

# Simple Character-based Text Splitter with Overlap
def chunk_text(text, pdf_name, page_number, chunk_size=500, chunk_overlap=100, doc_id=None, scope="knowledge_base", patient_id=None):
    chunks = []
    # Let's clean up whitespace
    clean_text = re.sub(r'\s+', ' ', text).strip()
    
    start = 0
    while start < len(clean_text):
        end = start + chunk_size
        chunk_content = clean_text[start:end]
        
        # Try to break at a space boundary if possible
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
            "patient_id": patient_id
        })
        
        start += (chunk_size - chunk_overlap)
        if start >= len(clean_text) or chunk_size >= len(clean_text):
            break
            
    return chunks

def process_pdf(file_path: str, filename: str, doc_id: int = None, scope: str = "knowledge_base", patient_id: str = None) -> int:
    """Extracts text page-by-page, chunks it, embeds it, and stores in FAISS with metadata."""
    print(f"Processing PDF: {filename} from {file_path} (scope={scope}, patient={patient_id})")
    reader = PdfReader(file_path)
    all_chunks = []
    
    # 1. Ingest page by page
    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        page_text = page.extract_text() or ""
        if page_text.strip():
            # 2. Chunk text with metadata
            page_chunks = chunk_text(page_text, filename, page_num, doc_id=doc_id, scope=scope, patient_id=patient_id)
            all_chunks.extend(page_chunks)
            
    if not all_chunks:
        print("No text extracted from PDF.")
        return 0
        
    print(f"Extracted {len(all_chunks)} chunks from {filename}.")
    
    # 3. Generate embeddings
    embedder = get_embedding_model()
    texts = [chunk["text"] for chunk in all_chunks]
    
    # Encode and normalize embeddings (for cosine similarity using Inner Product)
    embeddings = embedder.encode(texts, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")
    faiss.normalize_L2(embeddings)
    
    # 4. Store in FAISS
    index, metadata, embed_arr = get_vector_store()
    index.add(embeddings)
    metadata.extend(all_chunks)
    
    # Update embeddings array in memory
    global _embeddings_array
    if _embeddings_array is None:
        _embeddings_array = embeddings
    else:
        _embeddings_array = np.vstack([_embeddings_array, embeddings])
    
    save_vector_store(index, metadata)
    return len(all_chunks)

def call_groq_llm(prompt: str) -> str:
    """Helper to query Llama 3.3 model using Groq API."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a clinical decision support system. Answer the medical question using the provided context. Be precise, professional, and base your answers strictly on the context provided."},
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
    """Call Gemini API via http.client if Groq is not available but GEMINI/GOOGLE API key is."""
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
    """Creates a mock RAG answer strictly from sentences in retrieved chunks if no LLM key is configured."""
    print("No API Key detected. Using mock RAG response generator.")
    sentences = []
    for chunk in retrieved_chunks:
        sentences.extend(split_into_sentences(chunk["text"]))
        
    # Match key query words
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
        answer = " Based on the uploaded medical documents: " + " ".join(answer_parts)
    else:
        answer = "No matching references found in context. General recommendation: please verify with clinical guidelines."
        
    return answer

# Lightweight Python BM25 implementation
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
            # Standard BM25 IDF formula
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

def query_pipeline(query: str, filters: dict = None, direct_llm: bool = False) -> dict:
    """Executes search (with filters, FAISS+BM25, RRF hybrid), reranking, generation, verification, and confidence assessment."""
    index, metadata, embeddings_array = get_vector_store()
    
    if len(metadata) == 0 and not direct_llm:
        return {
            "answer": "No clinical documents have been uploaded to the system yet. Please upload a medical guideline PDF to enable Retrieval-Augmented Generation.",
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "evidence": [],
            "verification_results": []
        }
        
    # DIRECT LLM Mode
    if direct_llm:
        prompt = f"""You are a clinical decision support system. The user is asking a medical question.
Please answer it directly using your general medical knowledge.
IMPORTANT: Clearly label your answer as a direct LLM response without retrieved document evidence.

USER QUESTION:
{query}

CLINICAL RESPONSE (DIRECT LLM):"""
        
        answer = ""
        using_mock = False
        
        # Try LLM APIs
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

    # STRICT RAG Mode with Scoped Filtering
    # 1. Filter chunks by scope
    filtered_chunks_with_indices = []
    for idx, chunk in enumerate(metadata):
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
                doc_id = filters.get("document_id")
                # Handle both int and string comparisons
                if str(chunk.get("document_id")) != str(doc_id):
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
            "answer": f"No relevant context could be retrieved for the {scope_desc} scope. Please upload relevant guidelines or reports.",
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "evidence": [],
            "verification_results": []
        }

    # 2. Get Semantic Similarity Scores (FAISS)
    embedder = get_embedding_model()
    query_vector = embedder.encode([query])
    query_vector = np.array(query_vector).astype("float32")
    faiss.normalize_L2(query_vector)

    filtered_indices = [idx for idx, _ in filtered_chunks_with_indices]
    
    # Load / Reconstruct embeddings array if needed
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

    # 3. Get Keyword Scores (BM25)
    query_terms = re.findall(r'\w+', query.lower())
    filtered_chunks = [item[1] for item in filtered_chunks_with_indices]
    bm25 = BM25Retriever(filtered_chunks)
    bm25_scores = bm25.get_scores(query_terms)

    # 4. Hybrid Scoring using Reciprocal Rank Fusion (RRF)
    # Sort semantic and BM25 scores descending to get ranks
    semantic_rank_indices = np.argsort(semantic_scores)[::-1]
    bm25_rank_indices = np.argsort(bm25_scores)[::-1]

    semantic_ranks = {idx: rank + 1 for rank, idx in enumerate(semantic_rank_indices)}
    bm25_ranks = {idx: rank + 1 for rank, idx in enumerate(bm25_rank_indices)}

    rrf_scores = []
    for idx in range(len(filtered_chunks)):
        bm25_rank = bm25_ranks[idx] if bm25_scores[idx] > 0 else 1e9
        sem_rank = semantic_ranks[idx]
        
        # RRF formula (k=60)
        rrf_score = 1.0 / (60 + sem_rank) + 1.0 / (60 + bm25_rank)
        rrf_scores.append(rrf_score)

    # Sort chunks by hybrid RRF score
    sorted_indices = np.argsort(rrf_scores)[::-1]
    top_k_indices = sorted_indices[:5]
    
    top_chunks = []
    for idx in top_k_indices:
        chunk = filtered_chunks[idx].copy()
        chunk["retrieval_score"] = float(semantic_scores[idx])
        chunk["bm25_score"] = float(bm25_scores[idx])
        top_chunks.append(chunk)

    # 5. Rerank using Cross-Encoder
    cross_encoder = get_cross_encoder_model()
    pairs = [[query, c["text"]] for c in top_chunks]
    rerank_scores = cross_encoder.predict(pairs)
    
    # Sort by rerank score descending
    for i, score in enumerate(rerank_scores):
        top_chunks[i]["rerank_score"] = float(score)
        
    top_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    # 6. Context construction & Answer Generation
    context_passages = []
    for c in top_chunks:
        scope_label = "PATIENT DOCUMENT" if c.get("scope") == "patient" else "HOSPITAL KNOWLEDGE BASE"
        passage = f"Scope: {scope_label}\nSource: {c['pdf_name']} (Page {c['page_number']})\nContent: {c['text']}"
        context_passages.append(passage)
        
    context_text = "\n\n".join(context_passages)
    
    prompt = f"""Use the following medical context passages to answer the user's clinical query.
Your answer must be accurate, clinical, and directly supported by the context.
Do not introduce outside knowledge or exaggerate findings. If the context does not contain the answer, say so.

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

    # 7. Sentence-Level Answer Verification
    response_sentences = split_into_sentences(answer)
    
    context_sentences_metadata = []
    for chunk in top_chunks:
        c_sents = split_into_sentences(chunk["text"])
        for s in c_sents:
            context_sentences_metadata.append({
                "text": s,
                "pdf_name": chunk["pdf_name"],
                "page_number": chunk["page_number"]
            })
            
    verification_results = []
    evidence = []
    unsupported_count = 0
    total_score_sum = 0.0
    
    if response_sentences and context_sentences_metadata:
        resp_embeddings = embedder.encode(response_sentences)
        ctx_embeddings = embedder.encode([item["text"] for item in context_sentences_metadata])
        
        # Normalize
        resp_embeddings = resp_embeddings / np.linalg.norm(resp_embeddings, axis=1, keepdims=True)
        ctx_embeddings = ctx_embeddings / np.linalg.norm(ctx_embeddings, axis=1, keepdims=True)
        
        similarity_matrix = np.dot(resp_embeddings, ctx_embeddings.T)
        
        for r_idx, r_sent in enumerate(response_sentences):
            best_ctx_idx = int(np.argmax(similarity_matrix[r_idx]))
            max_sim = float(similarity_matrix[r_idx][best_ctx_idx])
            best_ctx = context_sentences_metadata[best_ctx_idx]
            
            if max_sim >= SIMILARITY_THRESHOLD_SUPPORTED:
                status = "Supported"
            elif max_sim >= SIMILARITY_THRESHOLD_PARTIAL:
                status = "Partially Supported"
            else:
                status = "Unsupported"
                unsupported_count += 1
                
            total_score_sum += max_sim
            
            verification_entry = {
                "sentence": r_sent,
                "status": status,
                "score": max_sim,
                "source_sentence": best_ctx["text"],
                "pdf_name": best_ctx["pdf_name"],
                "page_number": best_ctx["page_number"]
            }
            verification_results.append(verification_entry)
            
            if status != "Unsupported":
                evidence_entry = {
                    "pdf_name": best_ctx["pdf_name"],
                    "page_number": best_ctx["page_number"],
                    "supporting_text": best_ctx["text"],
                    "response_sentence": r_sent
                }
                if not any(e["supporting_text"] == best_ctx["text"] for e in evidence):
                    evidence.append(evidence_entry)
    else:
        for s in response_sentences:
            verification_results.append({
                "sentence": s,
                "status": "Unsupported",
                "score": 0.0,
                "source_sentence": "",
                "pdf_name": "N/A",
                "page_number": 0
            })
        unsupported_count = len(response_sentences)
        
    # 8. Confidence Score & Level calculation
    if len(response_sentences) > 0:
        avg_verification_score = total_score_sum / len(response_sentences)
    else:
        avg_verification_score = 0.0
        
    avg_retrieval_score = sum(c.get("retrieval_score", 0.0) for c in top_chunks) / len(top_chunks) if top_chunks else 0.0
    confidence_score = (avg_verification_score * 0.7) + (avg_retrieval_score * 0.3)
    
    if unsupported_count > 0 or len(metadata) == 0:
        confidence_level = "Low"
    elif confidence_score >= 0.75:
        confidence_level = "High"
    elif confidence_score >= 0.55:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # STRICT RAG Fallback: If low confidence or has unsupported statements, show 'I don't know' fallback
    if confidence_level == "Low" and not using_mock:
        answer = "I do not have sufficient evidence in the retrieved documents to answer this question. (Note: RAG grounds responses in retrieved evidence and reduces unsupported generation. The retrieved sources did not contain enough direct support to verify this answer safely.)"
        verification_results = []
        evidence = []
        
    return {
        "answer": answer,
        "confidence_level": confidence_level,
        "confidence_score": float(round(confidence_score, 2)),
        "evidence": evidence,
        "verification_results": verification_results,
        "using_mock": using_mock
    }
