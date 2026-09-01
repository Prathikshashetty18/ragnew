import os
import re
import hashlib
from typing import Dict, Any, Tuple
from pypdf import PdfReader
from sqlalchemy.orm import Session

# Medical clinical lexicon for domain relevance evaluation
CLINICAL_LEXICON = {
    "pneumonia", "tuberculosis", "hypertension", "diabetes", "cardiovascular",
    "antibiotic", "dosage", "diagnosis", "etiology", "pathology", "symptoms",
    "treatment", "clinical", "patient", "therapy", "antimicrobial", "radiology",
    "consolidation", "effusion", "hematology", "biochemistry", "leukocyte",
    "hemoglobin", "platelet", "crp", "glucose", "insulin", "guideline",
    "protocol", "infection", "bacterial", "viral", "respiratory", "cardiac",
    "pulmonary", "renal", "hepatic", "neurological", "oncology", "pharmacology",
    "amoxicillin", "ceftriaxone", "azithromycin", "levofloxacin", "doxycycline",
    "vancomycin", "curb-65", "x-ray", "computed tomography", "mri", "prognosis",
    "contraindication", "adverse", "laboratory", "triage", "inpatient", "outpatient",
    "disease", "syndrome", "acute", "chronic", "serum", "creatinine", "vital",
    "blood pressure", "pulse", "temperature", "oxygen", "spo2", "icu", "ventilator"
}

def compute_md5(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()

def validate_pdf_structure(file_path: str) -> Tuple[bool, str, int, str]:
    if not os.path.exists(file_path):
        return False, "File does not exist on disk.", 0, ""
        
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
            if not header.startswith(b"%PDF-"):
                return False, "Invalid file format: Missing standard PDF header signature.", 0, ""
                
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        if page_count == 0:
            return False, "Corrupted PDF: Document contains 0 pages.", 0, ""
            
        full_text = []
        for p_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                full_text.append(text)
                
        combined_text = " ".join(full_text).strip()
        if len(combined_text) < 50:
            return False, "Unreadable or empty PDF: Insufficient selectable text extracted (may be an empty scan without OCR).", page_count, ""
            
        return True, "PDF structure verified and selectable text extracted.", page_count, combined_text
    except Exception as e:
        return False, f"Corrupted or unreadable PDF: {str(e)}", 0, ""

def evaluate_medical_relevance(text: str) -> Dict[str, Any]:
    clean_text = text.lower()
    words = re.findall(r'[a-zA-Z\-]+', clean_text)
    total_words = len(words)
    
    if total_words == 0:
        return {
            "score": 0.0,
            "classification": "LOW",
            "decision": "REJECT",
            "matched_terms": [],
            "reason": "Document has zero textual words."
        }
        
    matched = set()
    for term in CLINICAL_LEXICON:
        if " " in term:
            if term in clean_text:
                matched.add(term)
        else:
            if term in words:
                matched.add(term)
                
    distinct_term_count = len(matched)
    relevance_ratio = min(distinct_term_count / 12.0, 1.0)
    
    if distinct_term_count >= 6:
        classification = "HIGH"
        decision = "APPROVE"
        reason = f"Strong clinical relevance verified ({distinct_term_count} key medical terms detected)."
    elif distinct_term_count >= 2:
        classification = "UNCERTAIN"
        decision = "REVIEW"
        reason = f"Moderate medical terms ({distinct_term_count} terms detected). Requires clinical staff review."
    else:
        classification = "LOW"
        decision = "REJECT"
        reason = "Low medical relevance: Content does not match recognized clinical or healthcare terminology."
        
    return {
        "score": round(relevance_ratio, 2),
        "classification": classification,
        "decision": decision,
        "matched_terms": sorted(list(matched)),
        "reason": reason
    }

def detect_version_and_duplicates(filename: str, file_hash: str, db: Session, DocumentModel) -> Dict[str, Any]:
    existing_duplicate = db.query(DocumentModel).filter(DocumentModel.hash_md5 == file_hash).first()
    if existing_duplicate:
        return {
            "is_duplicate": True,
            "duplicate_of_id": existing_duplicate.id,
            "duplicate_of_name": existing_duplicate.name,
            "version": existing_duplicate.version,
            "flag": "DUPLICATE",
            "message": f"Exact duplicate of existing document '{existing_duplicate.name}' (ID: {existing_duplicate.id})."
        }
        
    version_match = re.search(r'v(?:er(?:sion)?)?[\s_.-]*(\d+(?:\.\d+)?)', filename, re.IGNORECASE)
    edition_match = re.search(r'(\d+)(?:st|nd|rd|th)[\s_.-]*(?:ed(?:ition)?)', filename, re.IGNORECASE)
    
    version = "1.0"
    if version_match:
        version = f"v{version_match.group(1)}"
    elif edition_match:
        version = f"{edition_match.group(1)}th Ed."
        
    return {
        "is_duplicate": False,
        "duplicate_of_id": None,
        "duplicate_of_name": None,
        "version": version,
        "flag": "NONE",
        "message": f"New document. Detected version: {version}"
    }
