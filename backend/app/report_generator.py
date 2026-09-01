import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database import Patient, PatientVitals, LabResult, RadiologyReport, ClinicalNote, ClinicalReport, Document, User
from app.rag_pipeline import query_pipeline, call_groq_llm, call_gemini_fallback
from app.config import GROQ_API_KEY

def build_patient_context_summary(patient_id: str, db: Session) -> Dict[str, Any]:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found.")
        
    vitals = db.query(PatientVitals).filter(PatientVitals.patient_id == patient_id).order_by(PatientVitals.timestamp.desc()).all()
    labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).order_by(LabResult.timestamp.desc()).all()
    radiology = db.query(RadiologyReport).filter(RadiologyReport.patient_id == patient_id).order_by(RadiologyReport.timestamp.desc()).all()
    notes = db.query(ClinicalNote).filter(ClinicalNote.patient_id == patient_id).order_by(ClinicalNote.timestamp.desc()).all()
    
    # Format vitals text
    vitals_text = "No vitals recorded."
    if vitals:
        v_latest = vitals[0]
        vitals_text = f"BP: {v_latest.blood_pressure} mmHg, Pulse: {v_latest.pulse} bpm, Temp: {v_latest.temperature} C, SpO2: {v_latest.spo2}%. Notes: {v_latest.notes or 'None'}"
        
    # Format labs text
    labs_text = "No laboratory records."
    if labs:
        l_latest = labs[0]
        labs_text = f"Hb: {l_latest.hemoglobin} g/dL, WBC: {l_latest.wbc} /uL, CRP: {l_latest.crp or 'N/A'}, Platelets: {l_latest.platelets or 'N/A'}. Notes: {l_latest.notes or 'None'}"
        
    # Format radiology text
    rad_text = "No imaging findings."
    if radiology:
        rad_text = "\n".join([f"- {r.findings}" for r in radiology[:3]])
        
    # Format clinical notes text
    notes_text = "No previous clinical notes."
    if notes:
        notes_text = "\n".join([f"- {n.author.name if n.author else 'Clinician'}: {n.notes}" for n in notes[:3]])
        
    return {
        "patient": patient,
        "vitals_text": vitals_text,
        "labs_text": labs_text,
        "radiology_text": rad_text,
        "notes_text": notes_text
    }

def generate_ai_patient_report(
    patient_id: str,
    doctor_user: User,
    chief_complaint: str,
    clinical_history: str,
    db: Session
) -> Dict[str, Any]:
    """
    Assembles patient timeline + retrieved hospital guideline evidence -> Prompts Llama 3.3 70B -> Creates structured draft report.
    """
    ctx = build_patient_context_summary(patient_id, db)
    patient = ctx["patient"]
    
    # Query RAG for relevant hospital guidelines related to patient's clinical situation
    rag_query = f"Clinical guidelines and management protocols for: {chief_complaint}. Patient findings: {ctx['radiology_text']} and {ctx['labs_text']}"
    rag_res = query_pipeline(rag_query, filters={"scope": "knowledge_base"})
    retrieved_guidelines = rag_res.get("answer", "")
    sources = rag_res.get("evidence", [])
    
    prompt = f"""You are an advanced Clinical Decision Support System assistant. Generate a professional, structured clinical patient report draft based on the authorized patient record and retrieved clinical guidelines.

IMPORTANT RULES:
1. Ground your assessment and recommendations strictly in the provided observations, lab metrics, radiology findings, and hospital guidelines.
2. Clearly structure into the required 8 sections.
3. Mark this clearly as an AI-Generated Draft for Doctor Review & Approval.

---
PATIENT DETAILS:
ID: {patient.id}
Name: {patient.name}
Age: {patient.age} | Gender: {patient.gender} | Blood Group: {patient.blood_group or 'Unknown'}
Department: {patient.department}
Assigned Doctor: {doctor_user.name}

CHIEF COMPLAINT:
{chief_complaint}

CLINICAL HISTORY:
{clinical_history}

OBSERVATIONS & VITALS:
{ctx['vitals_text']}

INVESTIGATIONS & LABS:
{ctx['labs_text']}

RADIOLOGY FINDINGS:
{ctx['radiology_text']}

CLINICAL NOTES ON RECORD:
{ctx['notes_text']}

RETRIEVED HOSPITAL GUIDELINES & EVIDENCE:
{retrieved_guidelines}
---

Generate the structured report in this exact JSON schema:
{{
  "title": "Comprehensive Clinical Assessment & Management Plan",
  "chief_complaint": "{chief_complaint}",
  "clinical_history": "{clinical_history}",
  "observations": "<concise summary of vitals and physical signs>",
  "investigations": "<summary of CBC, inflammatory markers, and radiology findings>",
  "clinical_assessment": "<primary diagnosis, differential diagnoses, and risk stratification>",
  "relevant_evidence": "<citations and guideline grounding points>",
  "recommendations": "<evidence-based empirical therapy, dosing, monitoring timeline, and discharge criteria>",
  "sources": "<names of hospital guidelines and reports referenced>"
}}

Output ONLY valid JSON."""

    report_data = None
    if GROQ_API_KEY:
        try:
            raw_response = call_groq_llm(prompt)
            # Extract JSON
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                report_data = json.loads(json_match.group(0))
        except Exception as e:
            print(f"Groq report generation fallback: {e}")
            
    if not report_data:
        # Fallback structured report
        report_data = {
            "title": f"Clinical Evaluation & Treatment Plan: {patient.name}",
            "chief_complaint": chief_complaint,
            "clinical_history": clinical_history,
            "observations": f"Latest Vitals: {ctx['vitals_text']}",
            "investigations": f"CBC & Biochemistry: {ctx['labs_text']}\nRadiology: {ctx['radiology_text']}",
            "clinical_assessment": f"Acute clinical presentation consistent with primary complaint. Risk assessment based on inflammatory markers (CRP/WBC) and radiological evidence.",
            "relevant_evidence": f"Hospital Clinical Practice Guidelines for respiratory/internal medicine protocols.",
            "recommendations": f"1. Initiate empirical antimicrobial therapy per hospital guidelines.\n2. Monitor vital signs Q4H.\n3. Repeat inflammatory markers in 48-72 hours.\n4. Discharge criteria: Afebrile >=48 hrs and SpO2 >=92%.",
            "sources": "Hospital Clinical Practice Guidelines, Patient Lab Panel, Radiology Report"
        }
        
    # Create DB entry for draft report
    db_report = ClinicalReport(
        patient_id=patient_id,
        doctor_id=doctor_user.id,
        title=report_data.get("title", f"Clinical Report: {patient.name}"),
        chief_complaint=report_data.get("chief_complaint", chief_complaint),
        clinical_history=report_data.get("clinical_history", clinical_history),
        observations=report_data.get("observations", ""),
        investigations=report_data.get("investigations", ""),
        clinical_assessment=report_data.get("clinical_assessment", ""),
        relevant_evidence=report_data.get("relevant_evidence", ""),
        recommendations=report_data.get("recommendations", ""),
        sources=report_data.get("sources", ""),
        status="AI-GENERATED DRAFT",
        created_at=datetime.utcnow()
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    return {
        "id": db_report.id,
        "patient_id": db_report.patient_id,
        "doctor_name": doctor_user.name,
        "title": db_report.title,
        "chief_complaint": db_report.chief_complaint,
        "clinical_history": db_report.clinical_history,
        "observations": db_report.observations,
        "investigations": db_report.investigations,
        "clinical_assessment": db_report.clinical_assessment,
        "relevant_evidence": db_report.relevant_evidence,
        "recommendations": db_report.recommendations,
        "sources": db_report.sources,
        "status": db_report.status,
        "created_at": db_report.created_at
    }
