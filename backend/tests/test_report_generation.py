import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, ClinicalReport, Patient, User
from app.report_generator import _to_clean_text, generate_ai_patient_report

def test_to_clean_text_conversions():
    # None
    assert _to_clean_text(None) == ""
    
    # String
    assert _to_clean_text("  Normal string  ") == "Normal string"
    
    # List of strings (recommendations, sources, relevant_evidence)
    recs = [
        "1. Intravenous Ceftriaxone 1g-2g daily.",
        "2. Azithromycin 500mg daily.",
        "3. Monitor SpO2."
    ]
    formatted = _to_clean_text(recs)
    assert isinstance(formatted, str)
    assert "Ceftriaxone 1g-2g" in formatted
    assert "Azithromycin" in formatted
    assert "\n" in formatted
    
    # List of dicts
    list_dicts = [{"source": "Guideline A"}, {"source": "Guideline B"}]
    formatted_dicts = _to_clean_text(list_dicts)
    assert isinstance(formatted_dicts, str)
    assert "Guideline A" in formatted_dicts

    # Dict
    d = {"vitals": "BP 120/80", "pulse": 72}
    formatted_d = _to_clean_text(d)
    assert isinstance(formatted_d, str)
    assert "120/80" in formatted_d

def test_clinical_report_sqlite_insertion_with_lists():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(username="dr_sqlite_test", password_hash="hash", name="Dr. SQLite", role="DOCTOR")
    db.add(user)
    db.commit()

    patient = Patient(id="P888", name="SQLite Test Patient", age=50, gender="Female", department="Pulmonology")
    db.add(patient)
    db.commit()

    # Simulate LLM returning lists for recommendations, sources, relevant_evidence
    llm_report_data = {
        "title": ["Comprehensive Clinical Assessment"],
        "chief_complaint": "Acute shortness of breath",
        "clinical_history": "Asthma on inhalers",
        "observations": ["Wheezing bilateral", "SpO2 93% on room air"],
        "investigations": ["WBC 11,500 /uL", "Chest X-ray hyperinflation"],
        "clinical_assessment": ["Acute asthma exacerbation", "Rule out atypical pneumonia"],
        "relevant_evidence": [
            "Hospital Clinical Practice Guideline - Respiratory Care",
            "Emergency Triage Protocol"
        ],
        "recommendations": [
            "1. Nebulized Salbutamol 2.5mg Q4H.",
            "2. Oral Prednisolone 40mg daily for 5 days.",
            "3. Supplemental oxygen to maintain SpO2 >= 94%."
        ],
        "sources": [
            "Hospital Clinical Practice Guidelines: Respiratory Infections",
            "Patient Lab Examination Panel"
        ]
    }

    # Creating ClinicalReport with converted text
    db_report = ClinicalReport(
        patient_id=patient.id,
        doctor_id=user.id,
        title=_to_clean_text(llm_report_data.get("title")) or f"Clinical Report: {patient.name}",
        chief_complaint=_to_clean_text(llm_report_data.get("chief_complaint")) or "Complaint",
        clinical_history=_to_clean_text(llm_report_data.get("clinical_history")) or "History",
        observations=_to_clean_text(llm_report_data.get("observations")),
        investigations=_to_clean_text(llm_report_data.get("investigations")),
        clinical_assessment=_to_clean_text(llm_report_data.get("clinical_assessment")),
        relevant_evidence=_to_clean_text(llm_report_data.get("relevant_evidence")),
        recommendations=_to_clean_text(llm_report_data.get("recommendations")),
        sources=_to_clean_text(llm_report_data.get("sources")),
        status="AI-GENERATED DRAFT"
    )

    # This MUST NOT raise sqlite3.ProgrammingError: Error binding parameter 10 - type 'list' is not supported
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    assert db_report.id is not None
    assert isinstance(db_report.recommendations, str)
    assert isinstance(db_report.sources, str)
    assert isinstance(db_report.relevant_evidence, str)
    assert isinstance(db_report.observations, str)
    assert "Salbutamol" in db_report.recommendations
    assert "Respiratory Infections" in db_report.sources

def test_sources_list_parameter_11_binding():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(username="dr_cardio", password_hash="hash", name="Dr. Cardio", role="DOCTOR")
    db.add(user)
    db.commit()

    patient = Patient(id="P777", name="Cardio Patient", age=62, gender="Male", department="Cardiology")
    db.add(patient)
    db.commit()

    # Exact prompt example:
    sources_list = [
        "Hospital Cardiology Protocols (2024)",
        "Institutional Clinical Guidelines – Acute Unspecified Presentation (2023)"
    ]

    report_data = {
        "title": "Cardiology Evaluation",
        "chief_complaint": "Chest pain",
        "clinical_history": "HTN, Hyperlipidemia",
        "observations": "BP 145/90",
        "investigations": "Troponin I: Negative, ECG: Normal Sinus Rhythm",
        "clinical_assessment": "Atypical chest pain, low risk ACS",
        "relevant_evidence": "Cardiology protocol 2024",
        "recommendations": ["1. Aspirin 81mg daily", "2. Outpatient stress test in 72h"],
        "sources": sources_list
    }

    # Clean fields as in report_generator.py
    for field in ["title", "chief_complaint", "clinical_history", "observations", 
                  "investigations", "clinical_assessment", "relevant_evidence", 
                  "recommendations", "sources"]:
        if field in report_data:
            report_data[field] = _to_clean_text(report_data[field])

    db_report = ClinicalReport(
        patient_id=patient.id,
        doctor_id=user.id,
        title=report_data.get("title"),
        chief_complaint=report_data.get("chief_complaint"),
        clinical_history=report_data.get("clinical_history"),
        observations=report_data.get("observations"),
        investigations=report_data.get("investigations"),
        clinical_assessment=report_data.get("clinical_assessment"),
        relevant_evidence=report_data.get("relevant_evidence"),
        recommendations=report_data.get("recommendations"),
        sources=report_data.get("sources"),
        status="AI-GENERATED DRAFT"
    )

    # Must insert parameter 11 (sources) without ProgrammingError: Error binding parameter 11: type 'list' is not supported
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    assert db_report.id is not None
    assert isinstance(db_report.sources, str)
    assert "Hospital Cardiology Protocols (2024)" in db_report.sources
    assert "Institutional Clinical Guidelines" in db_report.sources

def test_db_rollback_before_audit_log():
    from app.auth import log_audit_event
    from sqlalchemy import text
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(username="dr_rollback", password_hash="hash", name="Dr. Rollback", role="DOCTOR")
    db.add(user)
    db.commit()

    # Simulate a failed DB operation causing pending rollback
    try:
        db.execute(text("SELECT * FROM non_existent_table"))
    except Exception:
        pass

    # Calling rollback resets the session
    db.rollback()

    # Now log_audit_event must succeed cleanly
    log_audit_event(db, user, "AI_REPORT_GEN_FAILED", "patient", "P777", "FAILURE", "Simulated error")
    
    from app.database import AuditLog
    log = db.query(AuditLog).filter(AuditLog.action == "AI_REPORT_GEN_FAILED").first()
    assert log is not None
    assert log.status == "FAILURE"

def test_format_report_to_searchable_text():
    from app.report_generator import format_report_to_searchable_text
    patient = Patient(id="PAT-999", name="Jane Doe", age=45, gender="Female", department="Internal Medicine")
    report = ClinicalReport(
        id=42,
        patient_id="PAT-999",
        doctor_id=1,
        title="Comprehensive Pulmonary Assessment",
        chief_complaint="Persistent productive cough and fever",
        clinical_history="Non-smoker, history of mild asthma",
        observations="BP: 125/82, Pulse: 88, SpO2: 95%",
        investigations="WBC: 12,400, CRP: 48 mg/L, CXR: Right middle lobe infiltrate",
        clinical_assessment="Community-acquired pneumonia with mild hypoxemia",
        relevant_evidence="Hospital Respiratory Guideline 2024 (Section 3.2)",
        recommendations="1. Amoxicillin-clavulanate 1g PO Q12H for 7 days.\n2. Inhaled bronchodilators PRN.",
        sources="Hospital Clinical Practice Guidelines: Respiratory Care",
        status="AI-GENERATED DRAFT"
    )
    formatted = format_report_to_searchable_text(report, patient)
    assert "# CLINICAL PATIENT REPORT: Comprehensive Pulmonary Assessment" in formatted
    assert "PATIENT ID: PAT-999" in formatted
    assert "## CHIEF COMPLAINT" in formatted
    assert "Persistent productive cough" in formatted
    assert "## INVESTIGATIONS & LABS" in formatted
    assert "Right middle lobe infiltrate" in formatted
    assert "## CLINICAL ASSESSMENT & DIAGNOSIS" in formatted
    assert "Community-acquired pneumonia" in formatted
    assert "## RECOMMENDATIONS & TREATMENT PLAN" in formatted
    assert "Amoxicillin-clavulanate" in formatted


from unittest.mock import patch


@patch("app.rag_pipeline.call_groq_llm")
@patch("app.rag_pipeline.call_gemini_fallback")
def test_sync_report_to_knowledge_base_and_rag_retrieval(mock_gemini, mock_groq):
    from app.database import SessionLocal, Document
    from app.report_generator import sync_report_to_knowledge_base
    from app.rag_pipeline import query_pipeline, remove_document_from_vector_store
    
    def mock_llm_call(prompt, **kwargs):
        if "TEST_UPDATED_MARKER_9952" in prompt:
            return "The revised clinical assessment confirms TEST_UPDATED_MARKER_9952 is fully resolved [1]."
        return "Patient exhibits TEST_UNIQUE_REPORT_FINDING_8841 in left lower lobe per CT scan [1]."

    mock_groq.side_effect = mock_llm_call
    mock_gemini.side_effect = mock_llm_call

    db = SessionLocal()
    try:
        # Create test doctor and patient
        doc_user = db.query(User).filter(User.username == "dr_report_test").first()
        if not doc_user:
            doc_user = User(
                username="dr_report_test",
                password_hash="hash",
                name="Dr. Report Tester",
                role="DOCTOR",
                status="ACTIVE"
            )
            db.add(doc_user)
            db.commit()
            db.refresh(doc_user)
            
        test_patient_id = "PAT-TEST-REPORT-8841"
        patient = db.query(Patient).filter(Patient.id == test_patient_id).first()
        if not patient:
            patient = Patient(
                id=test_patient_id,
                name="Alice Report Test",
                age=58,
                gender="Female",
                department="Pulmonology",
                status="ACTIVE"
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)
            
        # Create test report with unique marker
        unique_marker = "TEST_UNIQUE_REPORT_FINDING_8841"
        report = ClinicalReport(
            patient_id=test_patient_id,
            doctor_id=doc_user.id,
            title="Pulmonary Follow-up Assessment",
            chief_complaint=f"Patient exhibits {unique_marker} in left lower lobe",
            clinical_history="Chronic dyspnea on exertion",
            observations="SpO2 91% on room air, crackles in base",
            investigations=f"High-resolution CT confirms {unique_marker} with subpleural ground glass opacities",
            clinical_assessment=f"Primary diagnostic finding is {unique_marker} requiring targeted therapy",
            relevant_evidence="Hospital Interstitial Lung Disease Protocol",
            recommendations="1. High-dose corticosteroid taper.\n2. Repeat HRCT in 6 weeks.",
            sources="Hospital Pulmonology Clinical Practice Guideline",
            status="AI-GENERATED DRAFT"
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # Sync to Knowledge Base
        doc = sync_report_to_knowledge_base(report, doc_user, db)
        assert doc is not None
        assert doc.id is not None
        assert doc.scope == "patient"
        assert doc.patient_id == test_patient_id
        assert doc.document_type == "clinical_report"
        assert doc.approval_status == "ACTIVE"
        assert doc.chunk_count > 0
        
        # Test RAG retrieval with patient scope
        res_patient = query_pipeline(
            query=f"What was the primary diagnostic finding and HRCT result for {unique_marker}?",
            filters={"scope": "patient", "patient_id": test_patient_id},
            user_role="DOCTOR",
            active_doc_ids={doc.id}
        )
        assert res_patient["evidence"] is not None
        assert len(res_patient["evidence"]) > 0
        evidence_texts = " ".join([e.get("supporting_text") or e.get("text", "") for e in res_patient["evidence"]])
        assert unique_marker in evidence_texts
        
        # Test Patient Isolation: Query for a different patient must NOT retrieve this evidence
        res_other_patient = query_pipeline(
            query=f"What was the diagnostic finding for {unique_marker}?",
            filters={"scope": "patient", "patient_id": "PAT-DIFFERENT-9999"},
            user_role="DOCTOR",
            active_doc_ids={doc.id}
        )
        other_evidence_texts = " ".join([e.get("supporting_text") or e.get("text", "") for e in res_other_patient.get("evidence", [])])
        assert unique_marker not in other_evidence_texts
        
        # Test Knowledge Base Isolation: KB scope queries must NOT retrieve patient report
        res_kb = query_pipeline(
            query=f"What is the protocol for {unique_marker}?",
            filters={"scope": "knowledge_base"},
            user_role="DOCTOR",
            active_doc_ids={doc.id}
        )
        kb_evidence_texts = " ".join([e.get("supporting_text") or e.get("text", "") for e in res_kb.get("evidence", [])])
        assert unique_marker not in kb_evidence_texts
        
        # Test updating report and re-syncing
        updated_marker = "TEST_UPDATED_MARKER_9952"
        report.clinical_assessment = f"Revised assessment: {updated_marker} fully resolved"
        db.commit()
        db.refresh(report)
        
        updated_doc = sync_report_to_knowledge_base(report, doc_user, db)
        assert updated_doc is not None
        
        res_updated = query_pipeline(
            query=f"What is the revised assessment for {updated_marker}?",
            filters={"scope": "patient", "patient_id": test_patient_id},
            user_role="DOCTOR",
            active_doc_ids={updated_doc.id}
        )
        updated_evidence_texts = " ".join([e.get("supporting_text") or e.get("text", "") for e in res_updated.get("evidence", [])])
        assert updated_marker in updated_evidence_texts
        
        # Clean up test document from vector store
        remove_document_from_vector_store(doc.id)
        db.delete(report)
        db.delete(doc)
        db.delete(patient)
        db.commit()
    finally:
        db.close()

