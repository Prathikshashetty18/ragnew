import pytest
from app.clinical_understanding import ClinicalEntityExtractor, ClinicalQueryExpander

def test_entity_extraction_pneumonia_dosage():
    query = "What is the recommended dose of Ceftriaxone 1g-2g daily for severe pneumonia in elderly patients?"
    entities = ClinicalEntityExtractor.extract_entities(query)

    assert "pneumonia" in entities["conditions"]
    assert "ceftriaxone" in entities["medications"]
    assert "elderly" in entities["populations"]
    assert "emergency" in entities["urgency"]  # 'severe' maps to emergency
    assert entities["treatment_intent"] is True
    assert any("1g" in d or "2g" in d for d in entities["dosages"])

def test_entity_extraction_symptom_cluster_meningitis():
    query = "Patient with fever, neck stiffness and altered consciousness. What emergency protocol applies?"
    entities = ClinicalEntityExtractor.extract_entities(query)

    assert "fever" in entities["symptoms"]
    assert "neck stiffness" in entities["symptoms"]
    assert "altered consciousness" in entities["symptoms"]
    assert "meningitis" in entities["inferred_syndromes"]
    assert entities["urgency"] == "emergency"

def test_entity_extraction_tuberculosis_investigations():
    query = "What diagnostic workup using GeneXpert MTB/RIF and AFB stain should be done for active tuberculosis?"
    entities = ClinicalEntityExtractor.extract_entities(query)

    assert "tuberculosis" in entities["conditions"]
    assert "genexpert" in entities["investigations"]
    assert "afb_stain" in entities["investigations"]
    assert entities["diagnostic_intent"] is True

def test_query_expansion_preserves_primary():
    query = "What is the empiric antibiotic therapy for community-acquired pneumonia?"
    entities = ClinicalEntityExtractor.extract_entities(query)
    variants = ClinicalQueryExpander.expand_query(query, entities)

    # First variant MUST be the exact original query
    assert variants[0] == query
    assert len(variants) >= 2
    # Ensure variants are relevant
    assert any("pneumonia" in v.lower() for v in variants)
