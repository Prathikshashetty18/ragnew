import pytest
import numpy as np
from app.retrievers import (
    tokenize_clinical_text,
    PersistentBM25Index,
    ReciprocalRankFusion,
    EvidenceDeduplicator,
    CrossEncoderReranker
)
from app.router import MultiRAGRouter

def test_clinical_tokenizer():
    text = "Give Ceftriaxone 1g-2g daily IV. WBC is 14,000 /uL and CRP is 48.5 mg/L. Check CURB-65 score."
    tokens = tokenize_clinical_text(text)
    
    # Must preserve medical units and acronyms
    assert "ceftriaxone" in tokens
    assert any("1g" in t or "2g" in t for t in tokens)
    assert any("curb-65" in t or "curb" in t for t in tokens)
    assert any("48.5" in t or "mg_l" in t or "mg" in t for t in tokens)

def test_bm25_index_lifecycle(tmp_path):
    storage_file = str(tmp_path / "test_bm25.pkl")
    chunks = [
        {"id": "c1", "text": "Ceftriaxone 1g daily for pneumonia treatment.", "contextualized_text": "Pneumonia. Ceftriaxone 1g daily."},
        {"id": "c2", "text": "Acid-fast bacilli stain and GeneXpert for tuberculosis.", "contextualized_text": "Tuberculosis. GeneXpert MTB."},
        {"id": "c3", "text": "Diabetic ketoacidosis with elevated blood glucose.", "contextualized_text": "Diabetes. Blood glucose."}
    ]
    bm25 = PersistentBM25Index(storage_path=storage_file)
    bm25.build_index(chunks)

    # Search for pneumonia
    results = bm25.search("Ceftriaxone 1g pneumonia")
    assert len(results) > 0
    assert results[0][0] == 0  # Chunk c1 should be rank 1

    # Search for tuberculosis
    tb_results = bm25.search("GeneXpert tuberculosis")
    assert len(tb_results) > 0
    assert tb_results[0][0] == 1  # Chunk c2 should be rank 1

    # Test load from disk
    loaded = PersistentBM25Index.load_from_disk(storage_path=storage_file)
    assert loaded.N == 3
    loaded_results = loaded.search("Ceftriaxone")
    assert len(loaded_results) > 0

def test_rrf_fusion_math():
    dense_results = [(0, 0.95), (1, 0.85), (2, 0.70)]
    bm25_results = [(1, 12.0), (0, 8.0), (3, 5.0)]

    fused = ReciprocalRankFusion.fuse(
        dense_results=dense_results,
        bm25_results=bm25_results,
        k=60,
        top_k=5,
        dense_weight=1.0,
        bm25_weight=1.0
    )

    # Document 1 has dense rank 2 and bm25 rank 1
    # Document 0 has dense rank 1 and bm25 rank 2
    # RRF(0) = 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.016393 + 0.016129 = 0.03252
    # RRF(1) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.03252
    # Both should be top candidates
    assert len(fused) == 4
    top_indices = [f["chunk_index"] for f in fused[:2]]
    assert 0 in top_indices and 1 in top_indices

def test_evidence_deduplication():
    chunks = [
        {"id": "c1", "text": "Diagnosis requires acute respiratory symptoms with cough, fever, dyspnea."},
        {"id": "c2", "text": "Diagnosis requires acute respiratory symptoms with cough, fever, dyspnea."},  # Identical
        {"id": "c3", "text": "Diagnosis requires acute respiratory symptoms with cough and fever."},  # Near duplicate (>85% overlap)
        {"id": "c4", "text": "Empirical antimicrobial therapy: Ceftriaxone 1g daily for inpatient care."}  # Diverse distinct
    ]
    deduped = EvidenceDeduplicator.deduplicate(chunks, similarity_threshold=0.80, max_chunks=5)
    assert len(deduped) <= 2
    texts = [c["text"] for c in deduped]
    assert any("Ceftriaxone" in t for t in texts)

def test_multirag_router_weights():
    # Dosage query
    dosage_entities = {
        "conditions": ["pneumonia"],
        "medications": ["ceftriaxone"],
        "dosages": ["1g daily"],
        "diagnostic_intent": False
    }
    route = MultiRAGRouter.route_query("Ceftriaxone 1g daily dose for pneumonia", dosage_entities)
    assert route["strategy"] == "medication_dosage"
    assert route["bm25_weight"] > route["dense_weight"]

    # Diagnostic criteria query
    diag_entities = {
        "conditions": ["tuberculosis"],
        "medications": [],
        "dosages": [],
        "diagnostic_intent": True
    }
    route = MultiRAGRouter.route_query("What are the diagnostic criteria for tuberculosis?", diag_entities)
    assert route["strategy"] == "condition_diagnostic"
