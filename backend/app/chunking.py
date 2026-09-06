"""
Hierarchical Clinical Document Chunker and Contextual Chunk Enricher.

Preserves clinical document hierarchy:
Document -> Chapter/Section -> Subsection -> Clinical Recommendation / Fact

Enriches chunks with structural metadata and contextualized representations
before embedding and BM25 indexing, while preserving original_text for LLM presentation.
"""

import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from app.config import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP

# Regex patterns for clinical document structural headers
SECTION_PATTERNS = [
    r'^(?:SECTION|CHAPTER|PART)\s+\d+[:\s\-\.]+[^\n]+',
    r'^(?:DOCUMENT REF|APPROVAL COMMITTEE|HOSPITAL APPROVED|CENTRAL CLINICAL|DEPARTMENT OF)[^\n]+',
    r'^#{1,3}\s+[^\n]+',
    r'^[A-Z0-9\s]{4,35}:$',  # Strictly standalone ALL CAPS headers
    r'^(?:CHIEF COMPLAINT|CLINICAL HISTORY|OBSERVATIONS|INVESTIGATIONS|CLINICAL ASSESSMENT|RELEVANT EVIDENCE|RECOMMENDATIONS|SOURCES)[:\s]+',
]

SUBSECTION_PATTERNS = [
    r'^\d+\.\d+\s+[A-Za-z0-9\s,\-\(\)]+',
    r'^\*\*[^*]+\*\*[:\s]*',
]

# Authority weights for medical sources
AUTHORITY_WEIGHTS = {
    "who": 1.0,
    "national": 0.95,
    "hospital": 0.90,
    "guideline": 0.90,
    "textbook": 0.80,
    "research_paper": 0.85,
    "clinical_report": 0.80,
    "ai_generated_report": 0.80,
    "blood_report": 0.75,
    "radiology_report": 0.75,
    "nursing_report": 0.70,
    "temporary": 0.70,
    "default": 0.75
}

def determine_authority_score(doc_name: str, doc_type: str = "guideline", scope: str = "knowledge_base") -> float:
    name_lower = doc_name.lower()
    type_lower = (doc_type or "").lower()
    
    if "who" in name_lower or "world health" in name_lower:
        return 1.0
    if "national" in name_lower or "cdc" in name_lower or "nice" in name_lower:
        return 0.95
    if "hospital" in name_lower or "hcg" in name_lower or "protocol" in name_lower:
        return 0.90
    if "guideline" in type_lower:
        return 0.90
    if "textbook" in type_lower or "textbook" in name_lower:
        return 0.80
    if "blood" in type_lower or "radiology" in type_lower:
        return 0.75
    return AUTHORITY_WEIGHTS.get(type_lower, 0.75)


def infer_clinical_disease(text: str, filename: str) -> str:
    combined = (filename + " " + text[:500]).lower().replace("_", " ")
    if "pneumonia" in combined or "respiratory" in combined:
        return "Pneumonia / Respiratory Infection"
    if "tuberculosis" in combined or re.search(r'\b(?:tb|mtb)\b', combined):
        return "Tuberculosis (TB)"
    if "diabetes" in combined or "dka" in combined or "hyperglycemia" in combined or "ketoacidosis" in combined:
        return "Diabetes Mellitus & Complications"
    if "x-ray" in combined or "chest" in combined or "radiology" in combined:
        return "Thoracic / Pulmonary Findings"
    if "blood" in combined or "cbc" in combined or "hematology" in combined:
        return "Hematology / Inflammatory Markers"
    return "General Clinical Medicine"


class HierarchicalClinicalChunker:
    """Slices documents respecting section headers, recommendations, and clinical hierarchy."""

    def __init__(self, chunk_size: int = RAG_CHUNK_SIZE, chunk_overlap: int = RAG_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_into_blocks(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Parses text into (parent_section, subsection, paragraph_text) blocks.
        Preserves content lines and separates inline headers from body text.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        blocks = []
        
        current_section = "General Overview"
        current_subsection = "Clinical Details"
        current_lines = []

        for line in lines:
            line_str = line.strip()
            # Standalone or short header lines (< 70 chars)
            is_section = False
            for pat in SECTION_PATTERNS:
                if re.match(pat, line_str) and len(line_str) < 70:
                    is_section = True
                    break
            
            is_subsection = False
            if not is_section:
                for pat in SUBSECTION_PATTERNS:
                    if re.match(pat, line_str) and len(line_str) < 70:
                        is_subsection = True
                        break

            if is_section:
                if current_lines:
                    blocks.append((current_section, current_subsection, " ".join(current_lines)))
                    current_lines = []
                clean_sec_str = re.sub(r'^#+\s*', '', line_str).strip()
                if re.match(r'^(?:SECTION|CHAPTER|PART)\s+\d+', clean_sec_str, re.IGNORECASE):
                    current_section = clean_sec_str
                elif ":" in clean_sec_str:
                    parts = clean_sec_str.split(":", 1)
                    current_section = parts[0].strip()
                    if parts[1].strip():
                        current_lines.append(parts[1].strip())
                else:
                    current_section = clean_sec_str
                current_subsection = "Overview"
            elif is_subsection:
                if current_lines:
                    blocks.append((current_section, current_subsection, " ".join(current_lines)))
                    current_lines = []
                clean_sub_str = re.sub(r'^#+\s*', '', line_str).strip()
                if ":" in clean_sub_str:
                    parts = clean_sub_str.split(":", 1)
                    current_subsection = parts[0].strip()
                    if parts[1].strip():
                        current_lines.append(parts[1].strip())
                else:
                    current_subsection = clean_sub_str
            else:
                current_lines.append(line_str)

        if current_lines:
            blocks.append((current_section, current_subsection, " ".join(current_lines)))

        return blocks

    def chunk_document(
        self,
        text: str,
        pdf_name: str,
        page_number: int,
        doc_id: Optional[int] = None,
        scope: str = "knowledge_base",
        patient_id: Optional[str] = None,
        version: str = "1.0",
        document_type: str = "Guideline"
    ) -> List[Dict[str, Any]]:
        blocks = self._split_into_blocks(text)
        disease = infer_clinical_disease(text, pdf_name)
        authority_score = determine_authority_score(pdf_name, document_type, scope)
        
        chunks = []

        for section, subsection, block_text in blocks:
            clean_text = re.sub(r'\s+', ' ', block_text).strip()
            if len(clean_text) < 20:
                continue

            clean_sec = re.sub(r'^#+\s*', '', section).strip()
            clean_sub = re.sub(r'^#+\s*', '', subsection).strip()

            # If block fits within chunk_size, keep as a single cohesive unit
            if len(clean_text) <= self.chunk_size:
                chunk_id = str(uuid.uuid4())
                contextualized = ContextualChunkEnricher.enrich(
                    text=clean_text,
                    pdf_name=pdf_name,
                    section=clean_sec,
                    subsection=clean_sub,
                    disease=disease,
                    version=version,
                    scope=scope,
                    patient_id=patient_id
                )
                chunks.append({
                    "id": chunk_id,
                    "chunk_id": chunk_id,
                    "text": clean_text,
                    "original_text": clean_text,
                    "contextualized_text": contextualized,
                    "pdf_name": pdf_name,
                    "document_name": pdf_name,
                    "page_number": page_number,
                    "page": page_number,
                    "document_id": doc_id,
                    "scope": scope,
                    "patient_id": patient_id,
                    "version": version,
                    "document_type": document_type,
                    "section": clean_sec,
                    "subsection": clean_sub,
                    "parent_section": clean_sec,
                    "disease": disease,
                    "condition": disease,
                    "authority_score": authority_score,
                    "status": "ACTIVE"
                })
            else:
                # Sub-chunk with overlap along sentence boundaries
                sentences = re.split(r'(?<=[.!?])\s+', clean_text)
                cur_chunk_sents = []
                cur_len = 0
                
                for s in sentences:
                    s_len = len(s)
                    if cur_len + s_len > self.chunk_size and cur_chunk_sents:
                        chunk_content = " ".join(cur_chunk_sents).strip()
                        chunk_id = str(uuid.uuid4())
                        contextualized = ContextualChunkEnricher.enrich(
                            text=chunk_content,
                            pdf_name=pdf_name,
                            section=clean_sec,
                            subsection=clean_sub,
                            disease=disease,
                            version=version,
                            scope=scope,
                            patient_id=patient_id
                        )
                        chunks.append({
                            "id": chunk_id,
                            "chunk_id": chunk_id,
                            "text": chunk_content,
                            "original_text": chunk_content,
                            "contextualized_text": contextualized,
                            "pdf_name": pdf_name,
                            "document_name": pdf_name,
                            "page_number": page_number,
                            "page": page_number,
                            "document_id": doc_id,
                            "scope": scope,
                            "patient_id": patient_id,
                            "version": version,
                            "document_type": document_type,
                            "section": clean_sec,
                            "subsection": clean_sub,
                            "parent_section": clean_sec,
                            "disease": disease,
                            "condition": disease,
                            "authority_score": authority_score,
                            "status": "ACTIVE"
                        })
                        
                        # Retain overlap sentences
                        overlap_sents = []
                        overlap_len = 0
                        for prev_s in reversed(cur_chunk_sents):
                            if overlap_len + len(prev_s) <= self.chunk_overlap:
                                overlap_sents.insert(0, prev_s)
                                overlap_len += len(prev_s)
                            else:
                                break
                        cur_chunk_sents = overlap_sents + [s]
                        cur_len = overlap_len + s_len
                    else:
                        cur_chunk_sents.append(s)
                        cur_len += s_len

                if cur_chunk_sents:
                    chunk_content = " ".join(cur_chunk_sents).strip()
                    chunk_id = str(uuid.uuid4())
                    contextualized = ContextualChunkEnricher.enrich(
                        text=chunk_content,
                        pdf_name=pdf_name,
                        section=clean_sec,
                        subsection=clean_sub,
                        disease=disease,
                        version=version,
                        scope=scope,
                        patient_id=patient_id
                    )
                    chunks.append({
                        "id": chunk_id,
                        "chunk_id": chunk_id,
                        "text": chunk_content,
                        "original_text": chunk_content,
                        "contextualized_text": contextualized,
                        "pdf_name": pdf_name,
                        "document_name": pdf_name,
                        "page_number": page_number,
                        "page": page_number,
                        "document_id": doc_id,
                        "scope": scope,
                        "patient_id": patient_id,
                        "version": version,
                        "document_type": document_type,
                        "section": clean_sec,
                        "subsection": clean_sub,
                        "parent_section": clean_sec,
                        "disease": disease,
                        "condition": disease,
                        "authority_score": authority_score,
                        "status": "ACTIVE"
                    })

        return chunks


class ContextualChunkEnricher:
    """Enriches chunk text with structural document provenance."""

    @staticmethod
    def enrich(
        text: str,
        pdf_name: str,
        section: str,
        subsection: str,
        disease: str,
        version: str = "1.0",
        scope: str = "knowledge_base",
        patient_id: Optional[str] = None
    ) -> str:
        clean_name = pdf_name.replace(".pdf", "").replace(".txt", "").replace("_", " ")
        clean_section = re.sub(r'^#+\s*', '', section).strip()
        clean_subsection = re.sub(r'^#+\s*', '', subsection).strip()
        if scope == "patient" and patient_id:
            header = f"Patient Record: {patient_id}. Document: {clean_name}. Section: {clean_section}."
        else:
            header = f"Document: {clean_name} (Ver: {version}). Section: {clean_section}. Subsection: {clean_subsection}. Topic: {disease}."
        return f"{header}\n{text}"

