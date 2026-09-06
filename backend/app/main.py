import os
import re
import uuid
import shutil
import random
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException, status, Form, Header, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
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
    hash_password, verify_password, create_access_token, decode_access_token,
    get_current_user, require_roles, log_audit_event, security_bearer
)
from app.document_validator import (
    validate_pdf_structure, evaluate_medical_relevance, 
    detect_version_and_duplicates, compute_md5
)
from app.rag_pipeline import (
    process_pdf, query_pipeline, remove_document_from_vector_store
)
from app.report_generator import generate_ai_patient_report, sync_report_to_knowledge_base, reconcile_unindexed_clinical_reports

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
    
    # Doctors & Interns can access assigned patients only
    if user_role_upper in ["DOCTOR", "INTERN"]:
        if patient.assigned_doctor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: You are not assigned to this patient's clinical care team."
            )
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
                
        # Reconcile unindexed clinical reports into Knowledge Base
        reconcile_unindexed_clinical_reports(db)
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
    respiratory_rate: Optional[int] = None
    temperature: Optional[float] = None
    spo2: Optional[int] = None
    blood_glucose: Optional[float] = None
    pain_score: Optional[int] = None
    intake_output: Optional[str] = None
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
    users = db.query(User).filter(User.status != "DELETED").order_by(User.id.asc()).all()
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
        
    cleaned_email = req.email.strip() if req.email and req.email.strip() else None

    # Check username uniqueness, and only check email uniqueness
    # when an email was actually supplied.
    query_filter = (User.username == req.username)
    if cleaned_email:
        query_filter = (
            (User.username == req.username) |
            (User.email == cleaned_email)
        )

    existing = db.query(User).filter(query_filter).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already in use.")
        
    new_user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role=role_upper,
        name=req.name,
        email=cleaned_email,
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

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_roles(["ADMIN"])), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")
    if target.status == "DELETED":
        raise HTTPException(status_code=400, detail="User is already deleted.")
        
    # Unassign any active patients assigned to this doctor
    patients_assigned = db.query(Patient).filter(Patient.assigned_doctor_id == target.id).all()
    for p in patients_assigned:
        p.assigned_doctor_id = None
        
    target.status = "DELETED"
    target.username = f"deleted_{target.id}_{target.username}"
    if target.email:
        target.email = f"deleted_{target.id}_{target.email}"
    db.commit()
    log_audit_event(db, admin, "USER_DELETED", "user", str(target.id), "SUCCESS", f"Deleted user {target.name} ({target.role})")
    return {"message": f"User {target.name} deleted successfully."}

@app.get("/api/doctors")
def list_doctors(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns active doctors for Front Desk assignment selector."""
    doctors = db.query(User).filter(
        User.role == "DOCTOR",
        User.status == "ACTIVE"
    ).order_by(User.name.asc()).all()
    
    return [
        {
            "id": d.id,
            "username": d.username,
            "name": d.name,
            "department": d.department or "General Medicine",
            "employee_id": d.employee_id
        } for d in doctors
    ]

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
        # Strict Doctor isolation: only return patients assigned to this clinician
        patients = query.filter(Patient.assigned_doctor_id == user.id).all()
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
def create_patient(req: PatientCreate, user: User = Depends(require_roles(["FRONT_DESK"])), db: Session = Depends(get_db)):
    # If assigned_doctor_id is supplied, verify doctor exists and has DOCTOR role
    if req.assigned_doctor_id:
        doc_user = db.query(User).filter(User.id == req.assigned_doctor_id, User.role == "DOCTOR").first()
        if not doc_user:
            raise HTTPException(status_code=400, detail=f"Doctor with ID {req.assigned_doctor_id} not found or is not a Doctor.")

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
                "respiratory_rate": v.respiratory_rate,
                "temperature": v.temperature,
                "spo2": v.spo2,
                "blood_glucose": v.blood_glucose,
                "pain_score": v.pain_score,
                "intake_output": v.intake_output,
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
def update_patient(patient_id: str, req: PatientUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    user_role_upper = (user.role or "").upper()
    
    # 1. Doctor Assignment / Reassignment -> FRONT_DESK ONLY
    if req.assigned_doctor_id is not None:
        if user_role_upper != "FRONT_DESK":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Only Front Desk staff are authorized to assign or reassign doctors."
            )
        doc_user = db.query(User).filter(User.id == req.assigned_doctor_id, User.role == "DOCTOR").first()
        if not doc_user:
            raise HTTPException(status_code=400, detail=f"Doctor with ID {req.assigned_doctor_id} not found or is not a Doctor.")
        patient.assigned_doctor_id = req.assigned_doctor_id
        
    # 2. Demographic Updates -> FRONT_DESK ONLY
    has_demo_updates = any(v is not None for v in [req.name, req.age, req.gender, req.blood_group, req.contact_details, req.department])
    if has_demo_updates:
        if user_role_upper != "FRONT_DESK":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Demographic updates are restricted to Front Desk staff."
            )
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
            
    # 3. Clinical Health Status -> Doctor (assigned) or Front Desk
    if req.health_status is not None:
        if user_role_upper in ["DOCTOR", "INTERN"]:
            verify_patient_access(user, patient_id, db)
        elif user_role_upper not in ["FRONT_DESK", "NURSE"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Unauthorized to update patient clinical health status."
            )
        patient.health_status = req.health_status
        
    db.commit()
    log_audit_event(db, user, "PATIENT_UPDATED", "patient", patient.id, "SUCCESS")
    return {"message": "Patient details updated successfully."}

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
def delete_patient(patient_id: str, user: User = Depends(require_roles(["FRONT_DESK", "ADMIN"])), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    patient.status = "DELETED"
    
    # 1. Unindex all patient clinical documents from vector store and mark DELETED
    docs = db.query(Document).filter(Document.patient_id == patient_id).all()
    for doc in docs:
        doc.approval_status = "DELETED"
        doc.status = "deleted"
        remove_document_from_vector_store(doc.id)
        
    # 2. Archive any clinical reports associated with this patient
    reports = db.query(ClinicalReport).filter(ClinicalReport.patient_id == patient_id).all()
    for rep in reports:
        rep.status = "ARCHIVED"
        
    db.commit()
    log_audit_event(db, user, "PATIENT_DELETED", "patient", patient.id, "SUCCESS", f"Deleted patient {patient.name} ({patient.id}) and unindexed associated documents.")
    return {"message": f"Patient record {patient_id} deleted successfully."}

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
        respiratory_rate=req.respiratory_rate,
        temperature=req.temperature,
        spo2=req.spo2,
        blood_glucose=req.blood_glucose,
        pain_score=req.pain_score,
        intake_output=req.intake_output,
        notes=req.notes
    )
    db.add(vitals)
    db.commit()
    db.refresh(vitals)
    log_audit_event(db, user, "VITALS_RECORDED", "patient", patient_id, "SUCCESS")
    return {
        "message": "Vitals recorded successfully.",
        "id": vitals.id,
        "blood_pressure": vitals.blood_pressure,
        "pulse": vitals.pulse,
        "respiratory_rate": vitals.respiratory_rate,
        "temperature": vitals.temperature,
        "spo2": vitals.spo2,
        "blood_glucose": vitals.blood_glucose,
        "pain_score": vitals.pain_score,
        "intake_output": vitals.intake_output,
        "notes": vitals.notes
    }

@app.get("/api/patients/{patient_id}/vitals")
def get_patient_vitals(patient_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    verify_patient_access(user, patient_id, db)
    vitals = db.query(PatientVitals).filter(PatientVitals.patient_id == patient_id).order_by(PatientVitals.timestamp.desc()).all()
    return [
        {
            "id": v.id,
            "blood_pressure": v.blood_pressure,
            "pulse": v.pulse,
            "respiratory_rate": v.respiratory_rate,
            "temperature": v.temperature,
            "spo2": v.spo2,
            "blood_glucose": v.blood_glucose,
            "pain_score": v.pain_score,
            "intake_output": v.intake_output,
            "notes": v.notes,
            "recorded_by": v.recorder.name if v.recorder else "System",
            "timestamp": v.timestamp.isoformat() if v.timestamp else None
        } for v in vitals
    ]

@app.delete("/api/patients/{patient_id}/vitals/{vitals_id}")
def delete_patient_vitals(
    patient_id: str,
    vitals_id: int,
    user: User = Depends(require_roles(["NURSE", "ADMIN"])),
    db: Session = Depends(get_db)
):
    vitals = db.query(PatientVitals).filter(
        PatientVitals.id == vitals_id,
        PatientVitals.patient_id == patient_id
    ).first()
    if not vitals:
        raise HTTPException(status_code=404, detail="Vitals record not found.")
        
    db.delete(vitals)
    db.commit()
    log_audit_event(
        db, user, "VITALS_DELETED", "patient", patient_id, "SUCCESS",
        f"Deleted vitals record {vitals_id} for patient {patient_id}"
    )
    return {"message": f"Vitals record {vitals_id} deleted successfully."}

# ----------------- LABORATORY ENDPOINTS -----------------

@app.get("/api/laboratory")
def list_laboratory_records(
    patient_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(LabResult)
    if patient_id:
        query = query.filter(LabResult.patient_id == patient_id)
    records = query.order_by(LabResult.timestamp.desc()).all()
    
    return [
        {
            "id": l.id,
            "patient_id": l.patient_id,
            "patient_name": l.patient.name if l.patient else l.patient_id,
            "hemoglobin": l.hemoglobin,
            "wbc": l.wbc,
            "crp": l.crp,
            "platelets": l.platelets,
            "notes": l.notes,
            "recorded_by": str(l.recorded_by),
            "technician_name": l.recorder.name if l.recorder else "Laboratory Staff",
            "timestamp": l.timestamp.isoformat() if l.timestamp else datetime.utcnow().isoformat()
        } for l in records
    ]

@app.post("/api/laboratory/upload")
async def upload_laboratory_record(
    background_tasks: BackgroundTasks,
    patient_id: str = Form(...),
    hemoglobin: Optional[str] = Form(None),
    wbc: Optional[str] = Form(None),
    crp: Optional[str] = Form(None),
    platelets: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: User = Depends(require_roles(["OTHER_STAFF", "LABORATORY_TECHNICIAN", "DOCTOR", "ADMIN", "NURSE"])),
    db: Session = Depends(get_db)
):
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required.")
        
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
        
    hb_val = None
    if hemoglobin not in (None, ""):
        try:
            hb_val = float(hemoglobin)
        except (ValueError, TypeError):
            pass

    wbc_val = None
    if wbc not in (None, ""):
        try:
            wbc_val = int(wbc)
        except (ValueError, TypeError):
            pass

    plt_val = None
    if platelets not in (None, ""):
        try:
            plt_val = int(platelets)
        except (ValueError, TypeError):
            pass

    crp_val = crp if crp not in (None, "") else None
    notes_val = notes if notes not in (None, "") else None

    lab = LabResult(
        patient_id=patient_id,
        recorded_by=user.id,
        hemoglobin=hb_val,
        wbc=wbc_val,
        crp=crp_val,
        platelets=plt_val,
        notes=notes_val
    )
    db.add(lab)
    db.commit()
    db.refresh(lab)
    
    doc_id = None
    if file and file.filename:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF documents are supported for laboratory attachments.")
            
        safe_name = os.path.basename(file.filename)
        safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
        temp_path = os.path.join(UPLOAD_DIR, safe_name)
        
        file_bytes = await file.read()
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
            
        valid_struct, struct_msg, page_count, extracted_text = validate_pdf_structure(temp_path)
        if not valid_struct:
            os.remove(temp_path)
            log_audit_event(db, user, "PDF_VALIDATION_FAILED", "document", safe_name, "FAILURE", struct_msg)
            raise HTTPException(status_code=400, detail=f"PDF Validation Failed: {struct_msg}")
            
        file_hash = compute_md5(file_bytes)
        version_info = detect_version_and_duplicates(safe_name, file_hash, db, Document, target_scope="patient")
        
        if not version_info["is_duplicate"]:
            db_doc = Document(
                name=safe_name,
                file_path=temp_path,
                status="processing",
                approval_status="ACTIVE",
                version=version_info["version"],
                medical_relevance_score=1.0,
                hash_md5=file_hash,
                scope="patient",
                patient_id=patient_id,
                uploaded_by=user.id,
                uploader_role=user.role,
                document_type="blood_report"
            )
            db.add(db_doc)
            db.commit()
            db.refresh(db_doc)
            doc_id = db_doc.id
            
            background_tasks.add_task(
                bg_process_pdf_task,
                temp_path,
                safe_name,
                db_doc.id,
                "patient",
                patient_id,
                version_info["version"],
                "blood_report"
            )
            
    log_audit_event(db, user, "LABORATORY_PANEL_RECORDED", "laboratory", str(lab.id), "SUCCESS", f"Recorded lab panel for patient {patient_id}")
    
    return {
        "message": "Laboratory results recorded successfully.",
        "id": lab.id,
        "patient_id": lab.patient_id,
        "patient_name": patient.name,
        "hemoglobin": lab.hemoglobin,
        "wbc": lab.wbc,
        "crp": lab.crp,
        "platelets": lab.platelets,
        "notes": lab.notes,
        "technician_name": user.name,
        "document_id": doc_id,
        "timestamp": lab.timestamp.isoformat() if lab.timestamp else datetime.utcnow().isoformat()
    }

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

@app.delete("/api/laboratory/{record_id}")
def delete_laboratory_record(
    record_id: int,
    user: User = Depends(require_roles(["LABORATORY_TECHNICIAN", "OTHER_STAFF", "ADMIN"])),
    db: Session = Depends(get_db)
):
    lab = db.query(LabResult).filter(LabResult.id == record_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratory record not found.")
        
    patient_id = lab.patient_id
    db.delete(lab)
    db.commit()
    
    log_audit_event(
        db, user, "LAB_RECORD_DELETED", "laboratory", str(record_id), "SUCCESS",
        f"Deleted laboratory record {record_id} for patient {patient_id}"
    )
    return {"message": f"Laboratory record {record_id} deleted successfully."}

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

# ----------------- RADIOLOGY ENDPOINTS -----------------

@app.get("/api/radiology")
def list_radiology_records(
    patient_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(RadiologyReport)
    if patient_id:
        query = query.filter(RadiologyReport.patient_id == patient_id)
    records = query.order_by(RadiologyReport.timestamp.desc()).all()
    
    return [
        {
            "id": r.id,
            "patient_id": r.patient_id,
            "patient_name": r.patient.name if r.patient else r.patient_id,
            "modality": r.modality or "X-Ray",
            "findings": r.findings or "",
            "impression": r.impression or "",
            "image_path": r.image_path,
            "document_id": r.document_id,
            "status": r.status or "FINAL",
            "radiologist_name": r.recorder.name if r.recorder else "Radiologist",
            "timestamp": r.timestamp.isoformat() if r.timestamp else datetime.utcnow().isoformat()
        } for r in records
    ]

@app.post("/api/radiology/upload")
async def upload_radiology_record(
    background_tasks: BackgroundTasks,
    patient_id: str = Form(...),
    modality: Optional[str] = Form("Chest X-Ray"),
    findings: str = Form(...),
    impression: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: User = Depends(require_roles(["RADIOLOGIST", "OTHER_STAFF", "DOCTOR", "ADMIN", "INTERN"])),
    db: Session = Depends(get_db)
):
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required.")
        
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
        
    if not findings or not findings.strip():
        raise HTTPException(status_code=400, detail="findings is required.")
        
    doc_id = None
    image_path = None
    if file and file.filename:
        filename_lower = file.filename.lower()
        safe_name = os.path.basename(file.filename)
        safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
        temp_path = os.path.join(UPLOAD_DIR, safe_name)
        
        file_bytes = await file.read()
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
            
        if filename_lower.endswith(".pdf"):
            valid_struct, struct_msg, page_count, extracted_text = validate_pdf_structure(temp_path)
            if not valid_struct:
                os.remove(temp_path)
                log_audit_event(db, user, "PDF_VALIDATION_FAILED", "document", safe_name, "FAILURE", struct_msg)
                raise HTTPException(status_code=400, detail=f"PDF Validation Failed: {struct_msg}")
                
            file_hash = compute_md5(file_bytes)
            version_info = detect_version_and_duplicates(safe_name, file_hash, db, Document, target_scope="patient")
            
            if not version_info["is_duplicate"]:
                db_doc = Document(
                    name=safe_name,
                    file_path=temp_path,
                    status="processing",
                    approval_status="ACTIVE",
                    version=version_info["version"],
                    medical_relevance_score=1.0,
                    hash_md5=file_hash,
                    scope="patient",
                    patient_id=patient_id,
                    uploaded_by=user.id,
                    uploader_role=user.role,
                    document_type="radiology_report"
                )
                db.add(db_doc)
                db.commit()
                db.refresh(db_doc)
                doc_id = db_doc.id
                
                background_tasks.add_task(
                    bg_process_pdf_task,
                    temp_path,
                    safe_name,
                    db_doc.id,
                    "patient",
                    patient_id,
                    version_info["version"],
                    "radiology_report"
                )
            else:
                existing_doc = db.query(Document).filter(Document.hash_md5 == file_hash).first()
                if existing_doc:
                    doc_id = existing_doc.id
        else:
            image_path = temp_path
            
    report = RadiologyReport(
        patient_id=patient_id,
        recorded_by=user.id,
        modality=modality or "Chest X-Ray",
        findings=findings.strip(),
        impression=impression.strip() if impression else None,
        image_path=image_path,
        document_id=doc_id,
        status="FINAL"
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    
    log_audit_event(
        db, user, "RADIOLOGY_REPORT_UPLOADED", "radiology", str(report.id), "SUCCESS",
        f"Recorded {report.modality} report for patient {patient_id}"
    )
    
    return {
        "message": "Radiology record logged successfully for patient.",
        "id": report.id,
        "patient_id": report.patient_id,
        "patient_name": patient.name,
        "modality": report.modality,
        "findings": report.findings,
        "impression": report.impression,
        "image_path": report.image_path,
        "document_id": report.document_id,
        "status": report.status,
        "radiologist_name": user.name,
        "timestamp": report.timestamp.isoformat() if report.timestamp else datetime.utcnow().isoformat()
    }

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

@app.delete("/api/radiology/{record_id}")
def delete_radiology_record(
    record_id: int,
    user: User = Depends(require_roles(["RADIOLOGIST", "OTHER_STAFF", "ADMIN"])),
    db: Session = Depends(get_db)
):
    report = db.query(RadiologyReport).filter(RadiologyReport.id == record_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Radiology report not found.")
        
    patient_id = report.patient_id
    doc_id = report.document_id
    
    # 1. If associated document exists, clean DB, vector store, and files
    if doc_id:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception:
                    pass
            doc.approval_status = "DELETED"
            doc.status = "deleted"
            if not doc.name.startswith("deleted_"):
                doc.name = f"deleted_{doc.id}_{doc.name}"
            db.commit()
            try:
                remove_document_from_vector_store(doc.id)
            except Exception as e:
                print(f"Error removing doc {doc.id} from vector store: {e}")
                
    # 2. If image file exists on disk, remove it
    if report.image_path and os.path.exists(report.image_path):
        try:
            os.remove(report.image_path)
        except Exception:
            pass
            
    # 3. Delete radiology report row
    db.delete(report)
    db.commit()
    
    log_audit_event(
        db, user, "RADIOLOGY_RECORD_DELETED", "radiology", str(record_id), "SUCCESS",
        f"Deleted radiology record {record_id} for patient {patient_id}"
    )
    return {"message": f"Radiology record {record_id} deleted successfully."}

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
    verify_patient_access(user, report.patient_id, db)
        
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
    db.refresh(report)
    
    # Re-sync updated report to Knowledge Base ONLY if it is already approved
    if report.status == "APPROVED":
        sync_report_to_knowledge_base(report, user, db)
    
    log_audit_event(db, user, "REPORT_EDITED", "clinical_report", str(report.id), "SUCCESS")
    return {"message": "Report updated successfully."}

@app.post("/api/reports/{report_id}/approve")
def approve_report(report_id: int, user: User = Depends(require_roles(["DOCTOR", "ADMIN"])), db: Session = Depends(get_db)):
    report = db.query(ClinicalReport).filter(ClinicalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    verify_patient_access(user, report.patient_id, db)
        
    report.status = "APPROVED"
    report.approved_at = datetime.utcnow()
    report.approved_by = user.id
    db.commit()
    db.refresh(report)
    
    # Sync approved authoritative report to Knowledge Base (FAISS + BM25)
    sync_report_to_knowledge_base(report, user, db)
    
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

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF documents are supported.")
        
    safe_name = os.path.basename(file.filename)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
    if scope == "temporary":
        safe_name = f"temp_{uuid.uuid4().hex[:8]}_{safe_name}"
    temp_path = os.path.join(UPLOAD_DIR, safe_name)
    
    # Free name slot if an old soft-deleted record exists with same name
    existing_name_doc = db.query(Document).filter(Document.name == safe_name).first()
    if existing_name_doc:
        if existing_name_doc.approval_status == "DELETED":
            if not existing_name_doc.name.startswith("deleted_"):
                existing_name_doc.name = f"deleted_{existing_name_doc.id}_{existing_name_doc.name}"
                db.commit()
    
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
    version_info = detect_version_and_duplicates(safe_name, file_hash, db, Document, target_scope=scope)
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
        
    # Remove physical file from disk if present
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    doc.approval_status = "DELETED"
    doc.status = "deleted"
    if not doc.name.startswith("deleted_"):
        doc.name = f"deleted_{doc.id}_{doc.name}"
    db.commit()
    remove_document_from_vector_store(doc.id)
    log_audit_event(db, admin, "DOCUMENT_DELETED", "document", str(doc.id), "SUCCESS", f"Deleted document {doc.name}")
    return {"message": f"Document '{doc.name}' deleted."}

@app.delete("/api/chat/attachments/{doc_id}")
def detach_chat_attachment(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Attachment not found.")
        
    if doc.scope != "temporary":
        raise HTTPException(status_code=400, detail="Only temporary session attachments can be detached via this endpoint.")
        
    if doc.uploaded_by != user.id and (user.role or "").upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Permission denied to detach this attachment.")
        
    # 1. Clean physical file from disk
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass
            
    # 2. Mark as DELETED in database
    doc.approval_status = "DELETED"
    doc.status = "deleted"
    if not doc.name.startswith("deleted_"):
        doc.name = f"deleted_{doc.id}_{doc.name}"
    db.commit()
    
    # 3. Synchronize vector stores (removes chunks from chunks.pkl, FAISS, and BM25)
    remove_document_from_vector_store(doc.id)
    
    log_audit_event(db, user, "TEMPORARY_ATTACHMENT_DETACHED", "document", str(doc.id), "SUCCESS", f"Detached temporary chat attachment '{doc.name}' and cleaned all vectors.")
    return {"message": f"Temporary attachment '{doc.name}' detached and completely cleaned up."}

@app.get("/api/documents/{doc_id}/file")
def get_document_file(
    doc_id: int,
    token: Optional[str] = Query(None),
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
):
    """
    Secure file serving endpoint. Validates user authentication (Bearer token or query param)
    and enforces server-side patient isolation if document belongs to a patient.
    """
    user = None
    auth_token = None
    if auth_creds and auth_creds.credentials:
        auth_token = auth_creds.credentials
    elif token:
        auth_token = token
        
    if auth_token:
        try:
            payload = decode_access_token(auth_token)
            username = payload.get("sub") or payload.get("username")
            if username:
                user = db.query(User).filter(User.username == username).first()
        except Exception:
            pass
            
    if not user or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not found or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    if doc.approval_status == "DELETED":
        raise HTTPException(status_code=404, detail="Document has been deleted.")
        
    # Patient isolation authorization check
    if doc.scope == "patient" and doc.patient_id:
        verify_patient_access(user, doc.patient_id, db)
        
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Physical document file not found on disk.")
        
    lower_path = doc.file_path.lower()
    if lower_path.endswith(".pdf"):
        media_type = "application/pdf"
    elif lower_path.endswith(".txt"):
        media_type = "text/plain"
    elif lower_path.endswith(".png"):
        media_type = "image/png"
    elif lower_path.endswith(".jpg") or lower_path.endswith(".jpeg"):
        media_type = "image/jpeg"
    else:
        media_type = "application/octet-stream"
        
    log_audit_event(db, user, "DOCUMENT_FILE_ACCESSED", "document", str(doc.id), "SUCCESS", f"Viewed file {doc.name}")
    
    return FileResponse(
        path=doc.file_path,
        media_type=media_type,
        filename=doc.name
    )

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
        
        # Direct LLM mode check: if confidence is None, do not show any grounding/RAG scores
        if m.confidence_score is None and m.confidence_level is None:
            g_level = None
            cov = ""
        elif tot == 0:
            g_level = "Not Supported" if (m.confidence_level or "").lower() == "low" else "Partially Supported"
            cov = ""
        elif contra > 0:
            g_level = "Not Supported"
            cov = f"{sup} of {tot} claims supported"
        elif sup == tot and tot > 0:
            g_level = "Strongly Supported"
            cov = f"{sup} of {tot} claims supported"
        elif sup > 0 or part > 0:
            g_level = "Partially Supported"
            cov = f"{sup} of {tot} claims supported"
        else:
            g_level = "Not Supported"
            cov = f"{sup} of {tot} claims supported"

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
    if not request.direct_llm and filters.get("scope") in ["patient", "patient_and_kb"]:
        patient_id = filters.get("patient_id")
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required for patient scope queries.")
        verify_patient_access(user, patient_id, db)
        
    # Get active approved documents (only needed in RAG mode)
    if not request.direct_llm:
        active_docs = db.query(Document.id).filter(Document.approval_status == "ACTIVE").all()
        active_doc_ids = {d[0] for d in active_docs}
    else:
        active_doc_ids = set()
    
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
            active_doc_ids=active_doc_ids,
            db=db
        )
    except Exception as e:
        db.delete(user_msg)
        db.commit()
        log_audit_event(db, user, "RAG_QUERY_FAILED", "session", request.session_id, "FAILURE", str(e))
        raise HTTPException(status_code=500, detail=f"Query failure: {str(e)}")
        
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
    
    log_audit_event(db, user, "QUERY_COMPLETED", "session", request.session_id, "SUCCESS", f"Mode: {'direct_llm' if request.direct_llm else 'strict_rag'}")
    
    return {
        "id": assistant_msg.id,
        "role": assistant_msg.role,
        "content": assistant_msg.content,
        "confidence_level": assistant_msg.confidence_level,
        "confidence_score": assistant_msg.confidence_score,
        "grounding_level": rag_result.get("grounding_level"),
        "grounding_coverage": rag_result.get("grounding_coverage", ""),
        "supported_claims": rag_result.get("supported_claims", 0),
        "total_claims": rag_result.get("total_claims", 0),
        "evidence": assistant_msg.evidence,
        "verification_results": assistant_msg.verification_results,
        "created_at": assistant_msg.created_at,
        "session_title": session.title,
        # Multi-RAG enhanced fields
        "mode": "direct_llm" if request.direct_llm else "strict_rag",
        "answer": assistant_msg.content,
        "retrieval": rag_result.get("retrieval", {}),
        "grounded": rag_result.get("grounded", False if request.direct_llm else True),
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
