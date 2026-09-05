import pytest
from app.chunking import HierarchicalClinicalChunker, ContextualChunkEnricher, determine_authority_score, infer_clinical_disease

SAMPLE_CLINICAL_TEXT = """HOSPITAL APPROVED CLINICAL PRACTICE GUIDELINE: RESPIRATORY INFECTIONS
DOCUMENT REF: HCG-RESP-2026-04

SECTION 1: COMMUNITY-ACQUIRED PNEUMONIA (CAP)
1.1 DIAGNOSTIC CRITERIA:
Diagnosis requires the presence of acute respiratory symptoms (cough, fever, dyspnea, pleuritic chest pain) accompanied by a new focal infiltrate on chest radiography.

1.2 RISK STRATIFICATION (CURB-65 SCORE):
Score 0-1 indicates low risk. Score 2 indicates moderate risk requiring short inpatient stay. Score >= 3 indicates high risk requiring urgent admission and ICU evaluation.

1.3 EMPIRICAL ANTIMICROBIAL THERAPY GUIDELINES:
Outpatient: Amoxicillin 1g TID orally or Doxycycline 100mg BID.
Inpatient Non-Severe CAP: Intravenous Beta-lactam (Ceftriaxone 1g-2g daily) PLUS Macrolide (Azithromycin 500mg daily).
"""

def test_hierarchical_chunker_structure():
    chunker = HierarchicalClinicalChunker(chunk_size=400, chunk_overlap=80)
    chunks = chunker.chunk_document(
        text=SAMPLE_CLINICAL_TEXT,
        pdf_name="Hospital_Guideline_Pneumonia.pdf",
        page_number=1,
        doc_id=1,
        scope="knowledge_base",
        document_type="Guideline"
    )

    assert len(chunks) >= 3
    # Verify metadata fields
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "pdf_name" in chunk
        assert "page_number" in chunk
        assert "section" in chunk
        assert "subsection" in chunk
        assert "parent_section" in chunk
        assert "disease" in chunk
        assert "authority_score" in chunk
        assert "contextualized_text" in chunk
        assert "original_text" in chunk

    # Check subsection mapping
    subsections = [c["subsection"] for c in chunks]
    assert any("DIAGNOSTIC CRITERIA" in s for s in subsections)
    assert any("RISK STRATIFICATION" in s for s in subsections)
    assert any("ANTIMICROBIAL" in s for s in subsections)

def test_contextual_chunk_enricher():
    enriched = ContextualChunkEnricher.enrich(
        text="Recommended dose is Ceftriaxone 1g daily.",
        pdf_name="Hospital_Guideline_Pneumonia.pdf",
        section="SECTION 1: CAP",
        subsection="1.3 ANTIMICROBIAL THERAPY",
        disease="Pneumonia",
        version="1.0"
    )
    assert "Document: Hospital Guideline Pneumonia" in enriched
    assert "Section: SECTION 1: CAP" in enriched
    assert "Subsection: 1.3 ANTIMICROBIAL THERAPY" in enriched
    assert "Topic: Pneumonia" in enriched
    assert "Recommended dose is Ceftriaxone 1g daily." in enriched

def test_authority_scoring():
    assert determine_authority_score("WHO_Guideline_TB.pdf", "Guideline") == 1.0
    assert determine_authority_score("National_Clinical_Standard.pdf", "Guideline") == 0.95
    assert determine_authority_score("Hospital_Guideline_Pneumonia.pdf", "Guideline") == 0.90
    assert determine_authority_score("Endocrinology_Textbook.pdf", "Textbook") == 0.80

def test_disease_inference():
    assert "Pneumonia" in infer_clinical_disease("patient has consolidation and cough", "Hospital_Guideline_Pneumonia.pdf")
    assert "Tuberculosis" in infer_clinical_disease("positive afb sputum culture", "Hospital_Guideline_Tuberculosis.pdf")
    assert "Diabetes" in infer_clinical_disease("ketoacidosis with glucose > 250", "Diabetes_Textbook.pdf")
