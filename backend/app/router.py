"""
Multi-RAG Deterministic Router.

Determines optimal retrieval weights, candidate parameters, and filtering rules
based on clinical entity analysis and intent detection.
"""

from typing import Dict, Any

class MultiRAGRouter:
    """Deterministic routing based on clinical query characteristics."""

    @staticmethod
    def route_query(query: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the query into a deterministic strategy configuration:
        - MEDICATION_DOSAGE: high lexical weight (BM25 1.5, Dense 0.8)
        - EXACT_GUIDELINE: heavy lexical emphasis (BM25 1.8, Dense 0.6)
        - CONDITION_DIAGNOSTIC: balanced hybrid with metadata priority
        - BROAD_CLINICAL: standard balanced hybrid (BM25 1.0, Dense 1.0)
        """
        has_dosage = len(entities.get("dosages", [])) > 0
        has_medication = len(entities.get("medications", [])) > 0
        has_conditions = len(entities.get("conditions", [])) > 0 or len(entities.get("inferred_syndromes", [])) > 0
        is_diagnostic = entities.get("diagnostic_intent", False)

        # 1. Medication / Dosage query: exact units and numbers require high lexical weighting
        if has_dosage and has_medication:
            return {
                "strategy": "medication_dosage",
                "dense_weight": 0.8,
                "bm25_weight": 1.6,
                "enable_reranker": True,
                "target_section_hint": "Antimicrobial Therapy / Dosage",
                "rationale": "High lexical emphasis chosen to precisely match drug names, dosages, and administration intervals."
            }

        if has_dosage:
            return {
                "strategy": "dosage_numerical",
                "dense_weight": 0.9,
                "bm25_weight": 1.4,
                "enable_reranker": True,
                "target_section_hint": "Dosage & Lab Thresholds",
                "rationale": "Lexical prioritization applied for numerical units, laboratory cutoffs, and dosing rules."
            }

        # 2. Exact guideline reference queries (e.g. 'document ref', 'hcg-resp', 'section 1.2')
        if any(w in query.lower() for w in ["section", "document ref", "curb-65 score", "table", "protocol ref"]):
            return {
                "strategy": "exact_guideline_phrase",
                "dense_weight": 0.7,
                "bm25_weight": 1.8,
                "enable_reranker": True,
                "target_section_hint": "Protocol Structure",
                "rationale": "High lexical priority to match exact document references, section numbers, or acronyms."
            }

        # 3. Condition-specific diagnostic or criteria questions
        if has_conditions and is_diagnostic:
            return {
                "strategy": "condition_diagnostic",
                "dense_weight": 1.2,
                "bm25_weight": 1.0,
                "enable_reranker": True,
                "target_section_hint": "Diagnostic Protocol & Workup",
                "rationale": "Balanced semantic and lexical routing to retrieve clinical suspicion and diagnostic criteria."
            }

        # 4. Standard broad clinical query
        return {
            "strategy": "broad_clinical_hybrid",
            "dense_weight": 1.0,
            "bm25_weight": 1.0,
            "enable_reranker": True,
            "target_section_hint": "General Medical Knowledge",
            "rationale": "Standard balanced Multi-RAG hybrid retrieval fusing dense semantic and BM25 lexical candidates."
        }
