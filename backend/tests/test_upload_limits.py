import io
import os
import re
import pytest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import MAX_UPLOAD_SIZE_MB, MAX_UPLOAD_SIZE_BYTES, UPLOAD_DIR
from app.database import Base, User, Patient, LabResult, RadiologyReport, Document, get_db
from app.auth import hash_password, create_access_token
from app.document_validator import check_content_length, read_upload_file_with_limit
from app.main import app

# ----------------- UNIT TESTS: read_upload_file_with_limit -----------------

@pytest.mark.anyio
async def test_read_upload_file_within_limit():
    raw_content = b"A" * 1024 * 10  # 10 KB
    upload = UploadFile(file=io.BytesIO(raw_content), filename="test.pdf")
    
    result = await read_upload_file_with_limit(upload, max_bytes=1024 * 20, chunk_size=1024)
    assert result == raw_content
    assert len(result) == 1024 * 10


@pytest.mark.anyio
async def test_read_upload_file_exact_limit():
    raw_content = b"B" * 2048
    upload = UploadFile(file=io.BytesIO(raw_content), filename="test.pdf")
    
    result = await read_upload_file_with_limit(upload, max_bytes=2048, chunk_size=512)
    assert result == raw_content
    assert len(result) == 2048


@pytest.mark.anyio
async def test_read_upload_file_exceeds_limit_raises_413():
    # 3 KB content with 2 KB limit
    raw_content = b"C" * 3072
    upload = UploadFile(file=io.BytesIO(raw_content), filename="test.pdf")
    
    with pytest.raises(HTTPException) as exc_info:
        await read_upload_file_with_limit(upload, max_bytes=2048, chunk_size=512)
        
    assert exc_info.value.status_code == 413
    assert "exceeds the maximum allowed size" in exc_info.value.detail


@pytest.mark.anyio
async def test_read_upload_file_streaming_stops_early():
    """Verify that read_upload_file_with_limit raises 413 during iteration without reading the entire stream."""
    class MockStreamFile:
        def __init__(self):
            self.read_count = 0

        def read(self, size=-1):
            self.read_count += 1
            if self.read_count > 100:
                return b""
            return b"X" * 1024  # 1 KB per chunk

    mock_file = MockStreamFile()
    mock_upload = UploadFile(file=mock_file, filename="large.pdf")
    
    # 5 KB limit with 1 KB chunks
    with pytest.raises(HTTPException) as exc_info:
        await read_upload_file_with_limit(mock_upload, max_bytes=5 * 1024, chunk_size=1024)
        
    assert exc_info.value.status_code == 413
    # Should have stopped right after reaching 6th chunk (6 KB > 5 KB), well before 100
    assert mock_file.read_count <= 7


# ----------------- UNIT TESTS: check_content_length -----------------

def test_check_content_length_valid():
    req = Request(scope={
        "type": "http",
        "headers": [(b"content-length", b"1024")]
    })
    # Should not raise
    check_content_length(req, max_bytes=2048)


def test_check_content_length_exceeded_raises_413():
    req = Request(scope={
        "type": "http",
        "headers": [(b"content-length", b"3000")]
    })
    with pytest.raises(HTTPException) as exc_info:
        check_content_length(req, max_bytes=2048)
        
    assert exc_info.value.status_code == 413
    assert "exceeds the maximum allowed size" in exc_info.value.detail


def test_check_content_length_missing_or_malformed_passes():
    # Missing header
    req_missing = Request(scope={"type": "http", "headers": []})
    check_content_length(req_missing, max_bytes=2048)  # passes to streaming check
    
    # Non-integer header
    req_bad = Request(scope={
        "type": "http",
        "headers": [(b"content-length", b"invalid_number")]
    })
    check_content_length(req_bad, max_bytes=2048)  # passes to streaming check


# ----------------- INTEGRATION TEST FIXTURES -----------------

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    admin = User(username="admin_user", password_hash=hash_password("AdminPass1!"), name="Admin User", role="ADMIN")
    doctor = User(username="doc_user", password_hash=hash_password("DocPass1!"), name="Doctor User", role="DOCTOR")
    intern = User(username="intern_user", password_hash=hash_password("InternPass1!"), name="Intern User", role="INTERN")
    radiologist = User(username="rad_user", password_hash=hash_password("RadPass1!"), name="Rad User", role="RADIOLOGIST")
    patient = Patient(id="P_TEST_99", name="Test Limit Patient", age=40, gender="Male", department="General Medicine")

    session.add_all([admin, doctor, intern, radiologist, patient])
    session.commit()
    session._SessionLocal = SessionLocal
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        db = db_session._SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_header(user: User) -> dict:
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def valid_pdf_bytes():
    seed_pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed_data", "Hospital_Guideline_Pneumonia.pdf")
    with open(seed_pdf_path, "rb") as f:
        return f.read()


# ----------------- ENDPOINT TESTS: /api/upload -----------------

def test_api_upload_unauthenticated(client):
    res = client.post("/api/upload", files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert res.status_code == 401


def test_api_upload_intern_forbidden(client, db_session):
    intern = db_session.query(User).filter(User.role == "INTERN").first()
    res = client.post(
        "/api/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=auth_header(intern)
    )
    assert res.status_code == 403
    assert "Interns do not have permission" in res.json()["detail"]


def test_api_upload_content_length_exceeded_413(client, db_session):
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    headers = auth_header(admin)
    # Advertise header larger than MAX_UPLOAD_SIZE_BYTES (25 MB)
    headers["content-length"] = str(MAX_UPLOAD_SIZE_BYTES + 1024 * 1024)

    res = client.post(
        "/api/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 small content", "application/pdf")},
        headers=headers
    )
    assert res.status_code == 413
    assert "exceeds the maximum allowed size" in res.json()["detail"]


def test_api_upload_streamed_body_exceeds_limit_413(client, db_session, monkeypatch):
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    
    # Temporarily set limit to 10 KB for fast test
    monkeypatch.setattr("app.main.MAX_UPLOAD_SIZE_BYTES", 10 * 1024)
    monkeypatch.setattr("app.main.MAX_UPLOAD_SIZE_MB", 0.01)

    # Send 15 KB
    oversized_payload = b"%PDF-1.4 " + (b"A" * 15 * 1024)
    res = client.post(
        "/api/upload",
        files={"file": ("test_oversized.pdf", oversized_payload, "application/pdf")},
        headers=auth_header(admin)
    )
    assert res.status_code == 413
    assert "exceeds the maximum allowed size" in res.json()["detail"]


def test_api_upload_invalid_extension_400(client, db_session):
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    res = client.post(
        "/api/upload",
        files={"file": ("malicious.exe", b"binarycontent", "application/octet-stream")},
        headers=auth_header(admin)
    )
    assert res.status_code == 400
    assert "Only PDF documents are supported" in res.json()["detail"]


def test_api_upload_corrupted_pdf_structure_cleaned_up(client, db_session):
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    fake_pdf = b"%PDF-corrupted-binary-content-not-valid-pdf"
    test_filename = "corrupted_test_sample.pdf"
    expected_path = os.path.join(UPLOAD_DIR, test_filename)

    # Ensure clean starting state
    if os.path.exists(expected_path):
        os.remove(expected_path)

    res = client.post(
        "/api/upload",
        files={"file": (test_filename, fake_pdf, "application/pdf")},
        headers=auth_header(admin)
    )
    assert res.status_code == 400
    assert "PDF Validation Failed" in res.json()["detail"]
    # Verify file was safely unlinked
    assert not os.path.exists(expected_path)


@patch("app.main.bg_process_pdf_task")
def test_api_upload_valid_pdf_success(mock_bg_task, client, db_session, valid_pdf_bytes):
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    filename = "valid_test_guideline.pdf"
    target_path = os.path.join(UPLOAD_DIR, filename)

    try:
        res = client.post(
            "/api/upload",
            files={"file": (filename, valid_pdf_bytes, "application/pdf")},
            data={"scope": "knowledge_base", "document_type": "Guideline"},
            headers=auth_header(admin)
        )
        assert res.status_code == 200
        assert res.json()["approval_status"] == "ACTIVE"
        mock_bg_task.assert_called_once()
    finally:
        if os.path.exists(target_path):
            os.remove(target_path)


# ----------------- ENDPOINT TESTS: /api/radiology/upload -----------------

def test_api_radiology_upload_content_length_exceeded_413(client, db_session):
    rad = db_session.query(User).filter(User.role == "RADIOLOGIST").first()
    headers = auth_header(rad)
    headers["content-length"] = str(MAX_UPLOAD_SIZE_BYTES + 5000)

    res = client.post(
        "/api/radiology/upload",
        data={"patient_id": "P_TEST_99", "findings": "Clear lung fields."},
        files={"file": ("scan.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=headers
    )
    assert res.status_code == 413


def test_api_radiology_upload_streamed_oversized_pdf_413(client, db_session, monkeypatch):
    rad = db_session.query(User).filter(User.role == "RADIOLOGIST").first()
    monkeypatch.setattr("app.main.MAX_UPLOAD_SIZE_BYTES", 5 * 1024)

    res = client.post(
        "/api/radiology/upload",
        data={"patient_id": "P_TEST_99", "findings": "Consolidation observed."},
        files={"file": ("huge_xray.pdf", b"%PDF-1.4 " + (b"Z" * 10 * 1024), "application/pdf")},
        headers=auth_header(rad)
    )
    assert res.status_code == 413


def test_api_radiology_upload_streamed_oversized_image_413(client, db_session, monkeypatch):
    rad = db_session.query(User).filter(User.role == "RADIOLOGIST").first()
    monkeypatch.setattr("app.main.MAX_UPLOAD_SIZE_BYTES", 5 * 1024)

    # Oversized non-PDF image must also be rejected by streaming size limit
    res = client.post(
        "/api/radiology/upload",
        data={"patient_id": "P_TEST_99", "findings": "Normal image."},
        files={"file": ("chest.png", b"\x89PNG\r\n\x1a\n" + (b"I" * 10 * 1024), "image/png")},
        headers=auth_header(rad)
    )
    assert res.status_code == 413


def test_api_radiology_upload_corrupted_pdf_cleaned_up(client, db_session):
    rad = db_session.query(User).filter(User.role == "RADIOLOGIST").first()
    filename = "corrupted_xray.pdf"
    target_path = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(target_path):
        os.remove(target_path)

    res = client.post(
        "/api/radiology/upload",
        data={"patient_id": "P_TEST_99", "findings": "Bilateral infiltrates."},
        files={"file": (filename, b"%PDF-invalid-structure", "application/pdf")},
        headers=auth_header(rad)
    )
    assert res.status_code == 400
    assert not os.path.exists(target_path)


def test_api_radiology_upload_valid_non_pdf_image_accepted(client, db_session):
    rad = db_session.query(User).filter(User.role == "RADIOLOGIST").first()
    filename = "valid_chest_scan.png"
    target_path = os.path.join(UPLOAD_DIR, filename)

    try:
        res = client.post(
            "/api/radiology/upload",
            data={"patient_id": "P_TEST_99", "findings": "Normal cardiac silhouette."},
            files={"file": (filename, b"\x89PNG\r\n\x1a\nsmall_valid_image", "image/png")},
            headers=auth_header(rad)
        )
        assert res.status_code == 200
        assert res.json()["patient_id"] == "P_TEST_99"
        assert res.json()["findings"] == "Normal cardiac silhouette."
    finally:
        if os.path.exists(target_path):
            os.remove(target_path)


# ----------------- ENDPOINT TESTS: /api/laboratory/upload -----------------

def test_api_laboratory_upload_oversized_attachment_413(client, db_session, monkeypatch):
    doc = db_session.query(User).filter(User.role == "DOCTOR").first()
    monkeypatch.setattr("app.main.MAX_UPLOAD_SIZE_BYTES", 5 * 1024)

    res = client.post(
        "/api/laboratory/upload",
        data={"patient_id": "P_TEST_99", "hemoglobin": "14.2", "wbc": "8.5"},
        files={"file": ("oversized_blood_work.pdf", b"%PDF-1.4 " + (b"L" * 10 * 1024), "application/pdf")},
        headers=auth_header(doc)
    )
    assert res.status_code == 413


def test_api_laboratory_upload_non_pdf_attachment_400(client, db_session):
    doc = db_session.query(User).filter(User.role == "DOCTOR").first()
    res = client.post(
        "/api/laboratory/upload",
        data={"patient_id": "P_TEST_99", "hemoglobin": "13.0"},
        files={"file": ("lab_results.csv", b"hemoglobin,13.0", "text/csv")},
        headers=auth_header(doc)
    )
    assert res.status_code == 400
    assert "Only PDF documents are supported" in res.json()["detail"]


def test_api_laboratory_transaction_atomicity_on_rejected_attachment(client, db_session):
    """
    Verify transaction atomicity:
    When attachment fails validation (e.g. invalid PDF structure),
    no orphan LabResult record must be inserted into the database.
    """
    doc = db_session.query(User).filter(User.role == "DOCTOR").first()
    filename = "broken_lab_report.pdf"
    target_path = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(target_path):
        os.remove(target_path)

    # Pre-check: count of LabResult for P_TEST_99 should be 0
    initial_count = db_session.query(LabResult).filter(LabResult.patient_id == "P_TEST_99").count()
    assert initial_count == 0

    res = client.post(
        "/api/laboratory/upload",
        data={
            "patient_id": "P_TEST_99",
            "hemoglobin": "12.5",
            "wbc": "6.0",
            "notes": "Routine CBC panel"
        },
        files={"file": (filename, b"%PDF-corrupted-lab-document-data", "application/pdf")},
        headers=auth_header(doc)
    )
    assert res.status_code == 400
    assert "PDF Validation Failed" in res.json()["detail"]

    # Post-check: ensure NO orphan LabResult was committed to the database
    post_count = db_session.query(LabResult).filter(LabResult.patient_id == "P_TEST_99").count()
    assert post_count == 0, "Regression: LabResult was committed despite attachment validation failure!"
    # Ensure temporary file unlinked
    assert not os.path.exists(target_path)


def test_api_laboratory_upload_without_file_succeeds(client, db_session):
    doc = db_session.query(User).filter(User.role == "DOCTOR").first()
    res = client.post(
        "/api/laboratory/upload",
        data={
            "patient_id": "P_TEST_99",
            "hemoglobin": "13.8",
            "wbc": "7.2",
            "platelets": "250000",
            "notes": "Normal complete blood count without document"
        },
        headers=auth_header(doc)
    )
    assert res.status_code == 200
    assert float(res.json()["hemoglobin"]) == 13.8
    assert res.json()["document_id"] is None

    # Verify committed in DB
    lab = db_session.query(LabResult).filter(LabResult.patient_id == "P_TEST_99").first()
    assert lab is not None
    assert float(lab.hemoglobin) == 13.8
