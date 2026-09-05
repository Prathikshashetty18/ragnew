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
