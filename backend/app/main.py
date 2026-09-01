import os
import re
import shutil
from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException, Security, status, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.config import UPLOAD_DIR, SEED_DIR, CDSS_API_KEY, GROQ_API_KEY
from app.database import get_db, init_db, Document, ChatSession, ChatMessage, User, Patient, PatientVitals, LabResult, RadiologyReport, ClinicalNote
from app.rag_pipeline import process_pdf, query_pipeline

# Initialize database tables
init_db()

app = FastAPI(title="Clinical RAG Decision Support System API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Security Definition
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    """Validates the incoming client request API Key header against CDSS_API_KEY configuration."""
    if CDSS_API_KEY and api_key != CDSS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Invalid X-API-Key credentials"
        )
    return api_key

# Dependency to authenticate current user via X-User-Id header
def get_current_user(x_user_id: str = Header(None), db: Session = Depends(get_db)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user credentials.")
    user = db.query(User).filter(User.username == x_user_id).first()
    if not user:
        # Check if ID was sent instead of username
        user = db.query(User).filter(User.id == int(x_user_id) if x_user_id.isdigit() else False).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

# Helper to verify patient access control
def verify_patient_access(user: User, patient_id: str, db: Session):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    
    # Simple Access Rules
    # Doctors and Interns can only access patient profiles assigned to them
    if user.role in ["doctor", "intern"]:
        if patient.assigned_doctor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: You are not assigned to patient {patient_id}."
            )
    return patient

# Pydantic Schemas
class SessionCreate(BaseModel):
    title: str

class QueryRequest(BaseModel):
    session_id: str
    query: str
    filters: dict = None  # scope: knowledge_base/patient/temporary, patient_id, document_id
    direct_llm: bool = False

class LoginRequest(BaseModel):
    username: str

class VitalsCreate(BaseModel):
    blood_pressure: str = None
    pulse: int = None
    temperature: float = None
    spo2: int = None
    notes: str = None

class LabsCreate(BaseModel):
    hemoglobin: float = None
    wbc: int = None
    crp: str = None
    notes: str = None

class NotesCreate(BaseModel):
    notes: str

class RadiologyCreate(BaseModel):
    findings: str
    document_id: int = None

# Background task for PDF ingestion
def bg_process_pdf(file_path: str, filename: str, doc_id: int, scope: str, patient_id: str):
    db = next(get_db())
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return
        
    try:
        chunk_count = process_pdf(file_path, filename, doc_id=doc_id, scope=scope, patient_id=patient_id)
        doc.status = "completed"
        doc.chunk_count = chunk_count
    except Exception as e:
        print(f"Error processing PDF in background: {e}")
        doc.status = "failed"
    finally:
        db.commit()
        db.close()

# Startup Event: Pre-load guideline seed PDFs placed in 'seed_data/' directory by developer
@app.on_event("startup")
def startup_populate_seed_data():
    print(f"Startup check: Scanning seed folder ({SEED_DIR}) for new clinical guideline guidelines...")
    if not os.path.exists(SEED_DIR):
        os.makedirs(SEED_DIR, exist_ok=True)
        return
        
    db = next(get_db())
    try:
        pdf_files = [f for f in os.listdir(SEED_DIR) if f.endswith(".pdf")]
        if not pdf_files:
            print("No clinical seed documents detected in seed_data/.")
            return

        for filename in pdf_files:
            safe_name = os.path.basename(filename)
            safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
            
            existing = db.query(Document).filter(Document.name == safe_name).first()
            if not existing:
                print(f"Pre-loading developer seed guideline: {safe_name}...")
                src_path = os.path.join(SEED_DIR, filename)
                dest_path = os.path.join(UPLOAD_DIR, safe_name)
                
                shutil.copy2(src_path, dest_path)
                
                db_doc = Document(
                    name=safe_name, 
                    file_path=dest_path, 
                    status="processing", 
                    scope="knowledge_base"
                )
                db.add(db_doc)
                db.commit()
                db.refresh(db_doc)
                
                try:
                    chunk_count = process_pdf(dest_path, safe_name, doc_id=db_doc.id, scope="knowledge_base")
                    db_doc.status = "completed"
                    db_doc.chunk_count = chunk_count
                    print(f"Successfully pre-loaded and indexed {safe_name} ({chunk_count} chunks).")
                except Exception as e:
                    print(f"Failed to process seed guideline {safe_name}: {e}")
                    db_doc.status = "failed"
                db.commit()
    except Exception as e:
        print(f"Error in seed pre-loading: {e}")
    finally:
        db.close()

# Public Endpoints
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "groq_api_key_configured": bool(GROQ_API_KEY),
        "gemini_api_key_configured": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "security_enabled": bool(CDSS_API_KEY)
    }

@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username. Please choose from seeded demo users.")
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "name": user.name
    }

# Protected Patient Endpoints
@app.get("/api/patients", dependencies=[Depends(verify_api_key)])
def get_patients(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Doctors & Interns can only see assigned patients.
    if user.role in ["doctor", "intern"]:
        patients = db.query(Patient).filter(Patient.assigned_doctor_id == user.id).all()
    else:
        patients = db.query(Patient).all()
        
    return [
        {
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "health_status": p.health_status,
            "assigned_doctor": p.assigned_doctor.name if p.assigned_doctor else None
        } for p in patients
    ]

@app.get("/api/patients/{patient_id}", dependencies=[Depends(verify_api_key)])
def get_patient_profile(patient_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = verify_patient_access(user, patient_id, db)
    
    # Fetch medical history items
    vitals = db.query(PatientVitals).filter(PatientVitals.patient_id == patient_id).order_by(PatientVitals.timestamp.desc()).all()
    labs = db.query(LabResult).filter(LabResult.patient_id == patient_id).order_by(LabResult.timestamp.desc()).all()
    radiology = db.query(RadiologyReport).filter(RadiologyReport.patient_id == patient_id).order_by(RadiologyReport.timestamp.desc()).all()
    notes = db.query(ClinicalNote).filter(ClinicalNote.patient_id == patient_id).order_by(ClinicalNote.timestamp.desc()).all()
    documents = db.query(Document).filter(Document.patient_id == patient_id).order_by(Document.created_at.desc()).all()
    
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "health_status": patient.health_status,
        "assigned_doctor": patient.assigned_doctor.name if patient.assigned_doctor else None,
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
                "chunk_count": d.chunk_count,
                "scope": d.scope,
                "document_type": d.document_type,
                "created_at": d.created_at
            } for d in documents
        ]
    }

@app.post("/api/patients/{patient_id}/vitals", dependencies=[Depends(verify_api_key)])
def record_vitals(patient_id: str, req: VitalsCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "nurse":
        raise HTTPException(status_code=403, detail="Only nurses are authorized to record vitals.")
    
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
    return {"message": "Vitals recorded successfully."}

@app.post("/api/patients/{patient_id}/labs", dependencies=[Depends(verify_api_key)])
def record_labs(patient_id: str, req: LabsCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "laboratory":
        raise HTTPException(status_code=403, detail="Only laboratory technicians are authorized to record lab results.")
    
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    labs = LabResult(
        patient_id=patient_id,
        recorded_by=user.id,
        hemoglobin=req.hemoglobin,
        wbc=req.wbc,
        crp=req.crp,
        notes=req.notes
    )
    db.add(labs)
    db.commit()
    return {"message": "Lab results recorded successfully."}

@app.post("/api/patients/{patient_id}/notes", dependencies=[Depends(verify_api_key)])
def record_clinical_notes(patient_id: str, req: NotesCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ["doctor", "intern"]:
        raise HTTPException(status_code=403, detail="Only clinicians/interns are authorized to write clinical notes.")
    
    verify_patient_access(user, patient_id, db)
    
    note = ClinicalNote(
        patient_id=patient_id,
        author_id=user.id,
        notes=req.notes
    )
    db.add(note)
    db.commit()
    return {"message": "Clinical note added successfully."}

@app.post("/api/patients/{patient_id}/radiology", dependencies=[Depends(verify_api_key)])
def record_radiology(patient_id: str, req: RadiologyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "radiologist":
        raise HTTPException(status_code=403, detail="Only radiologists are authorized to log radiology reports.")
    
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
    return {"message": "Radiology findings logged successfully."}

# Documents
@app.get("/api/documents", dependencies=[Depends(verify_api_key)])
def get_documents(scope: str = None, patient_id: str = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Document)
    
    # Apply scope filters
    if scope:
        query = query.filter(Document.scope == scope)
    if patient_id:
        verify_patient_access(user, patient_id, db)
        query = query.filter(Document.patient_id == patient_id)
        
    # If no filters but doctor/intern, they should only see assigned patient docs or KB docs
    if not scope and not patient_id and user.role in ["doctor", "intern"]:
        assigned_p_ids = [p.id for p in db.query(Patient).filter(Patient.assigned_doctor_id == user.id).all()]
        query = query.filter((Document.scope == "knowledge_base") | (Document.patient_id.in_(assigned_p_ids)) | (Document.uploaded_by == user.id))
        
    docs = query.order_by(Document.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "scope": d.scope,
            "patient_id": d.patient_id,
            "uploaded_by": d.uploader.name if d.uploader else "System",
            "uploader_role": d.uploader_role,
            "document_type": d.document_type,
            "created_at": d.created_at
        }
        for d in docs
    ]

@app.post("/api/upload", dependencies=[Depends(verify_api_key)])
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scope: str = Form("knowledge_base"),
    patient_id: str = Form(None),
    document_type: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")
        
    if scope == "patient":
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required for patient scope.")
        verify_patient_access(user, patient_id, db)
    elif scope == "knowledge_base" and user.role not in ["doctor", "intern"]:
        # Only doctors and interns can upload to Knowledge Base for prototype security
        raise HTTPException(status_code=403, detail="You do not have permission to upload general knowledge base resources.")
        
    safe_name = os.path.basename(file.filename)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
    
    # Check if document already exists
    existing = db.query(Document).filter(Document.name == safe_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Document '{safe_name}' already uploaded.")
        
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    db_doc = Document(
        name=safe_name, 
        file_path=file_path, 
        status="processing",
        scope=scope,
        patient_id=patient_id,
        uploaded_by=user.id,
        uploader_role=user.role,
        document_type=document_type
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    background_tasks.add_task(bg_process_pdf, file_path, safe_name, db_doc.id, scope, patient_id)
    
    return {
        "id": db_doc.id,
        "name": db_doc.name,
        "status": db_doc.status,
        "scope": db_doc.scope,
        "patient_id": db_doc.patient_id,
        "message": "File uploaded successfully. Processing started in the background."
    }

# Chat Sessions
@app.get("/api/sessions", dependencies=[Depends(verify_api_key)])
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
        }
        for s in sessions
    ]

@app.post("/api/sessions", dependencies=[Depends(verify_api_key)])
def create_session(request: SessionCreate, patient_id: str = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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

@app.delete("/api/sessions/{session_id}", dependencies=[Depends(verify_api_key)])
def delete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to delete this session.")
        
    db.delete(session)
    db.commit()
    return {"message": "Session deleted successfully."}

@app.get("/api/sessions/{session_id}/messages", dependencies=[Depends(verify_api_key)])
def get_messages(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to view messages in this session.")
        
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "confidence_level": m.confidence_level,
            "confidence_score": m.confidence_score,
            "evidence": m.evidence,
            "verification_results": m.verification_results,
            "created_at": m.created_at
        }
        for m in messages
    ]

@app.post("/api/ask", dependencies=[Depends(verify_api_key)])
def ask_question(request: QueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to chat in this session.")
        
    # Apply security screening for filters
    filters = request.filters or {}
    if filters.get("scope") == "patient" or filters.get("scope") == "patient_and_kb":
        patient_id = filters.get("patient_id")
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required for patient scope querying.")
        verify_patient_access(user, patient_id, db)
    elif filters.get("scope") == "temporary":
        doc_id = filters.get("document_id")
        if not doc_id:
            raise HTTPException(status_code=400, detail="document_id is required for temporary document Q&A.")
        # Verify document exists and belongs to user session
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

    # 1. Save user query in DB
    user_msg = ChatMessage(
        session_id=request.session_id,
        role="user",
        content=request.query
    )
    db.add(user_msg)
    db.commit()
    
    # 2. Run query through RAG pipeline
    try:
        rag_result = query_pipeline(request.query, filters=filters, direct_llm=request.direct_llm)
    except Exception as e:
        db.delete(user_msg)
        db.commit()
        raise HTTPException(status_code=500, detail=f"RAG pipeline failure: {str(e)}")
        
    # Update chat session title if it was default
    if session.title == "New Chat" or session.title.startswith("New Consultation") or session.title.startswith("New Chat"):
        session.title = request.query[:40] + ("..." if len(request.query) > 40 else "")
        
    # 3. Save assistant response in DB
    assistant_msg = ChatMessage(
        session_id=request.session_id,
        role="assistant",
        content=rag_result["answer"],
        confidence_level=rag_result["confidence_level"],
        confidence_score=rag_result["confidence_score"],
    )
    assistant_msg.evidence = rag_result["evidence"]
    assistant_msg.verification_results = rag_result["verification_results"]
    
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    
    return {
        "id": assistant_msg.id,
        "role": assistant_msg.role,
        "content": assistant_msg.content,
        "confidence_level": assistant_msg.confidence_level,
        "confidence_score": assistant_msg.confidence_score,
        "evidence": assistant_msg.evidence,
        "verification_results": assistant_msg.verification_results,
        "created_at": assistant_msg.created_at,
        "session_title": session.title
    }
