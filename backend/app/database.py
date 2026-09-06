import json
import uuid
import hashlib
import secrets
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import DATABASE_URL

# Setup SQLAlchemy engine and session
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def hash_pw_seed(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 100000
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations, dklen=32)
    return f"pbkdf2_sha256${iterations}${salt}${key.hex()}"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # ADMIN, DOCTOR, FRONT_DESK, INTERN, NURSE, OTHER_STAFF
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=True)
    employee_id = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, INACTIVE
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_patients = relationship("Patient", foreign_keys="Patient.assigned_doctor_id", back_populates="assigned_doctor")
    created_patients = relationship("Patient", foreign_keys="Patient.created_by", back_populates="creator")

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(50), primary_key=True, index=True)  # e.g., PAT-2026-000101
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    dob = Column(String(50), nullable=True)
    gender = Column(String(20), nullable=False)
    blood_group = Column(String(10), nullable=True)
    contact_details = Column(Text, nullable=True)
    department = Column(String(100), default="General Medicine")
    health_status = Column(String(100), default="Under Review")
    status = Column(String(50), default="ACTIVE")  # ACTIVE, DISCHARGED, ARCHIVED, DELETED
    
    assigned_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    admission_date = Column(DateTime, default=datetime.utcnow)
    discharge_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_doctor = relationship("User", foreign_keys=[assigned_doctor_id], back_populates="assigned_patients")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_patients")
    
    vitals = relationship("PatientVitals", back_populates="patient", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")
    radiology_reports = relationship("RadiologyReport", back_populates="patient", cascade="all, delete-orphan")
    clinical_notes = relationship("ClinicalNote", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    reports = relationship("ClinicalReport", back_populates="patient", cascade="all, delete-orphan")

class PatientVitals(Base):
    __tablename__ = "patient_vitals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    blood_pressure = Column(String(50), nullable=True)
    pulse = Column(Integer, nullable=True)
    respiratory_rate = Column(Integer, nullable=True)
    temperature = Column(Float, nullable=True)
    spo2 = Column(Integer, nullable=True)
    blood_glucose = Column(Float, nullable=True)
    pain_score = Column(Integer, nullable=True)
    intake_output = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="vitals")
    recorder = relationship("User")

class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    hemoglobin = Column(Float, nullable=True)
    wbc = Column(Integer, nullable=True)
    crp = Column(String(50), nullable=True)
    platelets = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="lab_results")
    recorder = relationship("User")

class RadiologyReport(Base):
    __tablename__ = "radiology_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    modality = Column(String(50), nullable=True, default="X-Ray")
    findings = Column(Text, nullable=True)
    impression = Column(Text, nullable=True)
    image_path = Column(String(512), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), nullable=True, default="FINAL")
    timestamp = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="radiology_reports")
    recorder = relationship("User")
    document = relationship("Document")

class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="clinical_notes")
    author = relationship("User")

class ClinicalReport(Base):
    __tablename__ = "clinical_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    chief_complaint = Column(Text, nullable=True)
    clinical_history = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)
    investigations = Column(Text, nullable=True)
    clinical_assessment = Column(Text, nullable=True)
    relevant_evidence = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    sources = Column(Text, nullable=True)
    status = Column(String(50), default="AI-GENERATED DRAFT")  # AI-GENERATED DRAFT, APPROVED, ARCHIVED
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    patient = relationship("Patient", back_populates="reports")
    doctor = relationship("User", foreign_keys=[doctor_id])
    approver = relationship("User", foreign_keys=[approved_by])

class TrustedSource(Base):
    __tablename__ = "trusted_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    domain = Column(String(200), nullable=False)
    source_type = Column(String(100), default="guideline")  # guideline, textbook, research_paper, institutional
    approval_status = Column(String(50), default="APPROVED")  # APPROVED, PENDING, REJECTED
    institution_approved = Column(Boolean, default=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    file_path = Column(String(512), nullable=False)
    status = Column(String(50), default="processing")  # processing, completed, failed
    approval_status = Column(String(50), default="ACTIVE")  # PENDING, APPROVED, ACTIVE, FLAGGED, ARCHIVED, DELETED
    version = Column(String(50), default="1.0")
    medical_relevance_score = Column(Float, nullable=True)
    hash_md5 = Column(String(64), nullable=True)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Scope metadata
    scope = Column(String(50), default="knowledge_base")  # knowledge_base, patient, temporary
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploader_role = Column(String(50), nullable=True)
    document_type = Column(String(100), nullable=True)  # guideline, textbook, research_paper, blood_report, radiology_report, nursing_report, medical_history, other

    patient = relationship("Patient", back_populates="documents")
    uploader = relationship("User")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_name = Column(String(100), nullable=True)
    user_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    status = Column(String(50), default="SUCCESS")  # SUCCESS, FAILURE, DENIED
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_id = Column(String(50), ForeignKey("patients.id"), nullable=True)
    
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    user = relationship("User")
    patient = relationship("Patient")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(50), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    
    # RAG metadata (Assistant messages only)
    confidence_level = Column(String(50), nullable=True)  # High, Medium, Low
    confidence_score = Column(Float, nullable=True)
    
    # Store complex lists as JSON string
    _evidence = Column("evidence", Text, nullable=True)
    _verification_results = Column("verification_results", Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    @property
    def evidence(self):
        if self._evidence:
            return json.loads(self._evidence)
        return []

    @evidence.setter
    def evidence(self, value):
        self._evidence = json.dumps(value)

    @property
    def verification_results(self):
        if self._verification_results:
            return json.loads(self._verification_results)
        return []

    @verification_results.setter
    def verification_results(self, value):
        self._verification_results = json.dumps(value)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Ensure all columns exist in sqlite schema
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(radiology_reports)"))
            existing_cols = {row[1] for row in result.fetchall()}
            if existing_cols:
                if "modality" not in existing_cols:
                    conn.execute(text("ALTER TABLE radiology_reports ADD COLUMN modality VARCHAR(50)"))
                if "impression" not in existing_cols:
                    conn.execute(text("ALTER TABLE radiology_reports ADD COLUMN impression TEXT"))
                if "image_path" not in existing_cols:
                    conn.execute(text("ALTER TABLE radiology_reports ADD COLUMN image_path VARCHAR(512)"))
                if "status" not in existing_cols:
                    conn.execute(text("ALTER TABLE radiology_reports ADD COLUMN status VARCHAR(50)"))
                conn.commit()

            result_vitals = conn.execute(text("PRAGMA table_info(patient_vitals)"))
            vitals_cols = {row[1] for row in result_vitals.fetchall()}
            if vitals_cols:
                if "respiratory_rate" not in vitals_cols:
                    conn.execute(text("ALTER TABLE patient_vitals ADD COLUMN respiratory_rate INTEGER"))
                if "blood_glucose" not in vitals_cols:
                    conn.execute(text("ALTER TABLE patient_vitals ADD COLUMN blood_glucose FLOAT"))
                if "pain_score" not in vitals_cols:
                    conn.execute(text("ALTER TABLE patient_vitals ADD COLUMN pain_score INTEGER"))
                if "intake_output" not in vitals_cols:
                    conn.execute(text("ALTER TABLE patient_vitals ADD COLUMN intake_output VARCHAR(255)"))
                conn.commit()
    except Exception:
        pass

    db = SessionLocal()
    try:
        # Seed users if missing
        users = [
            User(
                username="admin",
                password_hash=hash_pw_seed("Admin@123"),
                role="ADMIN",
                name="Hospital Administrator",
                email="admin@hospital.org",
                employee_id="EMP-ADM-001",
                department="Administration",
                status="ACTIVE"
            ),
            User(
                username="reshma",
                password_hash=hash_pw_seed("reshma@123"),
                role="DOCTOR",
                name="Dr. Reshma",
                email="reshma@hospital.org",
                employee_id="EMP-DOC-103",
                department="Internal Medicine",
                status="ACTIVE"
            ),
            User(
                username="prakash_rad",
                password_hash=hash_pw_seed("Radio@123"),
                role="RADIOLOGIST",
                name="Dr. Prakash (Radiology)",
                email="prakash@hospital.org",
                employee_id="EMP-RAD-402",
                department="Radiology",
                status="ACTIVE"
            ),
            User(
                username="rakshith",
                password_hash=hash_pw_seed("rakshith@123"),
                role="LABORATORY_TECHNICIAN",
                name="Rakshith (Lab Tech)",
                email="rakshith@hospital.org",
                employee_id="EMP-LAB-502",
                department="Pathology",
                status="ACTIVE"
            ),
            User(
                username="riya",
                password_hash=hash_pw_seed("riya@123"),
                role="NURSE",
                name="Riya (Staff Nurse)",
                email="riya@hospital.org",
                employee_id="EMP-NUR-302",
                department="Inpatient Ward",
                status="ACTIVE"
            ),
            User(
                username="shreya",
                password_hash=hash_pw_seed("shreya@123"),
                role="FRONT_DESK",
                name="Shreya (Front Desk)",
                email="shreya@hospital.org",
                employee_id="EMP-FD-202",
                department="Patient Registration",
                status="ACTIVE"
            ),
            User(
                username="arun",
                password_hash=hash_pw_seed("Doctor@123"),
                role="DOCTOR",
                name="Dr. Arun",
                email="arun@hospital.org",
                employee_id="EMP-DOC-101",
                department="Internal Medicine",
                status="ACTIVE"
            ),
            User(
                username="meera",
                password_hash=hash_pw_seed("Doctor@123"),
                role="DOCTOR",
                name="Dr. Meera",
                email="meera@hospital.org",
                employee_id="EMP-DOC-102",
                department="Cardiology",
                status="ACTIVE"
            ),
            User(
                username="frontdesk",
                password_hash=hash_pw_seed("Front@123"),
                role="FRONT_DESK",
                name="Sarah (Front Desk)",
                email="frontdesk@hospital.org",
                employee_id="EMP-FD-201",
                department="Patient Registration",
                status="ACTIVE"
            ),
            User(
                username="priya",
                password_hash=hash_pw_seed("Nurse@123"),
                role="NURSE",
                name="Priya (Staff Nurse)",
                email="priya@hospital.org",
                employee_id="EMP-NUR-301",
                department="Inpatient Ward",
                status="ACTIVE"
            ),
            User(
                username="arjun_intern",
                password_hash=hash_pw_seed("Intern@123"),
                role="INTERN",
                name="Arjun (Resident Intern)",
                email="arjun@hospital.org",
                employee_id="EMP-INT-601",
                department="Internal Medicine",
                status="ACTIVE"
            ),
            User(
                username="rahul_rad",
                password_hash=hash_pw_seed("Staff@123"),
                role="OTHER_STAFF",
                name="Rahul (Radiologist)",
                email="rahul@hospital.org",
                employee_id="EMP-RAD-401",
                department="Radiology",
                status="ACTIVE"
            ),
            User(
                username="ananya_lab",
                password_hash=hash_pw_seed("Staff@123"),
                role="OTHER_STAFF",
                name="Ananya (Lab Tech)",
                email="ananya@hospital.org",
                employee_id="EMP-LAB-501",
                department="Pathology",
                status="ACTIVE"
            ),
        ]
        for u in users:
            existing = db.query(User).filter(User.username == u.username).first()
            if not existing:
                db.add(u)
            else:
                if u.username != "admin":
                    existing.password_hash = u.password_hash
                    existing.role = u.role
                    existing.status = u.status
        db.commit()

        # Seed Trusted Sources
        if db.query(TrustedSource).count() == 0:
            sources = [
                TrustedSource(name="World Health Organization (WHO)", domain="who.int", source_type="guideline", approval_status="APPROVED", institution_approved=True),
                TrustedSource(name="Centers for Disease Control and Prevention (CDC)", domain="cdc.gov", source_type="guideline", approval_status="APPROVED", institution_approved=True),
                TrustedSource(name="National Library of Medicine (NIH/NLM)", domain="nih.gov", source_type="research_paper", approval_status="APPROVED", institution_approved=True),
                TrustedSource(name="Infectious Diseases Society of America (IDSA)", domain="idsociety.org", source_type="guideline", approval_status="APPROVED", institution_approved=True),
            ]
            for s in sources:
                db.add(s)
            db.commit()

        # Seed Initial Patients if empty
        if db.query(Patient).count() == 0:
            print("Seeding initial patient records...")
            doc_arun = db.query(User).filter(User.username == "arun").first()
            doc_meera = db.query(User).filter(User.username == "meera").first()
            admin_user = db.query(User).filter(User.username == "admin").first()
            
            patients = [
                Patient(
                    id="PAT-2026-000101",
                    name="Rahul Sharma",
                    age=45,
                    gender="Male",
                    dob="1981-05-12",
                    blood_group="O+",
                    contact_details="+91 98765 43210, Bangalore",
                    department="Pulmonology",
                    health_status="Under Review",
                    status="ACTIVE",
                    assigned_doctor_id=doc_arun.id if doc_arun else None,
                    created_by=admin_user.id if admin_user else None
                ),
                Patient(
                    id="PAT-2026-000102",
                    name="Ananya Verma",
                    age=32,
                    gender="Female",
                    dob="1994-08-22",
                    blood_group="A+",
                    contact_details="+91 98111 22233, Mumbai",
                    department="Internal Medicine",
                    health_status="Stable",
                    status="ACTIVE",
                    assigned_doctor_id=doc_arun.id if doc_arun else None,
                    created_by=admin_user.id if admin_user else None
                ),
                Patient(
                    id="PAT-2026-000103",
                    name="Arjun Rao",
                    age=28,
                    gender="Male",
                    dob="1998-03-15",
                    blood_group="B+",
                    contact_details="+91 97444 55566, Hyderabad",
                    department="Cardiology",
                    health_status="Discharged",
                    status="DISCHARGED",
                    assigned_doctor_id=doc_meera.id if doc_meera else None,
                    created_by=admin_user.id if admin_user else None
                ),
                Patient(
                    id="PAT-2026-000104",
                    name="Meera Nair",
                    age=61,
                    gender="Female",
                    dob="1965-11-04",
                    blood_group="AB+",
                    contact_details="+91 99888 77665, Chennai",
                    department="Cardiology",
                    health_status="Admitted",
                    status="ACTIVE",
                    assigned_doctor_id=doc_meera.id if doc_meera else None,
                    created_by=admin_user.id if admin_user else None
                )
            ]
            for p in patients:
                db.add(p)
            db.commit()

            # Seed vitals for PAT-2026-000101 recorded by Priya
            nurse = db.query(User).filter(User.username == "priya").first()
            if nurse:
                vitals = PatientVitals(
                    patient_id="PAT-2026-000101",
                    recorded_by=nurse.id,
                    blood_pressure="145/90",
                    pulse=98,
                    temperature=37.8,
                    spo2=98,
                    notes="Mild fever, blood pressure slightly elevated. Mild right sided chest pain on inspiration.",
                    timestamp=datetime.utcnow()
                )
                db.add(vitals)
                db.commit()

            # Seed lab result for PAT-2026-000101 recorded by Ananya
            lab_tech = db.query(User).filter(User.username == "ananya_lab").first()
            if lab_tech:
                labs = LabResult(
                    patient_id="PAT-2026-000101",
                    recorded_by=lab_tech.id,
                    hemoglobin=10.2,
                    wbc=14000,
                    crp="48.5 mg/L",
                    platelets=280000,
                    notes="Marked leukocytosis with elevated CRP (48.5 mg/L). Acute bacterial infection likely.",
                    timestamp=datetime.utcnow()
                )
                db.add(labs)
                db.commit()

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
