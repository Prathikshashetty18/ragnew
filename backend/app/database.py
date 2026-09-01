import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import DATABASE_URL

# Setup SQLAlchemy engine and session
# For SQLite, we allow multithreading access
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    role = Column(String(50), nullable=False)  # doctor, nurse, radiologist, laboratory, intern
    name = Column(String(100), nullable=False)

    assigned_patients = relationship("Patient", back_populates="assigned_doctor")

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    health_status = Column(String(100), default="Under Review")
    assigned_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assigned_doctor = relationship("User", back_populates="assigned_patients")
    vitals = relationship("PatientVitals", back_populates="patient", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")
    radiology_reports = relationship("RadiologyReport", back_populates="patient", cascade="all, delete-orphan")
    clinical_notes = relationship("ClinicalNote", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")

class PatientVitals(Base):
    __tablename__ = "patient_vitals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    blood_pressure = Column(String(50), nullable=True)
    pulse = Column(Integer, nullable=True)
    temperature = Column(Float, nullable=True)
    spo2 = Column(Integer, nullable=True)
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
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="lab_results")
    recorder = relationship("User")

class RadiologyReport(Base):
    __tablename__ = "radiology_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    findings = Column(Text, nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
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

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    file_path = Column(String(512), nullable=False)
    status = Column(String(50), default="processing")  # processing, completed, failed
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Scope metadata
    scope = Column(String(50), default="knowledge_base")  # knowledge_base, patient, temporary
    patient_id = Column(String(50), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploader_role = Column(String(50), nullable=True)
    document_type = Column(String(100), nullable=True)  # blood_report, radiology_report, nursing_report, medical_history, other

    patient = relationship("Patient", back_populates="documents")
    uploader = relationship("User")

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

# Database initialization helper
def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed fictional demo users and patients if table is empty
    db = SessionLocal()
    try:
        # Check if users are empty
        if db.query(User).count() == 0:
            print("Seeding database with fictional demo users...")
            users = [
                User(id=1, username="arun", role="doctor", name="Dr. Arun"),
                User(id=2, username="meera", role="doctor", name="Dr. Meera"),
                User(id=3, username="priya", role="nurse", name="Priya"),
                User(id=4, username="rahul_rad", role="radiologist", name="Rahul"),
                User(id=5, username="ananya_lab", role="laboratory", name="Ananya"),
                User(id=6, username="arjun_intern", role="intern", name="Arjun"),
            ]
            for u in users:
                db.add(u)
            db.commit()

        # Check if patients are empty
        if db.query(Patient).count() == 0:
            print("Seeding database with fictional patients...")
            patients = [
                Patient(id="P001", name="Rahul", age=45, gender="M", health_status="Under Review", assigned_doctor_id=1),
                Patient(id="P002", name="Ananya", age=32, gender="F", health_status="Stable", assigned_doctor_id=1),
                Patient(id="P003", name="Arjun", age=28, gender="M", health_status="Discharged", assigned_doctor_id=2),
                Patient(id="P004", name="Meera", age=61, gender="F", health_status="Admitted", assigned_doctor_id=2),
            ]
            for p in patients:
                db.add(p)
            db.commit()
            
            # Initial vitals for P001 recorded by Priya (nurse, user id 3)
            if db.query(PatientVitals).count() == 0:
                vitals = PatientVitals(
                    patient_id="P001",
                    recorded_by=3,
                    blood_pressure="145/90",
                    pulse=98,
                    temperature=37.8,
                    spo2=98,
                    notes="Mild fever, blood pressure slightly elevated.",
                    timestamp=datetime.utcnow()
                )
                db.add(vitals)
                db.commit()
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
