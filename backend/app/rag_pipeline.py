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
_vector_store_lock = threading.RLock()

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
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    results = []
    for line in lines:
        sents = re.split(r'(?<=[a-zA-Z\)])(?<=[.!?])\s+', line)
        for s in sents:
            s_clean = s.strip()
            if len(s_clean) > 5:
                results.append(s_clean)
    if not results:
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        results = [s.strip() for s in sents if len(s.strip()) > 5]
    return results


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


def index_text_document(
    text: str,
    document_name: str,
    doc_id: Optional[int] = None,
    scope: str = "patient",
    patient_id: Optional[str] = None,
    version: str = "1.0",
    document_type: str = "clinical_report",
    report_id: Optional[int] = None
) -> int:
    """
    Extracts structured blocks from text document, applies hierarchical chunking with structural context,
    embeds contextualized chunks into FAISS, and updates the persistent BM25 index.
    """
    if not text or not text.strip():
        return 0

    chunker = HierarchicalClinicalChunker(chunk_size=RAG_CHUNK_SIZE, chunk_overlap=RAG_CHUNK_OVERLAP)
    chunks = chunker.chunk_document(
        text=text,
        pdf_name=document_name,
        page_number=1,
        doc_id=doc_id,
        scope=scope,
        patient_id=patient_id,
        version=version,
        document_type=document_type
    )

    if not chunks:
        return 0

    if report_id:
        for c in chunks:
            c["report_id"] = report_id

    embedder = get_embedding_model()
    contextualized_texts = [chunk.get("contextualized_text") or chunk["text"] for chunk in chunks]

    embeddings = embedder.encode(contextualized_texts, show_progress_bar=False)
    embeddings = np.array(embeddings).astype("float32")
    faiss.normalize_L2(embeddings)

    with _vector_store_lock:
        index, metadata, embed_arr = get_vector_store()
        index.add(embeddings)
        metadata.extend(chunks)

        global _embeddings_array
        if _embeddings_array is None:
            _embeddings_array = embeddings
        else:
            _embeddings_array = np.vstack([_embeddings_array, embeddings])

        save_vector_store(index, metadata)

    # Update persistent BM25 index
    bm25 = get_bm25_index()
    bm25.add_chunks(chunks)

    print(f"Indexed text document '{document_name}' (doc_id={doc_id}, scope={scope}, patient={patient_id}): {len(chunks)} chunks.")
    return len(chunks)


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

DEFAULT_DIRECT_LLM_SYSTEM_PROMPT = (
    "You are an expert clinical medical assistant. Answer the medical question directly, thoroughly, and professionally "
    "using general clinical medical knowledge and evidence-based medicine principles. Format your answer cleanly and elegantly in markdown."
)


def call_groq_llm(prompt: str, max_tokens: int = 4096, system_prompt: Optional[str] = None) -> str:
    try:
        sys_content = system_prompt or DEFAULT_STRICT_RAG_SYSTEM_PROMPT
        client = Groq(api_key=GROQ_API_KEY, timeout=30.0)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": sys_content
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3 if system_prompt == DEFAULT_DIRECT_LLM_SYSTEM_PROMPT else 0.05,
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


def is_historical_patient_query(query: str) -> bool:
    """
    Detects if the query explicitly asks for historical reports, previous values,
    trends over time, or report comparisons.
    """
    q_lower = query.lower()
    historical_patterns = [
        r'\b(?:previous|prior|earlier|old|older|past|initial|baseline|first)\b',
        r'\b(?:history|historical|progression|trend|timeline|evolution)\b',
        r'\b(?:compare|comparison|difference|differences|changed|change|changes)\b',
        r'\b(?:report\s*(?:1|2|3|4|5|6|7|8|9|one|two|three|four|five|six|seven))\b',
        r'\b(?:previous\s*report|prior\s*report|earlier\s*report|old\s*report)\b'
    ]
    for pat in historical_patterns:
        if re.search(pat, q_lower):
            return True
    return False


def get_patient_active_reports(patient_id: str, db: Optional[Any] = None) -> List[Any]:
    """
    Retrieves active (non-archived) ClinicalReport records for a patient,
    sorted newest first (created_at DESC, id DESC).
    """
    close_db = False
    if db is None:
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            close_db = True
        except Exception:
            return []
    try:
        from app.database import ClinicalReport
        reports = db.query(ClinicalReport).filter(
            ClinicalReport.patient_id == patient_id,
            ClinicalReport.status != 'ARCHIVED'
        ).order_by(ClinicalReport.created_at.desc(), ClinicalReport.id.desc()).all()
        return reports
    except Exception as e:
        print(f"Error fetching active reports for patient {patient_id}: {e}")
        return []
    finally:
        if close_db and db:
            db.close()


def generate_mock_answer(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    Generates a structured, evidence-grounded clinical response cleanly tailored
    to the clinician's specific question using retrieved evidence chunks.
    """
    if not retrieved_chunks:
        return "Insufficient evidence in the hospital knowledge base to answer this question reliably."

    metadata_header_patterns = [
        r'^(?:REPORT ID|STATUS|DATE GENERATED|PATIENT ID|PATIENT NAME|AGE|GENDER|DEPARTMENT|ATTENDING DOCTOR|CREATED):',
        r'^#+\s*CLINICAL PATIENT REPORT',
        r'^#+\s*HOSPITAL APPROVED CLINICAL PRACTICE GUIDELINE',
        r'^DOCUMENT REF:',
        r'^APPROVAL COMMITTEE:',
        r'^SECTION \d+:',
        r'^\d+\.\d+\s+(?:DIAGNOSTIC CRITERIA|EMPIRICAL ANTIMICROBIAL THERAPY|RISK STRATIFICATION|MONITORING|CLINICAL SUSPICION):?'
    ]

    q_lower = query.lower()
    q_words = set(re.findall(r'\w+', q_lower)) - {
        "what", "is", "are", "the", "for", "and", "in", "to", "of", "a", "an",
        "was", "were", "did", "show", "give", "report", "patient", "clinical",
        "tell", "me", "about", "please", "can", "you", "does", "have", "with",
        "guideline", "guidelines", "protocol", "protocols"
    }

    # Helper: Clean document header / metadata text
    def clean_clinical_text(text_str: str) -> str:
        s = text_str.strip()
        # Drop entire line if it contains document/report header metadata
        if re.search(r'\b(?:REPORT ID|PATIENT ID|ATTENDING DOCTOR|APPROVAL COMMITTEE|DOCUMENT REF)\b', s, re.IGNORECASE):
            return ""
        if re.search(r'^#+\s*(?:CLINICAL PATIENT REPORT|HOSPITAL APPROVED)', s, re.IGNORECASE):
            return ""
        if re.search(r'^(?:STATUS|CREATED|PATIENT NAME|DEPARTMENT|AGE|GENDER):\s*', s, re.IGNORECASE):
            return ""
        # Drop publisher / journal headers, volume/issue headers, ISSN, and web links
        if re.search(r'(?:www\.[a-z0-9\-]+\.[a-z]+|http[s]?://\S+|©\s*\d{4}|\bISSN:\s*[0-9\-]+|\bVolume\s+\d+,\s*Issue\s+\d+|\bIJCRT\w*)', s, re.IGNORECASE):
            s = re.sub(r'(?:www\.[a-z0-9\-]+\.[a-z]+|http[s]?://\S+|©\s*\d{4}|\bISSN:\s*[0-9\-]+|\bVolume\s+\d+,\s*Issue\s+\d+|\bIJCRT\w*)', '', s, flags=re.IGNORECASE).strip(' -–—|:,')
            if len(re.sub(r'[^a-zA-Z0-9]', '', s)) < 8:
                return ""
        for pat in metadata_header_patterns:
            s = re.sub(pat, '', s, flags=re.IGNORECASE).strip()
        # Clean leading markdown headers or colons
        s = re.sub(r'^(?:#+\s*)+', '', s).strip()
        s = re.sub(r'^(?:OBSERVATIONS\s*(?:&|AND)?\s*VITALS|INVESTIGATIONS\s*(?:&|AND)?\s*LABS|CLINICAL ASSESSMENT\s*(?:&|AND)?\s*DIAGNOSIS|RECOMMENDATIONS\s*(?:&|AND)?\s*TREATMENT PLAN|CHIEF COMPLAINT|CLINICAL HISTORY):\s*', '', s, flags=re.IGNORECASE).strip()
        # Clean leading bullet symbols or list numbers so bullets are never doubled ("- - ")
        s = re.sub(r'^(?:[-*•]|\d+[.)])\s*', '', s).strip()
        return s

    # Detect clinical dimension intent
    has_vitals_intent = bool(re.search(r'\b(vital|vitals|signs|observation|observations|temp|temperature|bp|blood pressure|pulse|heart rate|spo2|oxygen|fever)\b', q_lower))
    has_labs_intent = bool(re.search(r'\b(lab|labs|investigation|investigations|blood|hemoglobin|wbc|platelets|crp|radiology|xray|x-ray|chest|ct|imaging|scan|infiltrate|consolidation)\b', q_lower))
    has_assessment_intent = bool(re.search(r'\b(assessment|diagnosis|diagnosed|curb|curb-65|severity|condition)\b', q_lower))
    has_treatment_intent = bool(re.search(r'\b(treatment|plan|recommendation|recommendations|medication|antibiotic|antimicrobial|dosage|dose|ceftriaxone|amoxicillin|azithromycin|discharge|monitoring|therapy|prescribe)\b', q_lower))
    has_complaint_intent = bool(re.search(r'\b(complaint|chief|symptom|symptoms|history|presenting|cough|chest pain|dyspnea)\b', q_lower))
    is_general_summary = bool(re.search(r'\b(summarize|summary|overview|entire report|whole report|full report)\b', q_lower))

    # Extract patient metadata if available from retrieved chunks
    patient_info = {}
    for chunk in retrieved_chunks:
        c_text = chunk.get("text", "")
        if "patient_name" in chunk and chunk["patient_name"]:
            patient_info["name"] = chunk["patient_name"]
        else:
            m_name = re.search(r'(?:PATIENT NAME|PATIENT|Patient):\s*([^\n,|]+)', c_text, re.IGNORECASE)
            if m_name and "name" not in patient_info:
                patient_info["name"] = m_name.group(1).strip()

        m_age = re.search(r'(?:AGE|Age):\s*(\d+)', c_text, re.IGNORECASE)
        if m_age and "age" not in patient_info:
            patient_info["age"] = f"{m_age.group(1).strip()} years"

        m_gender = re.search(r'(?:GENDER|Gender|Sex):\s*([^\n,|]+)', c_text, re.IGNORECASE)
        if m_gender and "gender" not in patient_info:
            g_str = m_gender.group(1).strip()
            if g_str.lower().startswith("m"):
                patient_info["gender"] = "Male"
            elif g_str.lower().startswith("f"):
                patient_info["gender"] = "Female"
            else:
                patient_info["gender"] = g_str

        m_dept = re.search(r'(?:DEPARTMENT|Department):\s*([^\n,|]+)', c_text, re.IGNORECASE)
        if m_dept and "dept" not in patient_info:
            patient_info["dept"] = m_dept.group(1).strip()

    # 1. Collect candidate statements categorized by topic
    # Each entry: (statement, ref_id, chunk_score)
    categorized_facts: Dict[str, List[Tuple[str, int, float]]] = {
        "observations": [],
        "investigations": [],
        "assessment": [],
        "treatment": [],
        "complaint": [],
        "guideline_statements": []
    }

    for idx, chunk in enumerate(retrieved_chunks):
        ref_id = idx + 1
        chunk_score = chunk.get("rerank_score", chunk.get("dense_score", 1.0 / (idx + 1)))
        text = chunk.get("text", "")
        sec_name = chunk.get("section", "").upper()

        raw_lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in raw_lines:
            clean = clean_clinical_text(line)
            if not clean or len(clean) < 4:
                continue

            # Check if this is a patient observation/vitals line
            if "OBSERVATION" in sec_name or "VITAL" in sec_name or "Latest Vitals:" in line or "BP:" in line:
                vitals_match = re.search(r'BP:\s*([^,]+),\s*Pulse:\s*([^,]+),\s*Temp:\s*([^,]+),\s*SpO2:\s*([^\.]+)', line)
                if vitals_match:
                    bp, pulse, temp, spo2 = vitals_match.groups()
                    categorized_facts["observations"].append((f"Blood pressure: {bp.strip()}", ref_id, chunk_score))
                    categorized_facts["observations"].append((f"Pulse: {pulse.strip()}", ref_id, chunk_score))
                    categorized_facts["observations"].append((f"Temperature: {temp.strip()}", ref_id, chunk_score))
                    categorized_facts["observations"].append((f"SpO2: {spo2.strip()}", ref_id, chunk_score))

                notes_match = re.search(r'Notes:\s*(.*)', line)
                if notes_match:
                    notes_text = notes_match.group(1).strip()
                    for n_sent in re.split(r'(?<=[.!?])\s+', notes_text):
                        n_clean = n_sent.strip().rstrip(".")
                        if n_clean:
                            categorized_facts["observations"].append((n_clean, ref_id, chunk_score))
                elif not vitals_match:
                    categorized_facts["observations"].append((clean, ref_id, chunk_score))

            elif "INVESTIGATION" in sec_name or "LAB" in sec_name or "RADIOLOGY" in sec_name or "Hemoglobin:" in line or "CBC" in line:
                if "Radiology:" in line:
                    rad_parts = line.split("Radiology:")
                    lab_part = clean_clinical_text(rad_parts[0])
                    rad_part = clean_clinical_text(rad_parts[1])
                    if lab_part:
                        categorized_facts["investigations"].append((lab_part, ref_id, chunk_score))
                    if rad_part:
                        categorized_facts["investigations"].append((f"Radiology: {rad_part}", ref_id, chunk_score))
                else:
                    categorized_facts["investigations"].append((clean, ref_id, chunk_score))

            elif "ASSESSMENT" in sec_name or "DIAGNOSIS" in sec_name or "Assessment:" in line:
                categorized_facts["assessment"].append((clean, ref_id, chunk_score))

            elif "RECOMMENDATION" in sec_name or "TREATMENT" in sec_name or "ANTIMICROBIAL" in sec_name:
                if re.search(r'^\d+\.\s+', clean):
                    for item in re.split(r'(?=\b\d+\.\s+)', clean):
                        it_clean = clean_clinical_text(item).rstrip(".")
                        if it_clean:
                            categorized_facts["treatment"].append((it_clean, ref_id, chunk_score))
                else:
                    for item in re.split(r'(?=\s*-\s+[A-Za-z])', clean):
                        it_clean = clean_clinical_text(item).rstrip(".")
                        if it_clean:
                            categorized_facts["treatment"].append((it_clean, ref_id, chunk_score))

            elif "CHIEF COMPLAINT" in sec_name or "CLINICAL HISTORY" in sec_name:
                categorized_facts["complaint"].append((clean, ref_id, chunk_score))

            else:
                # Guideline protocol or generic text
                for s in re.split(r'(?<=[.!?])\s+', clean):
                    s_clean = clean_clinical_text(s)
                    if len(s_clean) > 8:
                        categorized_facts["guideline_statements"].append((s_clean, ref_id, chunk_score))

    # 2. Assemble focused answer according to query intent
    result_blocks = []

    # CASE 0: Comparative / Historical Query across multiple reports
    is_historical = is_historical_patient_query(query)
    distinct_reports = {}
    for idx, c in enumerate(retrieved_chunks):
        rep_name = c.get("pdf_name", "Clinical Report")
        if rep_name not in distinct_reports:
            distinct_reports[rep_name] = []
        distinct_reports[rep_name].append((idx + 1, c))

    if is_historical and len(distinct_reports) > 1 and not is_general_summary:
        comp_blocks = ["### Clinical Report Comparison\n"]
        for rep_name, c_list in distinct_reports.items():
            m_rep = re.search(r'Report(\d+)', rep_name)
            rep_label = f"Report {m_rep.group(1)}" if m_rep else rep_name
            lines = [f"#### {rep_label}"]
            seen = set()
            for ref_id, chunk in c_list:
                c_text = chunk.get("text", "")
                for raw_line in c_text.split("\n"):
                    clean = clean_clinical_text(raw_line)
                    if not clean or len(clean) < 4 or any(clean.upper().startswith(p) for p in ["REPORT ID", "STATUS", "PATIENT ID", "CREATED"]):
                        continue
                    norm = clean.lower()
                    if norm in seen:
                        continue
                    seen.add(norm)
                    if has_vitals_intent and any(k in norm for k in ["blood pressure", "bp:", "pulse:", "temp:", "spo2:", "vitals"]):
                        v_match = re.match(r'^(Blood pressure|Pulse|Temperature|SpO2|Notes):\s*(.*)', clean, re.IGNORECASE)
                        if v_match:
                            lines.append(f"- **{v_match.group(1)}:** {v_match.group(2)} [{ref_id}]")
                        else:
                            lines.append(f"- {clean} [{ref_id}]")
                    elif has_treatment_intent and any(k in norm for k in ["mg", "daily", "therapy", "antimicrobial", "ceftriaxone", "treatment", "monitor"]):
                        lines.append(f"- {clean} [{ref_id}]")
                    elif has_assessment_intent and any(k in norm for k in ["diagnosis", "assessment", "acute", "pneumonia"]):
                        lines.append(f"- {clean} [{ref_id}]")
                    elif not (has_vitals_intent or has_treatment_intent or has_assessment_intent or has_labs_intent):
                        lines.append(f"- {clean} [{ref_id}]")
            if len(lines) > 1:
                comp_blocks.append("\n".join(lines[:6]))
        if len(comp_blocks) > 1:
            result_blocks.append("\n\n".join(comp_blocks))

    # CASE 1: Query specifically asks about Observations & Vitals
    if not result_blocks and has_vitals_intent and not is_general_summary:
        obs_list = categorized_facts["observations"]
        if obs_list:
            seen = set()
            lines = ["### Observations & Vital Signs\n"]
            for item, ref_id, _ in obs_list:
                norm = item.lower()
                if norm not in seen:
                    seen.add(norm)
                    v_match = re.match(r'^(Blood pressure|Pulse|Temperature|SpO2|Notes|Radiology|Hemoglobin|WBC|Platelets|Creatinine|CRP):\s*(.*)', item, re.IGNORECASE)
                    if v_match:
                        lines.append(f"- **{v_match.group(1)}:** {v_match.group(2)} [{ref_id}]")
                    else:
                        lines.append(f"- {item} [{ref_id}]")
            result_blocks.append("\n".join(lines))

    # CASE 2: Query specifically asks about Labs / Investigations / Radiology
    elif not result_blocks and has_labs_intent and not is_general_summary:
        inv_list = categorized_facts["investigations"]
        if inv_list:
            seen = set()
            lines = ["### Investigations & Diagnostic Findings\n"]
            for item, ref_id, _ in inv_list:
                norm = item.lower()
                if norm not in seen:
                    seen.add(norm)
                    v_match = re.match(r'^(Blood pressure|Pulse|Temperature|SpO2|Notes|Radiology|Hemoglobin|WBC|Platelets|Creatinine|CRP):\s*(.*)', item, re.IGNORECASE)
                    if v_match:
                        lines.append(f"- **{v_match.group(1)}:** {v_match.group(2)} [{ref_id}]")
                    else:
                        lines.append(f"- {item} [{ref_id}]")
            result_blocks.append("\n".join(lines))

    # CASE 3: Query specifically asks about Assessment / Diagnosis
    elif not result_blocks and has_assessment_intent and not is_general_summary:
        ass_list = categorized_facts["assessment"]
        if ass_list:
            seen = set()
            lines = ["### Clinical Assessment & Diagnosis\n"]
            for item, ref_id, _ in ass_list:
                norm = item.lower()
                if norm not in seen:
                    seen.add(norm)
                    lines.append(f"- {item} [{ref_id}]")
            result_blocks.append("\n".join(lines))

    # CASE 4: Query specifically asks about Treatment / Recommendations / Antimicrobial Guidelines
    elif not result_blocks and has_treatment_intent and not is_general_summary:
        tx_list = categorized_facts["treatment"] + [
            (s, r, sc) for s, r, sc in categorized_facts["guideline_statements"]
            if any(w in s.lower() for w in ["therapy", "dose", "antimicrobial", "ceftriaxone", "amoxicillin", "mg", "daily", "admission", "icu", "discharge"])
        ]
        if tx_list:
            scored_tx = []
            seen = set()
            for item, ref_id, chunk_sc in tx_list:
                norm = item.lower()
                if norm in seen:
                    continue
                seen.add(norm)
                item_words = set(re.findall(r'\w+', norm))
                overlap = len(q_words.intersection(item_words))
                if "severe" in q_lower and ("severe" in norm or "icu" in norm):
                    overlap += 3
                if "outpatient" in q_lower and "outpatient" in norm:
                    overlap += 3
                if "inpatient" in q_lower and "inpatient" in norm:
                    overlap += 2
                scored_tx.append((overlap, chunk_sc, item, ref_id))

            scored_tx.sort(key=lambda x: (x[0], x[1]), reverse=True)
            lines = ["### Treatment Recommendations & Guidelines\n"]
            for _, _, item, ref_id in scored_tx[:4]:
                lines.append(f"- {item} [{ref_id}]")
            result_blocks.append("\n".join(lines))

    # CASE 5: General Summary of patient or report
    elif not result_blocks and is_general_summary:
        summary_blocks = []
        header_lines = ["### Clinical Patient Report\n"]
        meta_lines = []
        if "name" in patient_info:
            meta_lines.append(f"**Patient:** {patient_info['name']}  ")
        if "age" in patient_info:
            meta_lines.append(f"**Age:** {patient_info['age']}  ")
        if "gender" in patient_info:
            meta_lines.append(f"**Gender:** {patient_info['gender']}  ")
        if "dept" in patient_info:
            meta_lines.append(f"**Department:** {patient_info['dept']}  ")
        if meta_lines:
            header_lines.append("\n".join(meta_lines) + "\n")
        summary_blocks.append("".join(header_lines).strip())

        if categorized_facts["complaint"]:
            lines = ["#### Chief Complaint & History"]
            for item, ref_id, _ in categorized_facts["complaint"][:2]:
                lines.append(f"- {item} [{ref_id}]")
            summary_blocks.append("\n".join(lines))

        if categorized_facts["observations"]:
            lines = ["#### Observations & Vital Signs"]
            seen = set()
            obs_items = []
            for item, ref_id, _ in categorized_facts["observations"][:6]:
                norm = item.lower()
                if norm not in seen:
                    seen.add(norm)
                    v_match = re.match(r'^(Blood pressure|Pulse|Temperature|SpO2):\s*(.*)', item, re.IGNORECASE)
                    if v_match:
                        obs_items.append(f"- **{v_match.group(1)}:** {v_match.group(2)} [{ref_id}]")
                    else:
                        obs_items.append(f"- {item} [{ref_id}]")
            if obs_items:
                lines.extend(obs_items)
            summary_blocks.append("\n".join(lines))

        if categorized_facts["investigations"]:
            lines = ["#### Investigations & Diagnostics"]
            seen = set()
            inv_items = []
            for item, ref_id, _ in categorized_facts["investigations"][:3]:
                norm = item.lower()
                if norm not in seen:
                    seen.add(norm)
                    if "radiology:" in norm:
                        inv_items.append(f"- **Radiology:** {re.sub(r'^radiology:\s*', '', item, flags=re.IGNORECASE)} [{ref_id}]")
                    else:
                        inv_items.append(f"- **Laboratory Panel:** {item} [{ref_id}]")
            if inv_items:
                lines.extend(inv_items)
            summary_blocks.append("\n".join(lines))

        if categorized_facts["assessment"]:
            lines = ["#### Clinical Assessment"]
            for item, ref_id, _ in categorized_facts["assessment"][:2]:
                lines.append(f"- {item} [{ref_id}]")
            summary_blocks.append("\n".join(lines))

        if categorized_facts["treatment"]:
            lines = ["#### Recommendations & Treatment Plan"]
            for item, ref_id, _ in categorized_facts["treatment"][:3]:
                lines.append(f"- {item} [{ref_id}]")
            summary_blocks.append("\n".join(lines))

        result_blocks.append("\n\n".join(summary_blocks))

    # CASE 6: Specific Question / Guidelines Question (fallback across all sentences)
    if not result_blocks:
        all_candidates = []
        for idx, chunk in enumerate(retrieved_chunks):
            ref_id = idx + 1
            chunk_sc = chunk.get("rerank_score", chunk.get("dense_score", 1.0 / (idx + 1)))
            text = chunk.get("text", "")
            for raw_line in text.split("\n"):
                clean = clean_clinical_text(raw_line)
                if not clean or len(clean) < 10:
                    continue
                for sent in re.split(r'(?<=[.!?])\s+', clean):
                    s_clean = sent.strip().rstrip(".")
                    if len(s_clean) < 10:
                        continue
                    # Remove any leftover journal / web artifacts
                    s_clean = re.sub(r'(?:www\.[a-z0-9\-]+\.[a-z]+|http[s]?://\S+|©\s*\d{4}|\bISSN:\s*[0-9\-]+|\bVolume\s+\d+|\bIJCRT\w*)', '', s_clean, flags=re.IGNORECASE).strip(' -–—|:,')
                    if len(s_clean) < 10:
                        continue
                    s_words = set(re.findall(r'\w+', s_clean.lower()))
                    overlap = len(q_words.intersection(s_words))
                    all_candidates.append((overlap, chunk_sc, s_clean, ref_id))

        all_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # Deduplicate candidates while preserving order
        unique_candidates = []
        seen_sents = set()
        for overlap, chunk_sc, s_text, ref_id in all_candidates:
            norm = re.sub(r'[^a-z0-9]', '', s_text.lower())
            if not norm or any(norm in seen or seen in norm for seen in seen_sents):
                continue
            seen_sents.add(norm)
            unique_candidates.append((overlap, chunk_sc, s_text, ref_id))

        # Determine section header
        if any(w in q_lower for w in ["step", "steps", "cpr", "procedure", "how to", "manage", "management", "action", "emergency", "cardiac"]):
            header_title = "### Clinical Guidance & Protocol\n"
        else:
            first_sec = retrieved_chunks[0].get("section")
            if first_sec and first_sec.lower() not in ["none", "general", "general overview", "details"]:
                header_title = f"### {first_sec.title()}\n"
            else:
                header_title = "### Clinical Evidence & Guidance\n"

        lines = [header_title]
        if unique_candidates and unique_candidates[0][0] > 0:
            for _, _, s_text, ref_id in unique_candidates[:4]:
                lines.append(f"- {s_text} [{ref_id}]")
            result_blocks.append("\n".join(lines))
        elif unique_candidates:
            for _, _, s_text, ref_id in unique_candidates[:3]:
                lines.append(f"- {s_text} [{ref_id}]")
            result_blocks.append("\n".join(lines))
        else:
            first_chunk = retrieved_chunks[0]
            clean_first = clean_clinical_text(first_chunk.get('text', ''))
            first_sent = re.split(r'(?<=[.!?])\s+', clean_first)[0] if clean_first else "Clinical protocol documented."
            result_blocks.append(f"### Clinical Guidance\n\n- {first_sent} [1]")

    return "\n\n".join(result_blocks)


def query_pipeline(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    direct_llm: bool = False,
    user_role: str = "DOCTOR",
    active_doc_ids: Optional[Set[int]] = None,
    db: Optional[Any] = None
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
    # 1. DIRECT LLM Mode — Genuinely bypasses FAISS, BM25, RRF, Reranker, NLI, and Citations
    if direct_llm:
        answer = ""
        using_mock = False

        if GROQ_API_KEY:
            try:
                answer = call_groq_llm(query, system_prompt=DEFAULT_DIRECT_LLM_SYSTEM_PROMPT)
            except Exception as e_groq:
                gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                if gemini_key:
                    try:
                        answer = call_gemini_fallback(query, system_prompt=DEFAULT_DIRECT_LLM_SYSTEM_PROMPT)
                    except Exception:
                        answer = "Direct LLM response: Unable to contact LLM provider. Please check network or API configuration."
                        using_mock = True
                else:
                    answer = f"Direct LLM Error: {str(e_groq)}"
                    using_mock = True
        else:
            gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if gemini_key:
                try:
                    answer = call_gemini_fallback(query, system_prompt=DEFAULT_DIRECT_LLM_SYSTEM_PROMPT)
                except Exception:
                    answer = "Direct LLM Mode: External API unavailable."
                    using_mock = True
            else:
                answer = "Direct LLM Mode: No API keys configured. LLM generation unavailable."
                using_mock = True

        return {
            "answer": answer.strip() if answer else "",
            "confidence_level": None,
            "confidence_score": None,
            "grounding_level": None,
            "grounding_coverage": "",
            "supported_claims": 0,
            "total_claims": 0,
            "evidence": [],
            "verification_results": [],
            "using_mock": using_mock,
            "grounded": False,
            "citations": [],
            "retrieval": {}
        }

    t0 = time.time()
    index, metadata, embeddings_array = get_vector_store()

    if len(metadata) == 0:
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
            "using_mock": False,
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
    patient_id_filter = (filters.get("patient_id") if filters else None) or clinical_entities.get("patient_id")
    is_historical = is_historical_patient_query(query)

    latest_report_id = None
    allowed_report_ids = set()
    if patient_id_filter:
        active_reports = get_patient_active_reports(patient_id_filter, db)
        if active_reports:
            latest_report_id = active_reports[0].id
            allowed_report_ids = {r.id for r in active_reports}

    filtered_chunks_with_indices: List[Tuple[int, Dict[str, Any]]] = []
    for idx, chunk in enumerate(metadata):
        doc_id = chunk.get("document_id")
        if active_doc_ids is not None and doc_id is not None and doc_id not in active_doc_ids:
            continue

        chunk_patient_id = chunk.get("patient_id")
        chunk_report_id = chunk.get("report_id")
        chunk_pdf_name = chunk.get("pdf_name", "")
        if chunk_report_id is None and "Report" in chunk_pdf_name:
            m_rep = re.search(r'Report(\d+)', chunk_pdf_name)
            if m_rep:
                chunk_report_id = int(m_rep.group(1))

        is_clinical_rep = (
            chunk_report_id is not None
            or chunk.get("document_type") == "clinical_report"
            or "Clinical_Report_" in chunk_pdf_name
        )

        match = True
        if filters:
            scope = filters.get("scope")
            if scope == "knowledge_base":
                if chunk.get("scope") != "knowledge_base":
                    match = False
            elif scope == "patient":
                if chunk.get("scope") != "patient" or chunk_patient_id != patient_id_filter:
                    match = False
                elif is_clinical_rep:
                    if chunk_report_id is not None and chunk_report_id not in allowed_report_ids and allowed_report_ids:
                        match = False
                    elif not is_historical and latest_report_id is not None and chunk_report_id != latest_report_id:
                        match = False
            elif scope == "temporary":
                doc_id_filter = filters.get("document_id")
                if str(chunk.get("document_id")) != str(doc_id_filter):
                    match = False
            elif scope == "patient_and_kb":
                is_kb = chunk.get("scope") == "knowledge_base"
                is_patient = chunk.get("scope") == "patient" and chunk_patient_id == patient_id_filter
                if not (is_kb or is_patient):
                    match = False
                elif is_patient and is_clinical_rep:
                    if chunk_report_id is not None and chunk_report_id not in allowed_report_ids and allowed_report_ids:
                        match = False
                    elif not is_historical and latest_report_id is not None and chunk_report_id != latest_report_id:
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
    elif max_raw_rerank < -3.0:
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
            "using_mock": False,
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
1. Answer the clinical question directly, cleanly, and concisely using ONLY the supplied retrieved evidence passages.
2. Address ONLY the specific clinical dimension or question asked (e.g., if asked about observations/vitals, return ONLY the observations and vital signs; if asked about treatment, return ONLY treatment recommendations; do NOT prepend or append unrelated report sections).
3. Do NOT include raw report metadata, header banners, "REPORT ID", "STATUS", "PATIENT ID", "CREATED", or chunk IDs in your answer text.
4. If comparing multiple reports or past timeline, clearly organize findings under chronological report headers (e.g., #### Report X).
5. Do NOT use outside medical knowledge, conjecture, or unverified treatments.
6. Do NOT invent facts, diagnoses, dosages, treatments, clinical values, or recommendations.
7. Paraphrasing is allowed IF AND ONLY IF the clinical meaning is preserved and fully supported.
8. If the retrieved evidence does not adequately answer the question, return verbatim:
"Insufficient evidence in the hospital knowledge base to answer this question reliably."
9. Annotate medical claims with their corresponding bracketed source reference, e.g., [1], [2].

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
