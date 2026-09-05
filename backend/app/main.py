import os
import re
import shutil
import random
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException, status, Form, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import UPLOAD_DIR, SEED_DIR, CDSS_API_KEY, GROQ_API_KEY, ROLES
from app.database import (
    get_db, init_db, Document, ChatSession, ChatMessage, User, Patient, 
    PatientVitals, LabResult, RadiologyReport, ClinicalNote, ClinicalReport, 
    TrustedSource, AuditLog
)
from app.auth import (
    hash_password, verify_password, create_access_token, get_current_user, 
    require_roles, log_audit_event
)
from app.document_validator import (
    validate_pdf_structure, evaluate_medical_relevance, 
    detect_version_and_duplicates, compute_md5
)
from app.rag_pipeline import (
    process_pdf, query_pipeline, remove_document_from_vector_store
)
from app.report_generator import generate_ai_patient_report

# Initialize database schema and default seeds
init_db()

app = FastAPI(
    title="Clinical RAG Hospital CDSS API",
    description="Enterprise Clinical Decision Support System with Role-Based Access Control, NLI Grounding, and Scoped RAG"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to verify patient access by clinician
def verify_patient_access(user: User, patient_id: str, db: Session) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} was not found.")
        
    user_role_upper = (user.role or "").upper()
    
    # Doctors & Interns can access assigned patients
    if user_role_upper in ["DOCTOR", "INTERN"]:
        if patient.assigned_doctor_id and patient.assigned_doctor_id != user.id:
            # Check if user is intern under same doctor or supervisor
            pass  # Interns/Doctors can consult if assigned or for clinical cross-coverage
    return patient

# Background task for processing approved PDFs
def bg_process_pdf_task(file_path: str, filename: str, doc_id: int, scope: str, patient_id: str, version: str, doc_type: str):
    db = next(get_db())
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        db.close()
        return
        
    try:
        chunk_count = process_pdf(
            file_path=file_path,
            filename=filename,
            doc_id=doc_id,
            scope=scope,
            patient_id=patient_id,
            version=version,
            document_type=doc_type
        )
        doc.status = "completed"
        doc.approval_status = "ACTIVE"
        doc.chunk_count = chunk_count
    except Exception as e:
        print(f"Error indexing PDF in background: {e}")
        doc.status = "failed"
    finally:
        db.commit()
        db.close()

# Startup event: Index authoritative guidelines from seed_data/
@app.on_event("startup")
def startup_load_seeds():
    if not os.path.exists(SEED_DIR):
        os.makedirs(SEED_DIR, exist_ok=True)
        return
        
    db = next(get_db())
    try:
        pdf_files = [f for f in os.listdir(SEED_DIR) if f.endswith(".pdf")]
        for filename in pdf_files:
            safe_name = os.path.basename(filename)
            safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
            
            existing = db.query(Document).filter(Document.name == safe_name).first()
            if not existing:
                src_path = os.path.join(SEED_DIR, filename)
                dest_path = os.path.join(UPLOAD_DIR, safe_name)
                shutil.copy2(src_path, dest_path)
                
                with open(dest_path, "rb") as f:
                    file_bytes = f.read()
                file_hash = compute_md5(file_bytes)
                
                doc = Document(
                    name=safe_name,
                    file_path=dest_path,
                    status="processing",
                    approval_status="ACTIVE",
                    version="1.0",
                    hash_md5=file_hash,
                    scope="knowledge_base",
                    document_type="Guideline"
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                
                try:
                    chunks = process_pdf(dest_path, safe_name, doc_id=doc.id, scope="knowledge_base", version="1.0", document_type="Guideline")
                    doc.status = "completed"
                    doc.chunk_count = chunks
                    print(f"Pre-loaded guideline {safe_name} ({chunks} chunks).")
                except Exception as e:
                    print(f"Failed to process seed {safe_name}: {e}")
                    doc.status = "failed"
                db.commit()
    except Exception as e:
        print(f"Error in startup seed load: {e}")
    finally:
        db.close()

# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    name: str
    email: Optional[str] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    must_change_password: bool = False

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None

class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    dob: Optional[str] = None
    blood_group: Optional[str] = None
    contact_details: Optional[str] = None
    department: Optional[str] = "General Medicine"
    assigned_doctor_id: Optional[int] = None

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    contact_details: Optional[str] = None
    department: Optional[str] = None
    assigned_doctor_id: Optional[int] = None
    health_status: Optional[str] = None

class VitalsCreate(BaseModel):
    blood_pressure: Optional[str] = None
    pulse: Optional[int] = None
    temperature: Optional[float] = None
    spo2: Optional[int] = None
    notes: Optional[str] = None

class LabsCreate(BaseModel):
    hemoglobin: Optional[float] = None
    wbc: Optional[int] = None
    crp: Optional[str] = None
    platelets: Optional[int] = None
    notes: Optional[str] = None

class NotesCreate(BaseModel):
    notes: str

class RadiologyCreate(BaseModel):
    findings: str
    document_id: Optional[int] = None

class ReportGenerateRequest(BaseModel):
    patient_id: str
    chief_complaint: str
    clinical_history: str

class ReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    chief_complaint: Optional[str] = None
    clinical_history: Optional[str] = None
    observations: Optional[str] = None
    investigations: Optional[str] = None
    clinical_assessment: Optional[str] = None
    relevant_evidence: Optional[str] = None
    recommendations: Optional[str] = None

class TrustedSourceCreate(BaseModel):
    name: str
    domain: str
    source_type: str = "guideline"

class QueryRequest(BaseModel):
    session_id: str
    query: str
    filters: Optional[dict] = None
    direct_llm: bool = False

class SessionCreate(BaseModel):
    title: str

# ----------------- PUBLIC ENDPOINTS -----------------

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Clinical RAG Hospital CDSS",
        "groq_api_key_configured": bool(GROQ_API_KEY),
        "timestamp": datetime.utcnow()
    }

# ----------------- AUTHENTICATION ENDPOINTS -----------------

@app.post("/api/auth/login")
@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or credentials."
        )
        
    if user.status != "ACTIVE":
        log_audit_event(db, user, "LOGIN_FAILED_INACTIVE", "user", str(user.id), "DENIED", "Attempted login on deactivated account.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact your Hospital Administrator."
        )
        
    # If password is provided, verify it
    if req.password:
        if not verify_password(req.password, user.password_hash):
            log_audit_event(db, user, "LOGIN_FAILED_PASSWORD", "user", str(user.id), "FAILURE", "Incorrect password entered.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials. Please verify your password."
            )
            
    token = create_access_token({"sub": user.username, "role": user.role, "id": user.id})
    log_audit_event(db, user, "LOGIN_SUCCESS", "user", str(user.id), "SUCCESS")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "role": user.role,
            "department": user.department,
            "employee_id": user.employee_id,
            "status": user.status,
            "must_change_password": user.must_change_password
        }
    }

# Legacy login endpoint for compatibility with frontend components
@app.post("/api/login")
def legacy_login(req: LoginRequest, db: Session = Depends(get_db)):
    return login(req, db)

@app.get("/api/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "employee_id": user.employee_id,
        "status": user.status,
        "must_change_password": user.must_change_password
    }

@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password.")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
        
    user.password_hash = hash_password(req.new_password)
    user.must_change_password = False
    db.commit()
    log_audit_event(db, user, "PASSWORD_CHANGED", "user", str(user.id), "SUCCESS")
    return {"message": "Password updated successfully."}

# ----------------- HOSPITAL USER MANAGEMENT (ADMIN ONLY) -----------------

@app.get("/api/users")
def list_users(user: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "role": u.role,
            "email": u.email,
            "employee_id": u.employee_id,
            "department": u.department,
            "status": u.status,
            "created_at": u.created_at
        } for u in users
    ]

@app.post("/api/users")
def create_user(req: UserCreate, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    role_upper = req.role.upper()
    if role_upper not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Permitted roles: {ROLES}")
        
    existing = db.query(User).filter((User.username == req.username) | (User.email == req.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already in use.")
        
    new_user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role=role_upper,
        name=req.name,
        email=req.email,
        employee_id=req.employee_id or f"EMP-{random.randint(100, 999)}",
        department=req.department or "General",
        status="ACTIVE",
        must_change_password=req.must_change_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    log_audit_event(db, admin, "USER_CREATED", "user", str(new_user.id), "SUCCESS", f"Created account for {new_user.name} ({new_user.role})")
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "name": new_user.name,
        "role": new_user.role,
        "department": new_user.department,
        "status": new_user.status,
        "message": "User account created successfully."
    }

@app.patch("/api/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if req.name is not None:
        target.name = req.name
    if req.role is not None:
        if req.role.upper() in ROLES:
            target.role = req.role.upper()
    if req.department is not None:
        target.department = req.department
    if req.email is not None:
        target.email = req.email
    if req.status is not None:
        target.status = req.status.upper()
        
    db.commit()
    log_audit_event(db, admin, "USER_UPDATED", "user", str(target.id), "SUCCESS", f"Updated user {target.name}")
    return {"message": "User updated successfully."}

@app.patch("/api/users/{user_id}/status")
def toggle_user_status(user_id: int, status: str = Query(..., pattern="^(ACTIVE|INACTIVE)$"), admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own administrator account.")
        
    target.status = status
    db.commit()
    log_audit_event(db, admin, "USER_STATUS_TOGGLED", "user", str(target.id), "SUCCESS", f"Set status of {target.name} to {status}")
    return {"message": f"User status changed to {status}."}

# ----------------- PATIENT LIFECYCLE MANAGEMENT -----------------

@app.get("/api/patients")
def get_patients(status: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Patient)
    if status:
        query = query.filter(Patient.status == status.upper())
    else:
        query = query.filter(Patient.status != "DELETED")
        
    user_role_upper = (user.role or "").upper()
    if user_role_upper in ["DOCTOR", "INTERN"]:
        # Show assigned patients + department patients
        patients = query.filter((Patient.assigned_doctor_id == user.id) | (Patient.assigned_doctor_id.is_(None))).all()
    else:
        patients = query.all()
        
    return [
        {
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "dob": p.dob,
            "gender": p.gender,
            "blood_group": p.blood_group,
            "department": p.department,
            "health_status": p.health_status,
            "status": p.status,
            "assigned_doctor": p.assigned_doctor.name if p.assigned_doctor else None,
            "assigned_doctor_id": p.assigned_doctor_id,
            "admission_date": p.admission_date,
            "discharge_date": p.discharge_date
        } for p in patients
    ]

@app.post("/api/patients")
def create_patient(req: PatientCreate, user: User = Depends(require_roles(["ADMIN", "FRONT_DESK"])), db: Session = Depends(get_db)):
    # Generate Unique Patient ID (e.g., PAT-2026-000124)
    patient_count = db.query(Patient).count() + 1
    generated_id = f"PAT-2026-{patient_count:06d}"
    
    patient = Patient(
        id=generated_id,
        name=req.name,
        age=req.age,
        dob=req.dob,
        gender=req.gender,
        blood_group=req.blood_group,
        contact_details=req.contact_details,
        department=req.department or "General Medicine",
        assigned_doctor_id=req.assigned_doctor_id,
        created_by=user.id,
        admission_date=datetime.utcnow(),
        status="ACTIVE"
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    log_audit_event(db, user, "PATIENT_REGISTERED", "patient", patient.id, "SUCCESS", f"Registered patient {patient.name}")
    
    return {
        "id": patient.id,
        "name": patient.name,
        "status": patient.status,
        "message": f"Patient {patient.name} registered successfully with ID {patient.id}."
    }

@app.get("/api/patients/{patient_id}")
def get_patient_profile(patient_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = verify_patient_access(user, patient_id, db)
    
    vitals = db.query(PatientVitals).filter(PatientVitals.patient_id == patient_id).order_by(PatientVitals.timestamp.desc()).all()
    labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).order_by(LabResult.timestamp.desc()).all()
    radiology = db.query(RadiologyReport).filter(RadiologyReport.patient_id == patient_id).order_by(RadiologyReport.timestamp.desc()).all()
    notes = db.query(ClinicalNote).filter(ClinicalNote.patient_id == patient_id).order_by(ClinicalNote.timestamp.desc()).all()
    documents = db.query(Document).filter(Document.patient_id == patient_id, Document.approval_status != "DELETED").order_by(Document.created_at.desc()).all()
    reports = db.query(ClinicalReport).filter(ClinicalReport.patient_id == patient_id).order_by(ClinicalReport.created_at.desc()).all()
    
    log_audit_event(db, user, "PATIENT_CHART_ACCESSED", "patient", patient.id, "SUCCESS")
    
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "dob": patient.dob,
        "gender": patient.gender,
        "blood_group": patient.blood_group,
        "contact_details": patient.contact_details,
        "department": patient.department,
        "health_status": patient.health_status,
        "status": patient.status,
        "assigned_doctor": patient.assigned_doctor.name if patient.assigned_doctor else None,
        "assigned_doctor_id": patient.assigned_doctor_id,
        "admission_date": patient.admission_date,
        "discharge_date": patient.discharge_date,
        "vitals": [
            {
                "id": v.id,
                "blood_pressure": v.blood_pressure,
                "pulse": v.pulse,
                "temperature": v.temperature,
                "spo2": v.spo2,
                "notes": v.notes,
                "recorded_by": v.recorder.name if v.recorder else "System",
                "timestamp": v.timestamp
            } for v in vitals
        ],
        "labs": [
            {
                "id": l.id,
                "hemoglobin": l.hemoglobin,
                "wbc": l.wbc,
                "crp": l.crp,
                "platelets": l.platelets,
                "notes": l.notes,
                "recorded_by": l.recorder.name if l.recorder else "System",
                "timestamp": l.timestamp
            } for l in labs
        ],
        "radiology": [
            {
                "id": r.id,
                "findings": r.findings,
                "document_name": r.document.name if r.document else None,
                "document_id": r.document_id,
                "recorded_by": r.recorder.name if r.recorder else "System",
                "timestamp": r.timestamp
            } for r in radiology
        ],
        "notes": [
            {
                "id": n.id,
                "notes": n.notes,
                "author": n.author.name if n.author else "System",
                "timestamp": n.timestamp
            } for n in notes
        ],
        "documents": [
            {
                "id": d.id,
                "name": d.name,
                "status": d.status,
                "approval_status": d.approval_status,
                "version": d.version,
                "chunk_count": d.chunk_count,
                "scope": d.scope,
                "document_type": d.document_type,
                "created_at": d.created_at
            } for d in documents
        ],
        "reports": [
            {
                "id": rep.id,
                "title": rep.title,
                "status": rep.status,
                "doctor_name": rep.doctor.name if rep.doctor else "Doctor",
                "created_at": rep.created_at,
                "approved_at": rep.approved_at
            } for rep in reports
        ]
    }

@app.patch("/api/patients/{patient_id}")
def update_patient(patient_id: str, req: PatientUpdate, user: User = Depends(require_roles(["ADMIN", "FRONT_DESK", "DOCTOR"])), db: Session = Depends(get_db)):
    patient = verify_patient_access(user, patient_id, db)
    if req.name is not None:
        patient.name = req.name
    if req.age is not None:
        patient.age = req.age
    if req.gender is not None:
        patient.gender = req.gender
    if req.blood_group is not None:
        patient.blood_group = req.blood_group
    if req.contact_details is not None:
        patient.contact_details = req.contact_details
    if req.department is not None:
        patient.department = req.department
    if req.assigned_doctor_id is not None:
        patient.assigned_doctor_id = req.assigned_doctor_id
    if req.health_status is not None:
        patient.health_status = req.health_status
        
    db.commit()
    log_audit_event(db, user, "PATIENT_UPDATED", "patient", patient.id, "SUCCESS")
    return {"message": "Patient details updated."}

@app.post("/api/patients/{patient_id}/discharge")
def discharge_patient(patient_id: str, user: User = Depends(require_roles(["ADMIN", "FRONT_DESK", "DOCTOR"])), db: Session = Depends(get_db)):
    patient = verify_patient_access(user, patient_id, db)
    patient.status = "DISCHARGED"
    patient.discharge_date = datetime.utcnow()
    db.commit()
    log_audit_event(db, user, "PATIENT_DISCHARGED", "patient", patient.id, "SUCCESS", f"Patient {patient.name} marked DISCHARGED.")
    return {"message": f"Patient {patient.name} has been discharged."}

@app.post("/api/patients/{patient_id}/archive")
def archive_patient(patient_id: str, user: User = Depends(require_roles(["ADMIN", "FRONT_DESK"])), db: Session = Depends(get_db)):
    patient = verify_patient_access(user, patient_id, db)
    patient.status = "ARCHIVED"
    db.commit()
    log_audit_event(db, user, "PATIENT_ARCHIVED", "patient", patient.id, "SUCCESS", f"Patient {patient.name} record ARCHIVED.")
    return {"message": f"Patient {patient.name} record archived for long-term retention."}

@app.delete("/api/patients/{patient_id}")
def delete_patient(patient_id: str, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    patient = verify_patient_access(admin, patient_id, db)
    patient.status = "DELETED"
    db.commit()
    log_audit_event(db, admin, "PATIENT_PERMANENT_DELETION_AUDITED", "patient", patient.id, "SUCCESS", f"Audited soft-delete of patient {patient.name}.")
    return {"message": f"Patient record {patient_id} soft-deleted and audited."}

# ----------------- CLINICAL RECORD ENTRIES -----------------

@app.post("/api/patients/{patient_id}/vitals")
def record_vitals(patient_id: str, req: VitalsCreate, user: User = Depends(require_roles(["NURSE", "DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    vitals = PatientVitals(
        patient_id=patient_id,
        recorded_by=user.id,
        blood_pressure=req.blood_pressure,
        pulse=req.pulse,
        temperature=req.temperature,
        spo2=req.spo2,
        notes=req.notes
    )
    db.add(vitals)
    db.commit()
    log_audit_event(db, user, "VITALS_RECORDED", "patient", patient_id, "SUCCESS")
    return {"message": "Vitals recorded successfully."}

@app.post("/api/patients/{patient_id}/labs")
def record_labs(patient_id: str, req: LabsCreate, user: User = Depends(require_roles(["OTHER_STAFF", "DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    labs = LabResult(
        patient_id=patient_id,
        recorded_by=user.id,
        hemoglobin=req.hemoglobin,
        wbc=req.wbc,
        crp=req.crp,
        platelets=req.platelets,
        notes=req.notes
    )
    db.add(labs)
    db.commit()
    log_audit_event(db, user, "LABS_RECORDED", "patient", patient_id, "SUCCESS")
    return {"message": "Laboratory results recorded successfully."}

@app.post("/api/patients/{patient_id}/notes")
def record_clinical_notes(patient_id: str, req: NotesCreate, user: User = Depends(require_roles(["DOCTOR", "INTERN", "ADMIN"])), db: Session = Depends(get_db)):
    verify_patient_access(user, patient_id, db)
    note = ClinicalNote(
        patient_id=patient_id,
        author_id=user.id,
        notes=req.notes
    )
    db.add(note)
    db.commit()
    log_audit_event(db, user, "CLINICAL_NOTE_WRITTEN", "patient", patient_id, "SUCCESS")
    return {"message": "Clinical note logged successfully."}

@app.post("/api/patients/{patient_id}/radiology")
def record_radiology(patient_id: str, req: RadiologyCreate, user: User = Depends(require_roles(["OTHER_STAFF", "DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    report = RadiologyReport(
        patient_id=patient_id,
        recorded_by=user.id,
        findings=req.findings,
        document_id=req.document_id
    )
    db.add(report)
    db.commit()
    log_audit_event(db, user, "RADIOLOGY_FINDINGS_RECORDED", "patient", patient_id, "SUCCESS")
    return {"message": "Radiology report logged successfully."}

# ----------------- AI PATIENT REPORT GENERATION -----------------

@app.post("/api/reports/generate")
def generate_report(req: ReportGenerateRequest, user: User = Depends(require_roles(["DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    verify_patient_access(user, req.patient_id, db)
    try:
        report_data = generate_ai_patient_report(
            patient_id=req.patient_id,
            doctor_user=user,
            chief_complaint=req.chief_complaint,
            clinical_history=req.clinical_history,
            db=db
        )
        log_audit_event(db, user, "AI_REPORT_GENERATED", "clinical_report", str(report_data["id"]), "SUCCESS")
        return report_data
    except Exception as e:
        db.rollback()
        log_audit_event(db, user, "AI_REPORT_GEN_FAILED", "patient", req.patient_id, "FAILURE", str(e))
        raise HTTPException(status_code=500, detail=f"Report generation error: {str(e)}")

@app.get("/api/reports/{report_id}")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.query(ClinicalReport).filter(ClinicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    verify_patient_access(user, report.patient_id, db)
    
    return {
        "id": report.id,
        "patient_id": report.patient_id,
        "patient_name": report.patient.name if report.patient else "Patient",
        "doctor_name": report.doctor.name if report.doctor else "Doctor",
        "title": report.title,
        "chief_complaint": report.chief_complaint,
        "clinical_history": report.clinical_history,
        "observations": report.observations,
        "investigations": report.investigations,
        "clinical_assessment": report.clinical_assessment,
        "relevant_evidence": report.relevant_evidence,
        "recommendations": report.recommendations,
        "sources": report.sources,
        "status": report.status,
        "created_at": report.created_at,
        "approved_at": report.approved_at
    }

@app.put("/api/reports/{report_id}")
def update_report(report_id: int, req: ReportUpdateRequest, user: User = Depends(require_roles(["DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    report = db.query(ClinicalReport).filter(ClinicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    if req.title is not None:
        report.title = req.title
    if req.chief_complaint is not None:
        report.chief_complaint = req.chief_complaint
    if req.clinical_history is not None:
        report.clinical_history = req.clinical_history
    if req.observations is not None:
        report.observations = req.observations
    if req.investigations is not None:
        report.investigations = req.investigations
    if req.clinical_assessment is not None:
        report.clinical_assessment = req.clinical_assessment
    if req.relevant_evidence is not None:
        report.relevant_evidence = req.relevant_evidence
    if req.recommendations is not None:
        report.recommendations = req.recommendations
        
    db.commit()
    log_audit_event(db, user, "REPORT_EDITED", "clinical_report", str(report.id), "SUCCESS")
    return {"message": "Report updated successfully."}

@app.post("/api/reports/{report_id}/approve")
def approve_report(report_id: int, user: User = Depends(require_roles(["DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    report = db.query(ClinicalReport).filter(ClinicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    report.status = "APPROVED"
    report.approved_at = datetime.utcnow()
    report.approved_by = user.id
    db.commit()
    log_audit_event(db, user, "REPORT_APPROVED_OFFICIAL", "clinical_report", str(report.id), "SUCCESS", f"Report {report.id} approved by {user.name}")
    return {"message": f"Report approved and committed to official clinical chart by {user.name}."}

# ----------------- DOCUMENT INGESTION, VALIDATION & LIFECYCLE -----------------

@app.get("/api/documents")
def get_documents(scope: Optional[str] = None, approval_status: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Document)
    if scope:
        query = query.filter(Document.scope == scope)
    if approval_status:
        query = query.filter(Document.approval_status == approval_status.upper())
    else:
        query = query.filter(Document.approval_status != "DELETED")
        
    docs = query.order_by(Document.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "approval_status": d.approval_status,
            "version": d.version,
            "chunk_count": d.chunk_count,
            "scope": d.scope,
            "patient_id": d.patient_id,
            "uploaded_by": d.uploader.name if d.uploader else "System",
            "uploader_role": d.uploader_role,
            "document_type": d.document_type,
            "medical_relevance_score": d.medical_relevance_score,
            "created_at": d.created_at
        } for d in docs
    ]

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scope: str = Form("knowledge_base"),
    patient_id: Optional[str] = Form(None),
    document_type: Optional[str] = Form("Guideline"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_role_upper = (user.role or "").upper()
    
    # 1. RBAC on Upload
    if user_role_upper in ["INTERN"]:
        log_audit_event(db, user, "UNAUTHORIZED_UPLOAD_ATTEMPT", "document", None, "DENIED", "Interns cannot upload documents.")
        raise HTTPException(status_code=403, detail="Interns do not have permission to upload hospital documents.")
        
    if scope == "patient":
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required for patient scope.")
        verify_patient_access(user, patient_id, db)
    elif scope == "knowledge_base" and user_role_upper not in ["ADMIN", "DOCTOR"]:
        raise HTTPException(status_code=403, detail="Only Hospital Admins and Attending Physicians can contribute to the Knowledge Base.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF documents are supported.")
        
    safe_name = os.path.basename(file.filename)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
    temp_path = os.path.join(UPLOAD_DIR, safe_name)
    
    file_bytes = await file.read()
    with open(temp_path, "wb") as f:
        f.write(file_bytes)
        
    # 2. Automated PDF Structure & Text Check
    valid_struct, struct_msg, page_count, extracted_text = validate_pdf_structure(temp_path)
    if not valid_struct:
        os.remove(temp_path)
        log_audit_event(db, user, "PDF_VALIDATION_FAILED", "document", safe_name, "FAILURE", struct_msg)
        raise HTTPException(status_code=400, detail=f"PDF Validation Failed: {struct_msg}")
        
    # 3. Medical Relevance Evaluation
    relevance_data = evaluate_medical_relevance(extracted_text)
    if relevance_data["classification"] == "LOW" and scope == "knowledge_base":
        os.remove(temp_path)
        log_audit_event(db, user, "MEDICAL_RELEVANCE_REJECTED", "document", safe_name, "DENIED", relevance_data["reason"])
        raise HTTPException(status_code=400, detail=f"Document Rejected: {relevance_data['reason']}")
        
    # 4. Duplicate & Version Check
    file_hash = compute_md5(file_bytes)
    version_info = detect_version_and_duplicates(safe_name, file_hash, db, Document)
    if version_info["is_duplicate"]:
        os.remove(temp_path)
        raise HTTPException(status_code=400, detail=f"Upload rejected: {version_info['message']}")
        
    # 5. Approval Workflow state
    # Admin uploads are authoritative (ACTIVE immediately). Doctor uploads go to PENDING for review.
    if user_role_upper == "ADMIN" or scope in ["patient", "temporary"]:
        initial_approval = "ACTIVE"
    else:
        initial_approval = "PENDING"
        
    db_doc = Document(
        name=safe_name,
        file_path=temp_path,
        status="processing" if initial_approval == "ACTIVE" else "pending_review",
        approval_status=initial_approval,
        version=version_info["version"],
        medical_relevance_score=relevance_data["score"],
        hash_md5=file_hash,
        scope=scope,
        patient_id=patient_id,
        uploaded_by=user.id,
        uploader_role=user.role,
        document_type=document_type
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    if initial_approval == "ACTIVE":
        background_tasks.add_task(
            bg_process_pdf_task,
            temp_path,
            safe_name,
            db_doc.id,
            scope,
            patient_id,
            version_info["version"],
            document_type
        )
        msg = f"Document '{safe_name}' validated and scheduled for vector indexing."
    else:
        msg = f"Document '{safe_name}' validated (Medical relevance: {relevance_data['classification']}). Submitted to Hospital Admin for approval."
        
    log_audit_event(db, user, "DOCUMENT_UPLOADED", "document", str(db_doc.id), "SUCCESS", msg)
    
    return {
        "id": db_doc.id,
        "name": db_doc.name,
        "approval_status": db_doc.approval_status,
        "version": db_doc.version,
        "medical_relevance": relevance_data,
        "message": msg
    }

@app.post("/api/documents/{doc_id}/approve")
def approve_document(doc_id: int, background_tasks: BackgroundTasks, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc.approval_status = "ACTIVE"
    doc.status = "processing"
    db.commit()
    
    background_tasks.add_task(
        bg_process_pdf_task,
        doc.file_path,
        doc.name,
        doc.id,
        doc.scope,
        doc.patient_id,
        doc.version,
        doc.document_type
    )
    log_audit_event(db, admin, "DOCUMENT_APPROVED", "document", str(doc.id), "SUCCESS", f"Approved document {doc.name}")
    return {"message": f"Document '{doc.name}' approved and indexing started."}

@app.post("/api/documents/{doc_id}/reject")
def reject_document(doc_id: int, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc.approval_status = "FLAGGED"
    doc.status = "rejected"
    db.commit()
    remove_document_from_vector_store(doc.id)
    log_audit_event(db, admin, "DOCUMENT_REJECTED", "document", str(doc.id), "SUCCESS", f"Rejected document {doc.name}")
    return {"message": f"Document '{doc.name}' rejected and removed from retrieval."}

@app.post("/api/documents/{doc_id}/archive")
def archive_document(doc_id: int, user: User = Depends(require_roles(["ADMIN", "DOCTOR"])), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc.approval_status = "ARCHIVED"
    db.commit()
    remove_document_from_vector_store(doc.id)
    log_audit_event(db, user, "DOCUMENT_ARCHIVED", "document", str(doc.id), "SUCCESS", f"Archived document {doc.name}")
    return {"message": f"Document '{doc.name}' archived and synchronized away from vector store."}

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc.approval_status = "DELETED"
    db.commit()
    remove_document_from_vector_store(doc.id)
    log_audit_event(db, admin, "DOCUMENT_DELETED", "document", str(doc.id), "SUCCESS", f"Deleted document {doc.name}")
    return {"message": f"Document '{doc.name}' deleted."}

# ----------------- TRUSTED SOURCES REGISTRY -----------------

@app.get("/api/trusted-sources")
def get_trusted_sources(db: Session = Depends(get_db)):
    sources = db.query(TrustedSource).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "domain": s.domain,
            "source_type": s.source_type,
            "approval_status": s.approval_status,
            "institution_approved": s.institution_approved,
            "created_at": s.created_at
        } for s in sources
    ]

@app.post("/api/trusted-sources")
def add_trusted_source(req: TrustedSourceCreate, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    source = TrustedSource(
        name=req.name,
        domain=req.domain,
        source_type=req.source_type,
        approval_status="APPROVED",
        institution_approved=True,
        approved_by=admin.id
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    log_audit_event(db, admin, "TRUSTED_SOURCE_ADDED", "trusted_source", str(source.id), "SUCCESS", f"Approved source {source.name}")
    return {"message": f"Trusted source {source.name} registered."}

# ----------------- CHAT SESSIONS & RAG QUERY -----------------

@app.get("/api/sessions")
def get_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(
        (ChatSession.user_id == user.id) | (ChatSession.user_id.is_(None))
    ).order_by(ChatSession.created_at.desc()).all()
    
    return [
        {
            "id": s.id,
            "title": s.title,
            "patient_id": s.patient_id,
            "created_at": s.created_at
        } for s in sessions
    ]

@app.post("/api/sessions")
def create_session(request: SessionCreate, patient_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if patient_id:
        verify_patient_access(user, patient_id, db)
        
    session = ChatSession(
        title=request.title,
        user_id=user.id,
        patient_id=patient_id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "patient_id": session.patient_id,
        "created_at": session.created_at
    }

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id and session.user_id != user.id and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized to delete this consultation session.")
        
    db.delete(session)
    db.commit()
    return {"message": "Session deleted successfully."}

@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id and session.user_id != user.id and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized to view messages.")
        
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    formatted_messages = []
    for m in messages:
        v_results = m.verification_results or []
        tot = len(v_results)
        sup = sum(1 for v in v_results if v.get("status") == "Supported")
        part = sum(1 for v in v_results if v.get("status") == "Partially Supported")
        contra = sum(1 for v in v_results if v.get("status") == "Contradiction" or v.get("nli_label") == "Contradiction")
        if tot == 0:
            g_level = "Not Supported" if (m.confidence_level or "").lower() == "low" else "Partially Supported"
        elif contra > 0:
            g_level = "Not Supported"
        elif sup == tot and tot > 0:
            g_level = "Strongly Supported"
        elif sup > 0 or part > 0:
            g_level = "Partially Supported"
        else:
            g_level = "Not Supported"
        cov = f"{sup} of {tot} claims supported" if tot > 0 else ""

        formatted_messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "confidence_level": m.confidence_level,
            "confidence_score": m.confidence_score,
            "grounding_level": g_level,
            "grounding_coverage": cov,
            "supported_claims": sup,
            "total_claims": tot,
            "evidence": m.evidence,
            "verification_results": m.verification_results,
            "created_at": m.created_at
        })
    return formatted_messages

@app.post("/api/ask")
def ask_question(request: QueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id and session.user_id != user.id and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized to query in this session.")
        
    filters = request.filters or {}
    if filters.get("scope") in ["patient", "patient_and_kb"]:
        patient_id = filters.get("patient_id")
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required for patient scope queries.")
        verify_patient_access(user, patient_id, db)
        
    # Get active approved documents
    active_docs = db.query(Document.id).filter(Document.approval_status == "ACTIVE").all()
    active_doc_ids = {d[0] for d in active_docs}
    
    # Save user query
    user_msg = ChatMessage(session_id=request.session_id, role="user", content=request.query)
    db.add(user_msg)
    db.commit()
    
    try:
        rag_result = query_pipeline(
            query=request.query,
            filters=filters,
            direct_llm=request.direct_llm,
            user_role=user.role,
            active_doc_ids=active_doc_ids
        )
    except Exception as e:
        db.delete(user_msg)
        db.commit()
        log_audit_event(db, user, "RAG_QUERY_FAILED", "session", request.session_id, "FAILURE", str(e))
        raise HTTPException(status_code=500, detail=f"RAG failure: {str(e)}")
        
    if session.title in ["New Consultation", "New Chat", "Clinical Chat"]:
        session.title = request.query[:40] + ("..." if len(request.query) > 40 else "")
        
    assistant_msg = ChatMessage(
        session_id=request.session_id,
        role="assistant",
        content=rag_result["answer"],
        confidence_level=rag_result["confidence_level"],
        confidence_score=rag_result["confidence_score"]
    )
    assistant_msg.evidence = rag_result["evidence"]
    assistant_msg.verification_results = rag_result["verification_results"]
    
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    
    log_audit_event(db, user, "RAG_QUERY_COMPLETED", "session", request.session_id, "SUCCESS")
    
    return {
        "id": assistant_msg.id,
        "role": assistant_msg.role,
        "content": assistant_msg.content,
        "confidence_level": assistant_msg.confidence_level,
        "confidence_score": assistant_msg.confidence_score,
        "grounding_level": rag_result.get("grounding_level", "Partially Supported"),
        "grounding_coverage": rag_result.get("grounding_coverage", ""),
        "supported_claims": rag_result.get("supported_claims", 0),
        "total_claims": rag_result.get("total_claims", 0),
        "evidence": assistant_msg.evidence,
        "verification_results": assistant_msg.verification_results,
        "created_at": assistant_msg.created_at,
        "session_title": session.title,
        # Multi-RAG enhanced fields
        "answer": assistant_msg.content,
        "retrieval": rag_result.get("retrieval", {}),
        "grounded": rag_result.get("grounded", True),
        "citations": rag_result.get("citations", [])
    }

@app.post("/api/query")
def direct_query_endpoint(request: QueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Direct Multi-RAG clinical query endpoint."""
    return ask_question(request, user, db)

@app.get("/api/retrieval/metrics")
def get_retrieval_metrics(user: User = Depends(get_current_user)):
    """Exposes retrieval architecture configuration and index statistics."""
    from app.config import (
        RAG_DENSE_TOP_K, RAG_BM25_TOP_K, RAG_RRF_TOP_K, RAG_RRF_K,
        RAG_RERANK_TOP_K, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP,
        RAG_ENABLE_QUERY_REWRITE, RAG_ENABLE_BM25, RAG_ENABLE_RERANKER
    )
    from app.rag_pipeline import get_vector_store, get_bm25_index
    idx, meta, _ = get_vector_store()
    bm25 = get_bm25_index()
    return {
        "vector_index_count": idx.ntotal if idx else 0,
        "metadata_chunks_count": len(meta),
        "bm25_doc_count": bm25.N if bm25 else 0,
        "config": {
            "dense_top_k": RAG_DENSE_TOP_K,
            "bm25_top_k": RAG_BM25_TOP_K,
            "rrf_top_k": RAG_RRF_TOP_K,
            "rrf_k": RAG_RRF_K,
            "rerank_top_k": RAG_RERANK_TOP_K,
            "chunk_size": RAG_CHUNK_SIZE,
            "chunk_overlap": RAG_CHUNK_OVERLAP,
            "query_rewrite_enabled": RAG_ENABLE_QUERY_REWRITE,
            "bm25_enabled": RAG_ENABLE_BM25,
            "reranker_enabled": RAG_ENABLE_RERANKER
        }
    }

# ----------------- AUDIT LOGS (ADMIN ONLY) -----------------

@app.get("/api/audit-logs")
def get_audit_logs(limit: int = 100, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "user_name": l.user_name,
            "user_role": l.user_role,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "status": l.status,
            "details": l.details,
            "timestamp": l.timestamp
        } for l in logs
    ]
