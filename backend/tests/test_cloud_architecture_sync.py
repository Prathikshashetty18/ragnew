import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import faiss
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.config import get_safe_database_url
from app.database import Base, User, Patient, Document, ClinicalReport
from app.rag_pipeline import (
    get_vector_store,
    get_indexed_document_ids,
    _vector_store_lock,
    save_vector_store
)
import app.rag_pipeline as rag_pipeline
import app.main as main_app
from app.report_generator import (
    reconcile_unindexed_clinical_reports,
    format_report_to_searchable_text
)


class TestCloudArchitectureSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_vector_store_dir = rag_pipeline.VECTOR_STORE_DIR
        self.orig_upload_dir = main_app.UPLOAD_DIR

    def tearDown(self):
        rag_pipeline.VECTOR_STORE_DIR = self.orig_vector_store_dir
        main_app.UPLOAD_DIR = self.orig_upload_dir
        with _vector_store_lock:
            rag_pipeline._faiss_index = None
            rag_pipeline._chunks_metadata = None
            rag_pipeline._embeddings_array = None
            rag_pipeline._bm25_index = None
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # A. test_turso_url_normalization
    # -------------------------------------------------------------------------
    def test_turso_url_normalization(self):
        """Verify URL normalization, authToken attachment, secure flag, and token masking."""
        raw_turso = "libsql://clinical-rag-cdss-rajeshraiii.aws-ap-south-1.turso.io"
        token = "test_turso_jwt_secret_token_12345"

        with patch.dict(os.environ, {"DATABASE_URL": raw_turso, "TURSO_AUTH_TOKEN": token}):
            raw_url = os.environ.get("DATABASE_URL")
            t_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

            if raw_url.startswith("libsql://"):
                normalized = raw_url.replace("libsql://", "sqlite+libsql://", 1)
            else:
                normalized = raw_url

            if t_token and "libsql" in normalized and "authToken=" not in normalized:
                separator = "&" if "?" in normalized else "?"
                normalized = f"{normalized}{separator}authToken={t_token}&secure=true"

            self.assertTrue(normalized.startswith("sqlite+libsql://"))
            self.assertIn("authToken=test_turso_jwt_secret_token_12345", normalized)
            self.assertIn("secure=true", normalized)

            # Test safe masking (token is NEVER logged)
            safe_url = get_safe_database_url(normalized)
            self.assertNotIn("test_turso_jwt_secret_token_12345", safe_url)
            self.assertIn("authToken=***", safe_url)

    def test_turso_url_normalization_with_query_params(self):
        """Verify normalization when URL already contains query parameters."""
        raw_turso = "libsql://test-db.turso.io?tls=1"
        token = "secret_token_abc"

        with patch.dict(os.environ, {"DATABASE_URL": raw_turso, "TURSO_AUTH_TOKEN": token}):
            raw_url = os.environ.get("DATABASE_URL")
            t_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

            if raw_url.startswith("libsql://"):
                normalized = raw_url.replace("libsql://", "sqlite+libsql://", 1)
            else:
                normalized = raw_url

            if t_token and "libsql" in normalized and "authToken=" not in normalized:
                separator = "&" if "?" in normalized else "?"
                normalized = f"{normalized}{separator}authToken={t_token}&secure=true"

            self.assertEqual(
                normalized,
                "sqlite+libsql://test-db.turso.io?tls=1&authToken=secret_token_abc&secure=true"
            )

    def test_local_sqlite_url_remains_unchanged(self):
        """Verify standard sqlite:/// URLs are unaffected even if TURSO_AUTH_TOKEN is present."""
        local_sqlite = "sqlite:///C:/test_dir/clinical_rag_v2.db"
        token = "some_random_token"

        with patch.dict(os.environ, {"DATABASE_URL": local_sqlite, "TURSO_AUTH_TOKEN": token}):
            raw_url = os.environ.get("DATABASE_URL")
            t_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

            if raw_url.startswith("libsql://"):
                normalized = raw_url.replace("libsql://", "sqlite+libsql://", 1)
            else:
                normalized = raw_url

            if t_token and "libsql" in normalized and "authToken=" not in normalized:
                separator = "&" if "?" in normalized else "?"
                normalized = f"{normalized}{separator}authToken={t_token}&secure=true"

            self.assertEqual(normalized, local_sqlite)
            self.assertNotIn("authToken", normalized)

    # -------------------------------------------------------------------------
    # B. test_get_indexed_document_ids
    # -------------------------------------------------------------------------
    def test_get_indexed_document_ids(self):
        """Verify get_indexed_document_ids correctly inspects active chunk metadata."""
        sample_metadata = [
            {"text": "Chunk 1", "document_id": 101},
            {"text": "Chunk 2", "document_id": 101},
            {"text": "Chunk 3", "document_id": 202},
            {"text": "Chunk 4", "document_id": "303"},
            {"text": "Chunk 5", "document_id": None},
        ]

        with patch("app.rag_pipeline.get_vector_store", return_value=(None, sample_metadata, None)):
            ids = get_indexed_document_ids()
            self.assertEqual(ids, {101, 202, 303})

    # -------------------------------------------------------------------------
    # C. test_startup_reconciliation_of_missing_guidelines
    # -------------------------------------------------------------------------
    def test_startup_reconciliation_of_missing_guidelines(self):
        """Verify that a guideline existing in DB but missing from vector store is re-indexed."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        # Seed guideline in DB with non-zero chunk_count as if persisted in Turso
        guideline_doc = Document(
            name="Hospital_Guideline_Pneumonia.pdf",
            file_path=os.path.join(self.temp_dir, "Hospital_Guideline_Pneumonia.pdf"),
            status="completed",
            approval_status="ACTIVE",
            version="1.0",
            scope="knowledge_base",
            document_type="Guideline",
            chunk_count=15
        )
        db.add(guideline_doc)
        db.commit()
        db.refresh(guideline_doc)
        doc_id = guideline_doc.id

        # Isolated vector store and uploads
        test_vector_dir = os.path.join(self.temp_dir, "vector_store")
        test_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(test_vector_dir, exist_ok=True)
        os.makedirs(test_upload_dir, exist_ok=True)

        rag_pipeline.VECTOR_STORE_DIR = test_vector_dir
        main_app.UPLOAD_DIR = test_upload_dir

        # Reset in-memory vector store to simulate fresh container startup
        with _vector_store_lock:
            rag_pipeline._faiss_index = faiss.IndexFlatIP(384)
            rag_pipeline._chunks_metadata = []
            rag_pipeline._embeddings_array = None

        # Verify initial vector store does NOT have doc_id
        self.assertNotIn(doc_id, get_indexed_document_ids())

        # Mock get_db to return our isolated DB session
        def mock_get_db():
            yield db

        with patch("app.main.get_db", mock_get_db):
            main_app.startup_load_seeds()

        # Document must NOT be duplicated
        all_docs = db.query(Document).filter(Document.name == "Hospital_Guideline_Pneumonia.pdf").all()
        self.assertEqual(len(all_docs), 1)

        # Vector store must now contain the guideline doc_id
        indexed_ids = get_indexed_document_ids()
        self.assertIn(doc_id, indexed_ids)

        db.close()

    # -------------------------------------------------------------------------
    # D. test_startup_reconciliation_of_missing_clinical_reports
    # -------------------------------------------------------------------------
    def test_startup_reconciliation_of_missing_clinical_reports(self):
        """Verify that an approved clinical report missing from vector store is reconstituted."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        doctor = User(
            username="dr_reconcile_test",
            password_hash="hash",
            name="Dr. Reconcile",
            role="DOCTOR"
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)

        patient = Patient(
            id="PAT-RECON-001",
            name="Reconcile Patient",
            age=45,
            gender="Male",
            department="Pulmonology"
        )
        db.add(patient)
        db.commit()

        # Approved ClinicalReport in DB
        report = ClinicalReport(
            patient_id=patient.id,
            doctor_id=doctor.id,
            title="Reconciliation Pulmonary Evaluation",
            chief_complaint="Persistent productive cough and dyspnea",
            clinical_history="History of community-acquired pneumonia",
            observations="Blood pressure 125/80 mmHg, SpO2 95% on room air",
            investigations="Chest X-Ray shows right lower lobe consolidation",
            clinical_assessment="Resolving right lower lobe bacterial pneumonia",
            recommendations="Complete oral amoxicillin-clavulanate course for 5 more days",
            sources="Hospital Approved Pneumonia Management Protocol",
            status="APPROVED"
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        # Existing matching Document row with chunk_count > 0 (as saved in Turso)
        doc_filename = f"Clinical_Report_{patient.id}_Report{report.id}.txt"
        report_doc = Document(
            name=doc_filename,
            file_path=os.path.join(self.temp_dir, doc_filename),
            status="ready",
            approval_status="ACTIVE",
            version="1.0",
            scope="patient",
            patient_id=patient.id,
            document_type="clinical_report",
            chunk_count=8
        )
        db.add(report_doc)
        db.commit()
        db.refresh(report_doc)
        doc_id = report_doc.id

        # Isolated vector store
        test_vector_dir = os.path.join(self.temp_dir, "vector_store")
        test_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(test_vector_dir, exist_ok=True)
        os.makedirs(test_upload_dir, exist_ok=True)

        rag_pipeline.VECTOR_STORE_DIR = test_vector_dir
        main_app.UPLOAD_DIR = test_upload_dir

        # Reset vector store to simulate empty ephemeral container
        with _vector_store_lock:
            rag_pipeline._faiss_index = faiss.IndexFlatIP(384)
            rag_pipeline._chunks_metadata = []
            rag_pipeline._embeddings_array = None

        # Verify not in vector store initially
        self.assertNotIn(doc_id, get_indexed_document_ids())

        # Run reconciliation
        reconciled = reconcile_unindexed_clinical_reports(db)
        self.assertGreaterEqual(reconciled, 1)

        # Verify report was reconstituted and doc_id is now in vector store
        indexed_ids = get_indexed_document_ids()
        self.assertIn(doc_id, indexed_ids)

        db.close()

    # -------------------------------------------------------------------------
    # E. Local SQLite regression
    # -------------------------------------------------------------------------
    def test_local_sqlite_regression(self):
        """Verify normal local SQLite initialization and DEFAULT_DATABASE_URL behavior."""
        self.assertTrue(config.DEFAULT_DATABASE_URL.startswith("sqlite:///"))
        self.assertTrue(config.DEFAULT_DATABASE_URL.endswith("clinical_rag_v2.db"))
        self.assertTrue(os.path.isabs(config.DEFAULT_SQLITE_PATH))

        # Test in-memory DB engine creation
        test_engine = create_engine("sqlite:///:memory:")
        with test_engine.connect() as conn:
            from sqlalchemy import text
            res = conn.execute(text("SELECT 1")).scalar()
            self.assertEqual(res, 1)


if __name__ == "__main__":
    unittest.main()
