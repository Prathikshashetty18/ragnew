import pytest
from app.rag_pipeline import query_pipeline

def test_pipeline_normal_clinical_query():
    res = query_pipeline("What are the diagnostic criteria and symptoms for pneumonia?")
    
    assert "answer" in res
    assert len(res["answer"]) > 10
    assert "confidence_level" in res
    assert "confidence_score" in res
    assert "evidence" in res
    assert "citations" in res
    assert len(res["citations"]) > 0
    assert "retrieval" in res
    assert res["retrieval"]["strategy"] in ["condition_diagnostic", "broad_clinical_hybrid", "dosage_numerical", "medication_dosage"]

    # Verify top citation structure
    top_citation = res["citations"][0]
    assert "pdf_name" in top_citation
    assert "page_number" in top_citation
    assert "section" in top_citation

def test_pipeline_medication_dosage_query():
    res = query_pipeline("What is the empirical antibiotic dosage of Ceftriaxone 1g daily for inpatient pneumonia?")
    
    assert res["retrieval"]["strategy"] == "medication_dosage"
    assert len(res["citations"]) > 0
    # The answer or evidence must mention Ceftriaxone
    evidence_texts = " ".join([e.get("supporting_text", "") for e in res["evidence"]])
    citation_secs = " ".join([c.get("section", "") + " " + c.get("subsection", "") for c in res["citations"]])
    assert "ceftriaxone" in evidence_texts.lower() or "antimicrobial" in citation_secs.lower()

def test_pipeline_patient_scope_filter():
    # Patient P001 scope should only retrieve P001 reports
    res = query_pipeline(
        "What were the chest X-ray findings?",
        filters={"scope": "patient", "patient_id": "P001"}
    )
    assert len(res["citations"]) > 0
    for cit in res["citations"]:
        assert "Report" in cit["pdf_name"] or "Chest" in cit["pdf_name"] or "Blood" in cit["pdf_name"]

def test_pipeline_insufficient_evidence():
    # Out-of-corpus query
    res = query_pipeline("What is the laparoscopic surgical resection technique for acute appendicitis?")
    
    assert res["confidence_level"] == "Low"
    assert res["confidence_score"] == 0.0
    assert (
        "insufficient evidence in the hospital knowledge base" in res["answer"].lower()
        or "could not find sufficient supporting evidence" in res["answer"].lower()
    )
    assert res.get("retrieval", {}).get("insufficient_evidence") is True

def test_pipeline_direct_llm_mode():
    res = query_pipeline("What is insulin?", direct_llm=True)
    assert "answer" in res
    assert len(res["evidence"]) == 0
    assert len(res["citations"]) == 0

def test_pipeline_backward_compatibility_keys():
    res = query_pipeline("What are the TB screening tests?")
    expected_legacy_keys = [
        "answer", "confidence_level", "confidence_score",
        "evidence", "verification_results", "using_mock"
    ]
    for k in expected_legacy_keys:
        assert k in res, f"Missing legacy backward-compatible key: {k}"

    expected_new_keys = ["retrieval", "grounded", "citations"]
    for k in expected_new_keys:
        assert k in res, f"Missing Multi-RAG enhanced key: {k}"
