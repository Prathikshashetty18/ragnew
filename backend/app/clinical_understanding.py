"""
Clinical Query Understanding and Expansion module for CDSS.

Extracts structured clinical entities:
- Clinical conditions / Diagnoses
- Symptoms & signs
- Medications & drug classes
- Dosages, frequencies, and units
- Patient population & demographics
- Urgency / Emergency status
- Diagnostic investigations & lab tests
- Treatment intent vs. diagnostic intent
- Contraindications

Generates retrieval-oriented query variants while strictly preserving the original query as primary.
Avoids hallucinating patient facts: missing fields remain None / empty.
"""

import re
from typing import Dict, List, Any, Optional

# Clinical Conditions and Disease Lexicon
CLINICAL_CONDITIONS = {
    "pneumonia": ["pneumonia", "community-acquired pneumonia", "cap", "hospital-acquired pneumonia", "hap", "ventilator-associated pneumonia", "vap", "aspiration pneumonia"],
    "tuberculosis": ["tuberculosis", "tb", "pulmonary tb", "pulmonary tuberculosis", "mycobacterium tuberculosis", "mtb", "extrapulmonary tb"],
    "diabetes": ["diabetes", "diabetes mellitus", "type 1 diabetes", "type 2 diabetes", "t1d", "t2d", "dka", "diabetic ketoacidosis", "hhs", "hyperosmolar"],
    "diabetic_nephropathy": ["diabetic nephropathy", "microalbuminuria", "kimmelstiel-wilson", "diabetic kidney disease"],
    "diabetic_retinopathy": ["diabetic retinopathy", "microaneurysms", "cotton-wool spots", "neovascularization"],
    "diabetic_neuropathy": ["diabetic neuropathy", "polyneuropathy", "glove-and-stocking"],
    "meningitis": ["meningitis", "bacterial meningitis", "viral meningitis", "meningococcal"],
    "sepsis": ["sepsis", "septic shock", "severe sepsis", "bacteremia"],
    "hypertension": ["hypertension", "high blood pressure", "hypertensive crisis"],
    "asthma": ["asthma", "bronchospasm", "status asthmaticus"],
    "copd": ["copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
    "heart_failure": ["heart failure", "congestive heart failure", "chf"],
    "stroke": ["stroke", "cva", "ischemic stroke", "cerebrovascular accident", "transient ischemic attack", "tia"],
    "myocardial_infarction": ["myocardial infarction", "heart attack", "stemi", "nstemi", "acute coronary syndrome"],
    "pulmonary_embolism": ["pulmonary embolism", "pe", "deep vein thrombosis", "dvt"],
    "covid": ["covid", "covid-19", "sars-cov-2", "coronavirus"],
}

# Symptom clusters mapping to potential clinical concepts
SYMPTOM_CLUSTERS = {
    "meningitis": [
        {"fever", "neck stiffness"},
        {"fever", "stiff neck"},
        {"neck stiffness", "altered consciousness"},
        {"fever", "altered mental status", "headache"},
        {"fever", "altered consciousness", "neck stiffness"}
    ],
    "pneumonia": [
        {"cough", "fever", "chest pain"},
        {"cough", "fever", "dyspnea"},
        {"cough", "fever", "sputum"},
        {"productive cough", "fever"},
        {"pleuritic chest pain", "fever"}
    ],
    "tuberculosis": [
        {"cough", "hemoptysis"},
        {"cough", "night sweats"},
        {"cough", "weight loss"},
        {"fever", "night sweats", "weight loss"},
        {"persistent cough", "fever"}
    ],
    "diabetic_ketoacidosis": [
        {"hyperglycemia", "acidosis"},
        {"kussmaul", "ketones"},
        {"acetone breath", "vomiting"},
        {"dehydration", "altered mental status", "polyuria"}
    ]
}

# Medications & Antimicrobials
MEDICATIONS = {
    "amoxicillin": ["amoxicillin", "amoxil", "augmentin", "amoxicillin-clavulanate"],
    "ceftriaxone": ["ceftriaxone", "rocephin"],
    "azithromycin": ["azithromycin", "zithromax"],
    "levofloxacin": ["levofloxacin", "levaquin"],
    "doxycycline": ["doxycycline", "vibramycin"],
    "vancomycin": ["vancomycin", "vancocin"],
    "ampicillin_sulbactam": ["ampicillin-sulbactam", "unasyn"],
    "rifampicin": ["rifampicin", "rifampin"],
    "isoniazid": ["isoniazid", "inh"],
    "pyrazinamide": ["pyrazinamide"],
    "ethambutol": ["ethambutol"],
    "insulin": ["insulin", "regular insulin", "glargine", "lispro"],
    "metformin": ["metformin", "glucophage"],
    "lisinopril": ["lisinopril", "ace inhibitor", "acei"],
    "losartan": ["losartan", "arb"],
    "aspirin": ["aspirin", "asa"],
    "heparin": ["heparin", "enoxaparin", "lmwh"],
}

# Diagnostic investigations & lab markers
INVESTIGATIONS = {
    "curb65": ["curb-65", "curb 65", "curb65"],
    "cbc": ["cbc", "complete blood count", "hemoglobin", "wbc", "leukocyte", "neutrophils", "lymphocytes", "platelets"],
    "crp": ["crp", "c-reactive protein"],
    "esr": ["esr", "erythrocyte sedimentation rate"],
    "chest_xray": ["chest x-ray", "chest xray", "cxr", "radiograph", "radiography"],
    "ct_scan": ["ct scan", "computed tomography", "hrct"],
    "mri": ["mri", "magnetic resonance imaging"],
    "genexpert": ["genexpert", "xpert mtb", "xpert mtb/rif", "molecular testing"],
    "afb_stain": ["afb", "acid-fast bacilli", "sputum smear", "ziehl-neelsen"],
    "sputum_culture": ["sputum culture", "mgit", "liquid culture"],
    "blood_glucose": ["blood glucose", "blood sugar", "hba1c", "glycated hemoglobin"],
    "ketones": ["ketones", "ketonuria", "ketonemia", "beta-hydroxybutyrate"],
    "arterial_blood_gas": ["abg", "arterial blood gas", "serum bicarbonate", "ph"],
    "renal_panel": ["creatinine", "serum creatinine", "bun", "blood urea nitrogen", "gfr"],
    "lumbar_puncture": ["lumbar puncture", "csf", "cerebrospinal fluid", "spinal tap"]
}

# Population / Demographics terms
POPULATIONS = {
    "pediatric": ["child", "children", "pediatric", "infant", "toddler", "neonate", "newborn"],
    "elderly": ["elderly", "geriatric", "age >= 65", "older adult", "senior"],
    "adult": ["adult", "adults"],
    "pregnancy": ["pregnant", "pregnancy", "trimester", "gestational", "lactating", "breastfeeding"]
}

# Urgency keywords
URGENCY_KEYWORDS = {
    "emergency": ["emergency", "stat", "urgent", "immediate", "icu", "critical", "severe", "life-threatening", "shock", "acute"],
    "inpatient": ["inpatient", "admission", "admit", "hospitalized", "ward"],
    "outpatient": ["outpatient", "ambulatory", "home", "mild", "low risk"]
}


class ClinicalEntityExtractor:
    """Extracts clinical concepts, drugs, dosages, and patient variables from queries."""

    @staticmethod
    def extract_entities(query: str) -> Dict[str, Any]:
        q_lower = query.lower()
        extracted: Dict[str, Any] = {
            "conditions": [],
            "symptoms": [],
            "medications": [],
            "dosages": [],
            "investigations": [],
            "populations": [],
            "urgency": None,
            "treatment_intent": False,
            "diagnostic_intent": False,
            "inferred_syndromes": []
        }

        # 1. Detect explicit clinical conditions
        for cond_key, variants in CLINICAL_CONDITIONS.items():
            for v in variants:
                pattern = r'\b' + re.escape(v) + r'\b'
                if re.search(pattern, q_lower):
                    if cond_key not in extracted["conditions"]:
                        extracted["conditions"].append(cond_key)
                    break

        # 2. Detect symptoms & signs
        symptom_patterns = [
            "fever", "cough", "productive cough", "shortness of breath", "dyspnea",
            "chest pain", "pleuritic chest pain", "pleuritic pain", "neck stiffness",
            "stiff neck", "altered consciousness", "altered mental status", "confusion",
            "headache", "night sweats", "weight loss", "hemoptysis", "vomiting",
            "polyuria", "polydipsia", "dehydration", "kussmaul", "acetone breath"
        ]
        detected_symptoms = set()
        for sym in symptom_patterns:
            if re.search(r'\b' + re.escape(sym) + r'\b', q_lower):
                detected_symptoms.add(sym)
        extracted["symptoms"] = sorted(list(detected_symptoms))

        # Check symptom clusters for syndrome inference (without hallucinating patient facts)
        for syndrome, cluster_list in SYMPTOM_CLUSTERS.items():
            for cluster in cluster_list:
                if cluster.issubset(detected_symptoms):
                    if syndrome not in extracted["inferred_syndromes"]:
                        extracted["inferred_syndromes"].append(syndrome)
                    break

        # 3. Detect medications
        for med_key, variants in MEDICATIONS.items():
            for v in variants:
                pattern = r'\b' + re.escape(v) + r'\b'
                if re.search(pattern, q_lower):
                    if med_key not in extracted["medications"]:
                        extracted["medications"].append(med_key)
                    break

        # 4. Extract dosages, frequencies, and lab values with units
        dosage_patterns = [
            r'\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|units|u|ml|l)\b(?:\s*(?:tid|bid|qid|daily|po|iv|im|q\d+h|hours?))?',
            r'\b\d+(?:\.\d+)?\s*(?:g/dl|mg/dl|mmol/l|mEq/l|/ul|mm/hr)\b',
            r'\b\d{1,3}(?:,\d{3})+\s*(?:/ul|wbc|platelets)?\b',
            r'\bcurb(?:-|\s*)65\s*(?:score)?\s*(?:>=|>|<=|<|=)?\s*\d+\b'
        ]
        for dp in dosage_patterns:
            matches = re.findall(dp, q_lower)
            for m in matches:
                if m.strip() and m.strip() not in extracted["dosages"]:
                    extracted["dosages"].append(m.strip())

        # 5. Detect investigations
        for inv_key, variants in INVESTIGATIONS.items():
            for v in variants:
                pattern = r'\b' + re.escape(v) + r'\b'
                if re.search(pattern, q_lower):
                    if inv_key not in extracted["investigations"]:
                        extracted["investigations"].append(inv_key)
                    break

        # 6. Detect populations
        for pop_key, variants in POPULATIONS.items():
            for v in variants:
                pattern = r'\b' + re.escape(v) + r'\b'
                if re.search(pattern, q_lower):
                    if pop_key not in extracted["populations"]:
                        extracted["populations"].append(pop_key)
                    break

        # 7. Detect urgency
        for urg_level, words in URGENCY_KEYWORDS.items():
            for w in words:
                pattern = r'\b' + re.escape(w) + r'\b'
                if re.search(pattern, q_lower):
                    extracted["urgency"] = urg_level
                    break
            if extracted["urgency"]:
                break

        # 8. Detect clinical intent
        treatment_keywords = ["treat", "treatment", "therapy", "antibiotic", "dose", "dosage", "prescribe", "management", "medication", "drug", "regimen"]
        diagnostic_keywords = ["diagnos", "criteria", "workup", "screen", "test", "investigation", "symptom", "sign", "suspect", "identify", "evaluate"]

        if any(tk in q_lower for tk in treatment_keywords):
            extracted["treatment_intent"] = True
        if any(dk in q_lower for dk in diagnostic_keywords):
            extracted["diagnostic_intent"] = True

        return extracted


class ClinicalQueryExpander:
    """Generates focused retrieval variants while preserving the original query as primary."""

    @staticmethod
    def expand_query(query: str, entities: Optional[Dict[str, Any]] = None) -> List[str]:
        if entities is None:
            entities = ClinicalEntityExtractor.extract_entities(query)

        variants: List[str] = [query]  # Primary query is ALWAYS first

        conditions = entities.get("conditions", [])
        inferred = entities.get("inferred_syndromes", [])
        all_conditions = list(dict.fromkeys(conditions + inferred))

        medications = entities.get("medications", [])
        investigations = entities.get("investigations", [])
        urgency = entities.get("urgency")

        # Variant: Condition + Intent
        for cond in all_conditions:
            cond_display = cond.replace("_", " ")
            if entities.get("diagnostic_intent") or not entities.get("treatment_intent"):
                variants.append(f"{cond_display} diagnostic criteria workup guideline")
            if entities.get("treatment_intent") or not entities.get("diagnostic_intent"):
                variants.append(f"{cond_display} empirical antibiotic treatment guideline")
            if urgency == "emergency":
                variants.append(f"{cond_display} emergency critical care protocol")

        # Variant: Medication + Condition
        for med in medications:
            med_display = med.replace("_", " ")
            for cond in all_conditions:
                cond_display = cond.replace("_", " ")
                variants.append(f"{med_display} dosage administration {cond_display} guideline")
            if not all_conditions:
                variants.append(f"{med_display} clinical dosage indication hospital guideline")

        # Variant: Investigation + Condition
        for inv in investigations:
            inv_display = inv.replace("_", " ")
            for cond in all_conditions:
                cond_display = cond.replace("_", " ")
                variants.append(f"{inv_display} in {cond_display} clinical guideline")
            if not all_conditions:
                variants.append(f"{inv_display} findings report")

        # Variant: Symptom cluster concept
        symptoms = entities.get("symptoms", [])
        if symptoms and not all_conditions:
            sym_str = " ".join(symptoms[:3])
            variants.append(f"clinical guideline management for {sym_str}")

        # Deduplicate while preserving order
        seen = set()
        unique_variants = []
        for v in variants:
            clean_v = re.sub(r'\s+', ' ', v).strip()
            if clean_v.lower() not in seen:
                seen.add(clean_v.lower())
                unique_variants.append(clean_v)

        # Cap expansion variants to top 4 to avoid search dilution
        return unique_variants[:4]
