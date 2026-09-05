import pytest
from app.nli_validator import extract_claims, validate_response_with_nli
from app.rag_pipeline import DEFAULT_STRICT_RAG_SYSTEM_PROMPT, get_embedding_model

def test_extract_claims_various_formats():
    # Numbered list
    numbered_text = (
        "1. For low-risk outpatient community-acquired pneumonia, initiate Amoxicillin 1g TID.\n"
        "2. Alternatively, Doxycycline 100mg BID may be administered."
    )
    claims = extract_claims(numbered_text)
    assert len(claims) == 2
    assert "Amoxicillin 1g TID" in claims[0]
    assert "Doxycycline 100mg BID" in claims[1]

    # Bulleted list
    bullet_text = (
        "- Amoxicillin is recommended as first-line therapy.\n"
        "- Assess clinical response within 48 to 72 hours."
    )
    b_claims = extract_claims(bullet_text)
    assert len(b_claims) == 2

    # Meta preamble filtering
    preamble_text = (
        "Based on the provided hospital guidelines:\n"
        "1. First-line therapy for outpatient low-risk CAP is Amoxicillin 1g TID orally.\n"
        "Note that clinical evaluation is important."
    )
    p_claims = extract_claims(preamble_text)
    assert not any("Based on the provided" in c for c in p_claims)
    assert any("Amoxicillin 1g TID" in c for c in p_claims)

def test_evidence_grounding_strongly_supported_paraphrase():
    embedder = get_embedding_model()
    evidence_chunks = [
        {
            "id": 101,
            "text": "1.3 Empirical Antimicrobial Therapy. Outpatient / Low Risk: Amoxicillin 1g TID orally or Doxycycline 100mg BID. Duration: 5-7 days based on clinical stability.",
            "pdf_name": "Hospital_Guideline_Pneumonia.pdf",
            "page_number": 2,
            "section": "1.3 Empirical Antimicrobial Therapy",
            "subsection": "Outpatient"
        }
    ]

    # Clinical paraphrased answer
    answer = "For outpatient low-risk community-acquired pneumonia, first-line oral therapy is Amoxicillin 1g three times daily or Doxycycline 100mg twice daily."

    val_res = validate_response_with_nli(answer, evidence_chunks, embedder)
    
    assert val_res["total_claims"] >= 1
    assert val_res["grounding_level"] == "Strongly Supported"
    assert val_res["supported_claims"] == val_res["total_claims"]
    assert "claims supported" in val_res["grounding_coverage"]
    assert len(val_res["verification_results"]) >= 1
    assert val_res["verification_results"][0]["status"] == "Supported"
    assert val_res["verification_results"][0]["pdf_name"] == "Hospital_Guideline_Pneumonia.pdf"
    assert val_res["verification_results"][0]["chunk_id"] == 101

def test_strict_rag_prompt_invariants():
    assert "Answer the clinical question using ONLY the supplied retrieved evidence passages" in DEFAULT_STRICT_RAG_SYSTEM_PROMPT
    assert "Do NOT use any outside medical knowledge" in DEFAULT_STRICT_RAG_SYSTEM_PROMPT
    assert "Do NOT invent facts, diagnoses, dosages" in DEFAULT_STRICT_RAG_SYSTEM_PROMPT
    assert "Insufficient evidence in the hospital knowledge base to answer this question reliably." in DEFAULT_STRICT_RAG_SYSTEM_PROMPT

def test_calibrated_confidence_score_calculation():
    from app.retrievers import get_cross_encoder_model
    embedder = get_embedding_model()
    cross_encoder = get_cross_encoder_model()
    evidence_chunks = [
        {
            "id": 101,
            "text": "1.3 Empirical Antimicrobial Therapy. Outpatient / Low Risk: Amoxicillin 1g TID orally or Doxycycline 100mg BID.",
            "pdf_name": "Hospital_Guideline_Pneumonia.pdf",
            "page_number": 2,
            "dense_score": 0.80,
            "rerank_score": 0.96
        }
    ]

    # 1. Strongly supported answer
    answer = "For outpatient low-risk pneumonia, first-line oral therapy is Amoxicillin 1g three times daily or Doxycycline 100mg twice daily."
    res = validate_response_with_nli(answer, evidence_chunks, embedder, cross_encoder=cross_encoder)
    assert res["grounding_level"] == "Strongly Supported"
    assert res["confidence_level"] == "High"
    assert res["confidence_score"] >= 0.85
    assert res["supported_claims"] == res["total_claims"]

    # 2. Contradiction penalty
    contra_answer = "Outpatient low-risk pneumonia should not be treated with Amoxicillin or Doxycycline."
    res_contra = validate_response_with_nli(contra_answer, evidence_chunks, embedder, cross_encoder=cross_encoder)
    assert res_contra["grounding_level"] == "Not Supported"
    assert res_contra["confidence_level"] == "Low"
    assert res_contra["confidence_score"] <= 0.20

    # 3. Unsupported answer with zero claims
    unsupp_chunks = []
    res_unsupp = validate_response_with_nli(answer, unsupp_chunks, embedder, cross_encoder=cross_encoder)
    assert res_unsupp["confidence_level"] == "Low"
    assert res_unsupp["confidence_score"] == 0.0

