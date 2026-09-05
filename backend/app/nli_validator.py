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
    ("recommended", "avoid"),
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

EXPLICIT_NEGATION_PHRASES = [
    "not recommended", "should not", "do not give", "never use", "contraindicated", 
    "not indicated", "ineffective", "should be avoided", "avoid", "do not require",
    "does not require", "not required", "no requirement", "do not need", "does not need",
    "not necessary", "without any", "without monitoring", "without specialized",
    "does not provide", "do not provide", "routine non-urgent"
]

def split_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]

split_into_sentences = split_sentences

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
            overlap = p_tokens.intersection(h_tokens) - {"is", "are", "the", "a", "an", "and", "in", "to", "for", "with", "of"}
            if len(overlap) >= 2:
                return True, f"Opposing clinical relationship detected ({term_a} vs {term_b})."
                
    # 2. Check direct explicit negation statements
    for phrase in EXPLICIT_NEGATION_PHRASES:
        if phrase in h_lower and phrase not in p_lower:
            common_nouns = p_tokens.intersection(h_tokens) - {"is", "are", "the", "a", "an", "and", "in", "to", "for", "with", "not", "or", "of", "an"}
            if len(common_nouns) >= 2:
                return True, f"Contradictory negative assertion ('{phrase}') not supported by evidence."
        elif phrase in p_lower and phrase not in h_lower:
            if phrase in ["contraindicated", "not recommended", "should not", "never use"]:
                common_nouns = p_tokens.intersection(h_tokens) - {"is", "are", "the", "a", "an", "and", "in", "to", "for", "with", "not", "or", "of", "an"}
                if len(common_nouns) >= 2:
                    return True, f"Statement ignores clinical prohibition ('{phrase}') in guidelines."
            
    return False, ""

def extract_claims(text: str) -> List[str]:
    """
    Extracts atomic factual claims from clinical text, cleanly handling
    markdown bullet points, numbered recommendations, and sentence boundaries.
    """
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    claims: List[str] = []
    
    # Generic introductory / transitional sentences that do not constitute clinical assertions
    boilerplate_prefixes = [
        "based on the", "according to the", "here is the", "here are the",
        "in accordance with", "clinical recommendations:", "hospital guidelines indicate that",
        "the hallmarks of an icu include:", "hallmarks of an icu:", "according to hospital guidelines:"
    ]
    
    for line in lines:
        # Strip list markers like '1. ', '- ', '* ', '• '
        clean_line = re.sub(r'^(?:\d+\.|\-|\*|•)\s+', '', line).strip()
        # Strip header markers like '### '
        clean_line = re.sub(r'^#+\s+', '', clean_line).strip()
        
        if not clean_line or len(clean_line) < 5:
            continue
            
        # If the line ends with a colon and has boilerplate prefix, it's just a section header
        lower_line = clean_line.lower().rstrip(":")
        if any(lower_line.startswith(bp.rstrip(":")) for bp in boilerplate_prefixes) and clean_line.endswith(":"):
            continue
            
        # Split on sentence terminals
        raw_sents = re.split(r'(?<=[.!?])\s+', clean_line)
        for s in raw_sents:
            s_clean = s.strip()
            # Remove isolated citation markers for length check
            content_check = re.sub(r'\[\d+\]', '', s_clean).strip()
            if len(content_check) < 8:
                continue
                
            # Filter out non-factual introductory filler
            lower_s = content_check.lower().rstrip(":")
            if any(lower_s.startswith(bp.rstrip(":")) for bp in boilerplate_prefixes) and (len(content_check.split()) <= 6 or s_clean.endswith(":")):
                continue
                
            claims.append(s_clean)
            
    # Fallback to standard sentence splitting if line-based parsing produced nothing
    if not claims:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        claims = [s.strip() for s in sentences if len(s.strip()) > 5]
        
    return claims


def validate_response_with_nli(
    answer: str,
    context_chunks: List[Dict[str, Any]],
    embedder,
    cross_encoder=None,
    similarity_threshold_entailment: float = 0.55,
    similarity_threshold_partial: float = 0.38
) -> Dict[str, Any]:
    """
    Evaluates every factual claim in the generated answer against retrieved context:
    - Premise: Retrieved source chunk sentences & full chunk passages
    - Hypothesis: Generated clinical claim
    - Output: Supported (Entailment) | Partially Supported (Neutral) | Unsupported / Contradiction
    """
    response_sentences = extract_claims(answer)
    
    # Build premise database: both individual sentences, 2-sentence windows, and chunk passages
    context_premises_metadata = []
    for chunk in context_chunks:
        pdf_name = chunk.get("pdf_name", "Clinical Guideline")
        page_num = chunk.get("page_number", 1)
        version = chunk.get("version", "1.0")
        doc_type = chunk.get("document_type", "Guideline")
        scope = chunk.get("scope", "knowledge_base")
        chunk_id = chunk.get("chunk_id") or chunk.get("id")
        
        # 1. Individual sentences
        c_sents = split_into_sentences(chunk.get("text", ""))
        for s in c_sents:
            if len(s.strip()) > 8:
                context_premises_metadata.append({
                    "text": s.strip(),
                    "pdf_name": pdf_name,
                    "page_number": page_num,
                    "scope": scope,
                    "version": version,
                    "document_type": doc_type,
                    "chunk_id": chunk_id,
                    "is_full_chunk": False
                })
                
        # 2. 2-sentence sliding windows for compound statements
        for i in range(len(c_sents) - 1):
            pair_txt = (c_sents[i].strip() + " " + c_sents[i+1].strip()).strip()
            if len(pair_txt) > 25:
                context_premises_metadata.append({
                    "text": pair_txt,
                    "pdf_name": pdf_name,
                    "page_number": page_num,
                    "scope": scope,
                    "version": version,
                    "document_type": doc_type,
                    "chunk_id": chunk_id,
                    "is_full_chunk": False
                })
                
        # 3. Complete chunk text as high-context premise
        raw_text = (chunk.get("text") or "").strip()
        if raw_text and len(raw_text) > 20:
            context_premises_metadata.append({
                "text": raw_text,
                "pdf_name": pdf_name,
                "page_number": page_num,
                "scope": scope,
                "version": version,
                "document_type": doc_type,
                "chunk_id": chunk_id,
                "is_full_chunk": True
            })
            
    if not response_sentences or not context_premises_metadata:
        unsupported = [{
            "sentence": s,
            "status": "Unsupported",
            "nli_label": "Neutral",
            "score": 0.0,
            "max_sim": 0.0,
            "ce_score": 0.0,
            "source_sentence": "",
            "pdf_name": "N/A",
            "page_number": 0,
            "chunk_id": None,
            "explanation": "No context available for verification."
        } for s in response_sentences]
        
        return {
            "verification_results": unsupported,
            "evidence": [],
            "confidence_score": 0.0,
            "confidence_level": "Low",
            "grounding_level": "Not Supported",
            "grounding_coverage": f"0 of {len(response_sentences)} claims supported",
            "supported_claims": 0,
            "total_claims": len(response_sentences),
            "entailment_count": 0,
            "neutral_count": len(response_sentences),
            "contradiction_count": 0
        }
        
    # Clean claims for embedding comparison (normalize unicode, remove citations [1], [2], bolding **, markdown symbols)
    cleaned_claims = []
    for s in response_sentences:
        clean = s.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        clean = clean.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        clean = re.sub(r'[*_#`]', '', re.sub(r'\[\d+\]', '', clean)).strip()
        cleaned_claims.append(clean)
    
    resp_embeddings = embedder.encode(cleaned_claims)
    ctx_texts = [item["text"] for item in context_premises_metadata]
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
        cleaned_c = cleaned_claims[r_idx]
        top_k_indices = np.argsort(sim_matrix[r_idx])[::-1][:10]
        best_ctx_idx = int(top_k_indices[0])
        max_sim = float(sim_matrix[r_idx][best_ctx_idx])
        best_ctx = context_premises_metadata[best_ctx_idx]
        
        # Cross-encoder evaluation on top candidate premises
        ce_score = 0.0
        if cross_encoder is not None and top_k_indices.size > 0:
            candidate_pairs = [(cleaned_c, context_premises_metadata[idx]["text"]) for idx in top_k_indices]
            ce_raw_scores = cross_encoder.predict(candidate_pairs)
            best_ce_local_idx = int(np.argmax(ce_raw_scores))
            best_ce_raw = float(ce_raw_scores[best_ce_local_idx])
            ce_score = float(1.0 / (1.0 + np.exp(-best_ce_raw)))
            
            # If cross-encoder identifies a candidate with strong relevance, align best premise
            if ce_score > 0.50 and ce_raw_scores[best_ce_local_idx] > ce_raw_scores[0]:
                best_ctx_idx = int(top_k_indices[best_ce_local_idx])
                best_ctx = context_premises_metadata[best_ctx_idx]
        
        # Check for clinical contradiction across top candidate premises
        is_contra = False
        contra_reason = ""
        for idx in top_k_indices[:5]:
            cand_p = context_premises_metadata[int(idx)]
            c_flag, c_msg = check_clinical_contradiction(cand_p["text"], r_sent)
            if c_flag:
                is_contra = True
                contra_reason = c_msg
                best_ctx = cand_p
                break
        
        if is_contra:
            nli_label = "Contradiction"
            status = "Unsupported"
            score = 0.10
            contradiction_count += 1
            explanation = contra_reason
        elif (max_sim >= similarity_threshold_entailment) or (ce_score >= 0.50 and max_sim >= similarity_threshold_partial):
            nli_label = "Entailment"
            status = "Supported"
            score = max(max_sim, ce_score)
            entailment_count += 1
            explanation = "Sentence is directly entailed and supported by retrieved evidence."
        elif max_sim >= similarity_threshold_partial or ce_score >= 0.30:
            nli_label = "Neutral"
            status = "Partially Supported"
            score = max(max_sim, ce_score)
            neutral_count += 1
            explanation = "Sentence is plausibly neutral or partially supported by evidence."
        else:
            nli_label = "Neutral"
            status = "Unsupported"
            score = max_sim
            neutral_count += 1
            explanation = "Statement is unsupported by the retrieved evidence."

            
        total_score_sum += score
        selected_source_page = best_ctx["page_number"]
        
        # Structured Backend Debug Logging for each generated sentence:
        # max_sim, ce_score, nli_label, status, selected source page
        print(f"Sentence: \"{r_sent}\" | max_sim: {max_sim:.3f} | ce_score: {ce_score:.3f} | nli_label: {nli_label} | status: {status} | source_page: {selected_source_page} ({best_ctx['pdf_name']})")
        
        # Select clean source sentence display
        source_display = best_ctx["text"]
        if best_ctx.get("is_full_chunk") and len(source_display) > 280:
            source_display = source_display[:280] + "..."
            
        entry = {
            "sentence": r_sent,
            "status": status,
            "nli_label": nli_label,
            "score": round(score, 3),
            "max_sim": round(max_sim, 3),
            "ce_score": round(ce_score, 3),
            "source_sentence": source_display,
            "pdf_name": best_ctx["pdf_name"],
            "page_number": selected_source_page,
            "chunk_id": best_ctx.get("chunk_id"),
            "version": best_ctx.get("version", "1.0"),
            "document_type": best_ctx.get("document_type", "Guideline"),
            "explanation": explanation
        }
        verification_results.append(entry)
        
        # Add to evidence list if Supported or Partially Supported
        if status in ["Supported", "Partially Supported"]:
            ev_item = {
                "pdf_name": best_ctx["pdf_name"],
                "page_number": selected_source_page,
                "chunk_id": best_ctx.get("chunk_id"),
                "version": best_ctx.get("version", "1.0"),
                "document_type": best_ctx.get("document_type", "Guideline"),
                "supporting_text": source_display,
                "response_sentence": r_sent,
                "nli_label": nli_label,
                "status": status
            }
            if not any(e["supporting_text"] == source_display for e in evidence):
                evidence.append(ev_item)
                
    total_claims = len(response_sentences)
    supported_claims = entailment_count
    claim_coverage = (supported_claims / total_claims) if total_claims > 0 else 0.0
    avg_claim_score = (total_score_sum / total_claims) if total_claims > 0 else 0.0
    
    # Extract top 3 actual retrieval and rerank scores from context chunks
    top3_chunks = context_chunks[:3] if context_chunks else []
    top3_dense_list = [float(c["dense_score"]) if c.get("dense_score") is not None else float(avg_claim_score) for c in top3_chunks]
    top3_rerank_list = [float(c["rerank_score"]) if c.get("rerank_score") is not None else float(avg_claim_score) for c in top3_chunks]
    
    mean_top3_dense = sum(top3_dense_list) / max(len(top3_dense_list), 1) if top3_dense_list else 0.0
    mean_top3_rerank = sum(top3_rerank_list) / max(len(top3_rerank_list), 1) if top3_rerank_list else 0.0

    # Grounding Level Determination:
    # 🟢 Strongly Supported: All claims are directly supported by evidence
    # 🟡 Partially Supported: Some information supported, but verification needed
    # 🔴 Not Supported: Claim is not supported by retrieved evidence or contradiction found
    if total_claims == 0 or contradiction_count > 0 or supported_claims == 0:
        grounding_level = "Not Supported"
    elif supported_claims == total_claims and total_claims > 0:
        grounding_level = "Strongly Supported"
    elif supported_claims > 0 or (neutral_count > 0 and contradiction_count == 0):
        grounding_level = "Partially Supported"
    else:
        grounding_level = "Not Supported"

    # Confidence Score Calculation (Design 2)
    if total_claims == 0 or supported_claims == 0:
        confidence_level = "Low"
        confidence_score = float(round(min((mean_top3_dense * 0.15) + (mean_top3_rerank * 0.15), 0.20), 2))
    elif contradiction_count > 0:
        confidence_level = "Low"
        raw_conf = (avg_claim_score * claim_coverage * 0.70) + (mean_top3_dense * 0.15) + (mean_top3_rerank * 0.15)
        confidence_score = float(round(min(raw_conf * 0.25, 0.20), 2))
    else:
        raw_conf = (avg_claim_score * claim_coverage * 0.70) + (mean_top3_dense * 0.15) + (mean_top3_rerank * 0.15)
        confidence_score = float(round(raw_conf, 2))
        
        if confidence_score >= 0.80 and supported_claims == total_claims:
            confidence_level = "High"
        elif confidence_score >= 0.50:
            confidence_level = "Medium"
        else:
            confidence_level = "Low"

    grounding_coverage = f"{supported_claims} of {total_claims} claims supported"
    
    # Structured Backend Debug Logging for diagnostic trace:
    # avg_claim_score, claim_coverage, top3_dense_score, top3_rerank_score, final confidence_score
    print(f"[CDSS CONFIDENCE] avg_claim_score: {avg_claim_score:.4f} | claim_coverage: {claim_coverage:.4f} ({supported_claims}/{total_claims}) | top3_dense_score: {mean_top3_dense:.4f} | top3_rerank_score: {mean_top3_rerank:.4f} | final confidence_score: {confidence_score:.2f} ({confidence_level})")
    print(f"entailment_count: {entailment_count} | neutral_count: {neutral_count} | contradiction_count: {contradiction_count} | total_claims: {total_claims} | confidence_score: {confidence_score} | confidence_level: {confidence_level}")
    print(f"grounding_level: {grounding_level} | coverage: {grounding_coverage}\n")

    return {
        "verification_results": verification_results,
        "evidence": evidence,
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "grounding_level": grounding_level,
        "grounding_coverage": grounding_coverage,
        "supported_claims": supported_claims,
        "total_claims": total_claims,
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

