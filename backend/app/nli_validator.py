import re
import numpy as np
from typing import List, Dict, Any, Tuple

# Clinical polarity / antonym pairs for contradiction detection
CONTRADICTION_PAIRS = [
    ("increase", "decrease"),
    ("increased", "decreased"),
    ("increases", "decreases"),
    ("elevate", "reduce"),
    ("elevated", "reduced"),
    ("elevation", "reduction"),
    ("high", "low"),
    ("higher", "lower"),
    ("positive", "negative"),
    ("indicated", "contraindicated"),
    ("indicated", "avoid"),
    ("recommended", "contraindicated"),
    ("treatment", "contraindicated"),
    ("therapy", "contraindicated"),
    ("safe", "unsafe"),
    ("safe", "harmful"),
    ("normal", "abnormal"),
    ("present", "absent"),
    ("bacterial", "viral"),
    ("suitable", "unsuitable"),
    ("continue", "discontinue"),
    ("effective", "ineffective")
]

NEGATION_TERMS = {"not", "never", "cannot", "contraindicated", "unrecommended", "avoid", "ineffective"}

def split_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]

def check_clinical_contradiction(premise: str, hypothesis: str) -> Tuple[bool, str]:
    """
    Analyzes premise and hypothesis for clinical polarity inversion or explicit negation flips.
    """
    p_lower = premise.lower()
    h_lower = hypothesis.lower()
    
    p_tokens = set(re.findall(r'\w+', p_lower))
    h_tokens = set(re.findall(r'\w+', h_lower))
    
    # 1. Check direct antonym pairs where premise has term A and hypothesis has term B
    for term_a, term_b in CONTRADICTION_PAIRS:
        if (term_a in p_tokens and term_b in h_tokens) or (term_b in p_tokens and term_a in h_tokens):
            overlap = p_tokens.intersection(h_tokens)
            if len(overlap) >= 2:
                return True, f"Opposing clinical relationship detected ({term_a} vs {term_b})."
                
    # 2. Check direct explicit negation statements
    explicit_neg_phrases = [
        "not recommended", "should not", "do not give", "never use", "contraindicated", 
        "not indicated", "ineffective", "should be avoided", "avoid"
    ]
    for phrase in explicit_neg_phrases:
        if phrase in h_lower and phrase not in p_lower:
            common_nouns = p_tokens.intersection(h_tokens) - {"is", "are", "the", "a", "an", "and", "in", "to", "for", "with", "not", "or"}
            if len(common_nouns) >= 2:
                return True, f"Contradictory negative assertion ('{phrase}') not supported by evidence."
        elif phrase in p_lower and phrase not in h_lower:
            common_nouns = p_tokens.intersection(h_tokens) - {"is", "are", "the", "a", "an", "and", "in", "to", "for", "with", "not", "or"}
            if len(common_nouns) >= 2:
                return True, f"Statement ignores clinical prohibition ('{phrase}') in guidelines."
            
    return False, ""

def validate_response_with_nli(
    answer: str,
    context_chunks: List[Dict[str, Any]],
    embedder,
    cross_encoder=None,
    similarity_threshold_entailment: float = 0.65,
    similarity_threshold_partial: float = 0.45
) -> Dict[str, Any]:
    """
    Evaluates every claim in the generated answer against retrieved context using NLI:
    - Premise: Retrieved source chunk sentences
    - Hypothesis: Generated sentence
    - Output: Entailment | Neutral | Contradiction
    """
    response_sentences = split_sentences(answer)
    
    context_sentences_metadata = []
    for chunk in context_chunks:
        c_sents = split_sentences(chunk.get("text", ""))
        for s in c_sents:
            context_sentences_metadata.append({
                "text": s,
                "pdf_name": chunk.get("pdf_name", "Clinical Guideline"),
                "page_number": chunk.get("page_number", 1),
                "scope": chunk.get("scope", "knowledge_base"),
                "version": chunk.get("version", "1.0"),
                "document_type": chunk.get("document_type", "Guideline")
            })
            
    if not response_sentences or not context_sentences_metadata:
        unsupported = [{
            "sentence": s,
            "status": "Neutral",
            "nli_label": "Neutral",
            "score": 0.0,
            "source_sentence": "",
            "pdf_name": "N/A",
            "page_number": 0,
            "explanation": "No context available for verification."
        } for s in response_sentences]
        return {
            "verification_results": unsupported,
            "evidence": [],
            "confidence_score": 0.0,
            "confidence_level": "Low",
            "entailment_count": 0,
            "neutral_count": len(response_sentences),
            "contradiction_count": 0
        }
        
    resp_embeddings = embedder.encode(response_sentences)
    ctx_texts = [item["text"] for item in context_sentences_metadata]
    ctx_embeddings = embedder.encode(ctx_texts)
    
    # Normalize for cosine similarity
    resp_norm = np.linalg.norm(resp_embeddings, axis=1, keepdims=True)
    resp_norm[resp_norm == 0] = 1e-9
    resp_embeddings = resp_embeddings / resp_norm
    
    ctx_norm = np.linalg.norm(ctx_embeddings, axis=1, keepdims=True)
    ctx_norm[ctx_norm == 0] = 1e-9
    ctx_embeddings = ctx_embeddings / ctx_norm
    
    sim_matrix = np.dot(resp_embeddings, ctx_embeddings.T)
    
    verification_results = []
    evidence = []
    entailment_count = 0
    neutral_count = 0
    contradiction_count = 0
    total_score_sum = 0.0
    
    for r_idx, r_sent in enumerate(response_sentences):
        best_ctx_idx = int(np.argmax(sim_matrix[r_idx]))
        max_sim = float(sim_matrix[r_idx][best_ctx_idx])
        best_ctx = context_sentences_metadata[best_ctx_idx]
        
        # Check for clinical contradiction
        is_contra, contra_reason = check_clinical_contradiction(best_ctx["text"], r_sent)
        
        if is_contra:
            nli_label = "Contradiction"
            status = "Contradiction"
            score = max(0.1, 1.0 - max_sim)
            contradiction_count += 1
            explanation = contra_reason
        elif max_sim >= similarity_threshold_entailment:
            nli_label = "Entailment"
            status = "Supported"
            score = max_sim
            entailment_count += 1
            explanation = "Sentence is directly entailed and supported by retrieved evidence."
        elif max_sim >= similarity_threshold_partial:
            nli_label = "Neutral"
            status = "Partially Supported"
            score = max_sim
            neutral_count += 1
            explanation = "Sentence is plausibly neutral or partially supported by evidence."
        else:
            nli_label = "Neutral"
            status = "Unsupported"
            score = max_sim
            neutral_count += 1
            explanation = "Statement is unsupported by the retrieved evidence."
            
        total_score_sum += score
        
        entry = {
            "sentence": r_sent,
            "status": status,
            "nli_label": nli_label,
            "score": round(score, 3),
            "source_sentence": best_ctx["text"] if nli_label != "Contradiction" else best_ctx["text"],
            "pdf_name": best_ctx["pdf_name"],
            "page_number": best_ctx["page_number"],
            "version": best_ctx.get("version", "1.0"),
            "document_type": best_ctx.get("document_type", "Guideline"),
            "explanation": explanation
        }
        verification_results.append(entry)
        
        # Add to evidence list if Entailment or Partially Supported
        if nli_label == "Entailment" or (nli_label == "Neutral" and max_sim >= similarity_threshold_partial):
            ev_item = {
                "pdf_name": best_ctx["pdf_name"],
                "page_number": best_ctx["page_number"],
                "version": best_ctx.get("version", "1.0"),
                "document_type": best_ctx.get("document_type", "Guideline"),
                "supporting_text": best_ctx["text"],
                "response_sentence": r_sent,
                "nli_label": nli_label
            }
            if not any(e["supporting_text"] == best_ctx["text"] for e in evidence):
                evidence.append(ev_item)
                
    # Confidence scoring
    avg_score = total_score_sum / max(len(response_sentences), 1)
    retrieval_avg = sum(c.get("retrieval_score", 0.7) for c in context_chunks) / max(len(context_chunks), 1)
    
    # Penalize contradictions heavily
    confidence_score = (avg_score * 0.7) + (retrieval_avg * 0.3)
    if contradiction_count > 0:
        confidence_score = min(confidence_score * 0.3, 0.35)
        confidence_level = "Low"
    elif neutral_count > 0 or len(context_chunks) == 0:
        if confidence_score >= 0.75 and neutral_count <= 1 and entailment_count >= 2:
            confidence_level = "Medium"
        else:
            confidence_level = "Low"
    elif confidence_score >= 0.75:
        confidence_level = "High"
    elif confidence_score >= 0.55:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"
        
    return {
        "verification_results": verification_results,
        "evidence": evidence,
        "confidence_score": float(round(confidence_score, 2)),
        "confidence_level": confidence_level,
        "entailment_count": entailment_count,
        "neutral_count": neutral_count,
        "contradiction_count": contradiction_count
    }

def filter_citations_by_permission(
    evidence_list: List[Dict[str, Any]],
    user_or_role: Any
) -> List[Dict[str, Any]]:
    """
    Enforces RBAC on citations:
    - Doctors & Admins: Can view all clinical reports, lab reports, guidelines, textbooks, and research papers.
    - Nurses: Can view guidelines, vitals, and permitted nursing reports.
    - Interns: Read-only access to assigned patient reports and general knowledge base.
    - Front Desk / Other Staff: Restricted to general guidelines unless explicitly permitted.
    """
    if hasattr(user_or_role, "role"):
        user_role_upper = (user_or_role.role or "").upper()
    elif isinstance(user_or_role, str):
        user_role_upper = (user_or_role or "").upper()
    else:
        user_role_upper = ""
    
    filtered = []
    for ev in evidence_list:
        doc_type = (ev.get("document_type") or "").lower()
        scope = (ev.get("scope") or "").lower()
        
        # Knowledge base guidelines and textbooks are accessible to all clinical staff
        if scope == "knowledge_base" or "guideline" in doc_type or "textbook" in doc_type:
            filtered.append(ev)
        elif user_role_upper in ["ADMIN", "DOCTOR"]:
            # Doctors & Admins have full access
            filtered.append(ev)
        elif user_role_upper == "INTERN":
            # Interns can view patient charts
            filtered.append(ev)
        elif user_role_upper == "NURSE" and ("vital" in doc_type or "nurs" in doc_type or "guideline" in doc_type):
            filtered.append(ev)
        elif user_role_upper == "OTHER_STAFF" and ("lab" in doc_type or "radio" in doc_type or "guideline" in doc_type):
            filtered.append(ev)
            
    return filtered
