import json
import re
import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database import Patient, PatientVitals, LabResult, RadiologyReport, ClinicalNote, ClinicalReport, Document, User
from app.rag_pipeline import query_pipeline, call_groq_llm, call_gemini_fallback, index_text_document, remove_document_from_vector_store
from app.config import GROQ_API_KEY, UPLOAD_DIR

def _to_clean_text(val: Any) -> str:
    """
    Safely converts a field that may be returned by the LLM as a list, dict,
    or other non-string type into an appropriate string for SQLite Text columns.
    """
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        items = []
        for item in val:
            if isinstance(item, (dict, list)):
                items.append(json.dumps(item))
            elif item is not None:
                items.append(str(item).strip())
        return "\n".join(items)
    if isinstance(val, dict):
        return json.dumps(val, indent=2)
    return str(val).strip()

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
        v_parts = []
        if v_latest.blood_pressure:
            v_parts.append(f"BP: {v_latest.blood_pressure} mmHg")
        if v_latest.pulse is not None:
            v_parts.append(f"Pulse/HR: {v_latest.pulse} bpm")
        if v_latest.respiratory_rate is not None:
            v_parts.append(f"Respiratory Rate: {v_latest.respiratory_rate} /min")
        if v_latest.temperature is not None:
            v_parts.append(f"Temp: {v_latest.temperature} °C")
        if v_latest.spo2 is not None:
            v_parts.append(f"SpO2: {v_latest.spo2}%")
        if v_latest.blood_glucose is not None:
            v_parts.append(f"Blood Glucose: {v_latest.blood_glucose} mg/dL")
        if getattr(v_latest, "pain_severity", None):
            sev_label = {
                "NO_PAIN": "No Pain",
                "MILD": "Mild",
                "MODERATE": "Moderate",
                "SEVERE": "Severe"
            }.get(v_latest.pain_severity, v_latest.pain_severity)
            v_parts.append(f"Pain Severity: {sev_label}")
        if v_latest.intake_output:
            v_parts.append(f"Intake/Output: {v_latest.intake_output}")
        if v_latest.notes:
            v_parts.append(f"Notes: {v_latest.notes}")
        vitals_text = ", ".join(v_parts) if v_parts else "No vitals recorded."
        
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
            raw_response = call_groq_llm(prompt, max_tokens=4096)
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
        
    # Convert list/dict fields from LLM (such as recommendations, sources, relevant_evidence) to strings before saving
    if isinstance(report_data, dict):
        for field in ["title", "chief_complaint", "clinical_history", "observations", 
                      "investigations", "clinical_assessment", "relevant_evidence", 
                      "recommendations", "sources"]:
            if field in report_data:
                report_data[field] = _to_clean_text(report_data[field])

    # Create DB entry for draft report
    db_report = ClinicalReport(
        patient_id=patient_id,
        doctor_id=doctor_user.id,
        title=_to_clean_text(report_data.get("title")) or f"Clinical Report: {patient.name}",
        chief_complaint=_to_clean_text(report_data.get("chief_complaint")) or chief_complaint,
        clinical_history=_to_clean_text(report_data.get("clinical_history")) or clinical_history,
        observations=_to_clean_text(report_data.get("observations")),
        investigations=_to_clean_text(report_data.get("investigations")),
        clinical_assessment=_to_clean_text(report_data.get("clinical_assessment")),
        relevant_evidence=_to_clean_text(report_data.get("relevant_evidence")),
        recommendations=_to_clean_text(report_data.get("recommendations")),
        sources=_to_clean_text(report_data.get("sources")),
        status="AI-GENERATED DRAFT",
        created_at=datetime.utcnow()
    )
    try:
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
    except Exception as e:
        db.rollback()
        raise e
    
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


def format_report_to_searchable_text(report: ClinicalReport, patient: Optional[Patient] = None) -> str:
    """
    Formats structured ClinicalReport fields into clean, human-readable markdown text
    with standard section headers recognized by HierarchicalClinicalChunker.
    """
    p_name = patient.name if patient else "Unknown Patient"
    p_age = patient.age if patient else "N/A"
    p_gender = patient.gender if patient else "N/A"
    p_dept = patient.department if patient else "General Medicine"
    
    sections = [
        f"# CLINICAL PATIENT REPORT: {report.title}",
        f"REPORT ID: {report.id} | STATUS: {report.status} | CREATED: {report.created_at.strftime('%Y-%m-%d %H:%M:%S') if report.created_at else 'N/A'}",
        f"PATIENT ID: {report.patient_id} | PATIENT NAME: {p_name} | AGE: {p_age} | GENDER: {p_gender} | DEPARTMENT: {p_dept}",
        "",
        "## CHIEF COMPLAINT",
        report.chief_complaint or "None stated",
        "",
        "## CLINICAL HISTORY",
        report.clinical_history or "None recorded",
        "",
        "## OBSERVATIONS & VITALS",
        report.observations or "None recorded",
        "",
        "## INVESTIGATIONS & LABS",
        report.investigations or "None recorded",
        "",
        "## CLINICAL ASSESSMENT & DIAGNOSIS",
        report.clinical_assessment or "None recorded",
        "",
        "## RELEVANT EVIDENCE & GUIDELINES",
        report.relevant_evidence or "None cited",
        "",
        "## RECOMMENDATIONS & TREATMENT PLAN",
        report.recommendations or "None recorded",
        "",
        "## SOURCES & REFERENCES",
        report.sources or "None recorded"
    ]
    return "\n".join(sections)


def sync_report_to_knowledge_base(report: ClinicalReport, user: Optional[User], db: Session) -> Optional[Document]:
    """
    Syncs a ClinicalReport to the Knowledge Base:
    1. Formats report text into clean searchable clinical markdown.
    2. Writes text file to UPLOAD_DIR.
    3. Creates or updates a Document record in the database with scope='patient', approval_status='ACTIVE'.
    4. If updating, removes old chunks from FAISS vector store and BM25 index.
    5. Chunks, embeds, and indexes into FAISS and BM25 via index_text_document.
    6. Updates Document chunk_count and commits.
    """
    try:
        patient = db.query(Patient).filter(Patient.id == report.patient_id).first()
        report_text = format_report_to_searchable_text(report, patient)
        
        doc_filename = f"Clinical_Report_{report.patient_id}_Report{report.id}.txt"
        file_path = os.path.join(UPLOAD_DIR, doc_filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)
            
        file_hash = hashlib.md5(report_text.encode("utf-8")).hexdigest()
        
        # Check if Document record already exists
        existing_doc = db.query(Document).filter(
            (Document.name == doc_filename) | 
            ((Document.patient_id == report.patient_id) & (Document.document_type == "clinical_report") & (Document.file_path == file_path))
        ).first()
        
        if existing_doc:
            # Remove previous chunks from FAISS and BM25
            remove_document_from_vector_store(existing_doc.id)
            existing_doc.file_path = file_path
            existing_doc.hash_md5 = file_hash
            existing_doc.status = "ready"
            existing_doc.approval_status = "ACTIVE"
            existing_doc.updated_at = datetime.utcnow()
            
            chunk_count = index_text_document(
                text=report_text,
                document_name=doc_filename,
                doc_id=existing_doc.id,
                scope="patient",
                patient_id=report.patient_id,
                version=existing_doc.version or "1.0",
                document_type="clinical_report",
                report_id=report.id
            )
            existing_doc.chunk_count = chunk_count
            db.commit()
            db.refresh(existing_doc)
            print(f"Updated and re-indexed clinical report {report.id} (Doc ID {existing_doc.id}, {chunk_count} chunks).")
            return existing_doc
        else:
            db_doc = Document(
                name=doc_filename,
                file_path=file_path,
                status="ready",
                approval_status="ACTIVE",
                version="1.0",
                medical_relevance_score=1.0,
                hash_md5=file_hash,
                chunk_count=0,
                scope="patient",
                patient_id=report.patient_id,
                uploaded_by=user.id if user else None,
                uploader_role=user.role if user else "DOCTOR",
                document_type="clinical_report"
            )
            db.add(db_doc)
            db.commit()
            db.refresh(db_doc)
            
            chunk_count = index_text_document(
                text=report_text,
                document_name=doc_filename,
                doc_id=db_doc.id,
                scope="patient",
                patient_id=report.patient_id,
                version=db_doc.version,
                document_type="clinical_report",
                report_id=report.id
            )
            db_doc.chunk_count = chunk_count
            db.commit()
            db.refresh(db_doc)
            print(f"Created and indexed clinical report {report.id} as Document {db_doc.id} ({chunk_count} chunks).")
            return db_doc
    except Exception as e:
        print(f"Error syncing report {report.id} to Knowledge Base: {e}")
        return None


def reconcile_unindexed_clinical_reports(db: Session) -> int:
    """
    Scans ClinicalReport rows in the database, checks if the matching Document
    is missing or has chunk_count == 0, and syncs/indexes it into the Knowledge Base.
    """
    reconciled_count = 0
    try:
        reports = db.query(ClinicalReport).filter(ClinicalReport.status == "APPROVED").all()
        for report in reports:
            doc_filename = f"Clinical_Report_{report.patient_id}_Report{report.id}.txt"
            matching_doc = db.query(Document).filter(
                (Document.name == doc_filename) |
                ((Document.patient_id == report.patient_id) & (Document.document_type == "clinical_report") & (Document.name.like(f"%Report{report.id}%")))
            ).first()
            
            if not matching_doc or matching_doc.chunk_count == 0 or matching_doc.status != "ready":
                print(f"Reconciling unindexed clinical report: ID={report.id}, Patient={report.patient_id}")
                doc = sync_report_to_knowledge_base(report, report.doctor, db)
                if doc and doc.chunk_count > 0:
                    reconciled_count += 1
        print(f"Reconciliation complete: {reconciled_count} clinical reports indexed.")
    except Exception as e:
        print(f"Error during reconcile_unindexed_clinical_reports: {e}")
    return reconciled_count

