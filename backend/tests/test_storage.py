"""
Unit and integration tests for the persistent storage abstraction layer.
Validates:
- LocalStorageProvider operations and path normalization
- S3StorageProvider with mocked S3 client
- Path traversal rejection and filename sanitization
- In-memory PDF structure validation (BytesIO and bytes)
- Streaming file downloads via GET /api/documents/{id}/file
- Patient isolation enforcement on file downloads
- Physical file deletion and archive preservation semantics
"""

import io
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import UPLOAD_DIR
from app.database import Base, User, Patient, Document, get_db
from app.auth import hash_password, create_access_token
from app.document_validator import validate_pdf_structure
from app.storage import (
    LocalStorageProvider,
    S3StorageProvider,
    StorageError,
    StorageFileNotFoundError,
    sanitize_filename,
    get_storage,
    reset_storage
)
from app.main import app

# ----------------- 1. SANITIZATION & NORMALIZATION -----------------

def test_sanitize_filename_standard():
    assert sanitize_filename("Hospital_Guideline.pdf") == "Hospital_Guideline.pdf"
    assert sanitize_filename("documents/Hospital_Guideline.pdf") == "Hospital_Guideline.pdf"


def test_sanitize_filename_windows_path():
    win_path = r"C:\Users\test\backend\uploads\clinical_report.txt"
    assert sanitize_filename(win_path) == "clinical_report.txt"


def test_sanitize_filename_traversal_rejection():
    with pytest.raises(ValueError):
        sanitize_filename("..")
    with pytest.raises(ValueError):
        sanitize_filename("")
    with pytest.raises(ValueError):
        sanitize_filename("doc\x00test.pdf")


# ----------------- 2. LOCAL STORAGE PROVIDER -----------------

def test_local_storage_crud(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))
    content = b"Sample clinical report text content for local storage test."

    # 1. Upload bytes
    target = provider.upload("test_report.txt", content, content_type="text/plain")
    assert os.path.exists(target)

    # 2. Exists
    assert provider.exists("test_report.txt") is True
    assert provider.exists("documents/test_report.txt") is True
    assert provider.exists("nonexistent.txt") is False

    # 3. Get stream
    stream, media_type, size = provider.get_stream("test_report.txt")
    assert media_type == "text/plain"
    assert size == len(content)
    assert stream.read() == content

    # 4. Upload BytesIO
    bio = io.BytesIO(b"%PDF-1.4 header dummy data")
    target_pdf = provider.upload("dummy.pdf", bio, content_type="application/pdf")
    assert os.path.exists(target_pdf)

    # 5. Normalize key
    assert provider.normalize_key(target) == "documents/test_report.txt"

    # 6. Delete
    assert provider.delete("test_report.txt") is True
    assert provider.exists("test_report.txt") is False


def test_local_storage_not_found(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))
    with pytest.raises(StorageFileNotFoundError):
        provider.get_stream("missing_file.pdf")


# ----------------- 3. S3 / BACKBLAZE B2 STORAGE PROVIDER (MOCKED) -----------------

def test_s3_storage_crud_mocked():
    mock_s3 = MagicMock()
    provider = S3StorageProvider(
        bucket_name="clinical-rag-cdss-storage",
        endpoint_url="https://s3.us-east-005.backblazeb2.com",
        access_key_id="fake_key",
        secret_access_key="fake_secret",
        region_name="us-east-005",
        s3_client=mock_s3
    )

    # 1. Upload
    content = b"%PDF-1.4 test document body"
    key = provider.upload("guideline.pdf", content, content_type="application/pdf")
    assert key == "documents/guideline.pdf"
    mock_s3.put_object.assert_called_once_with(
        Bucket="clinical-rag-cdss-storage",
        Key="documents/guideline.pdf",
        Body=content,
        ContentType="application/pdf"
    )

    # 2. Exists
    mock_s3.head_object.return_value = {"ContentLength": len(content)}
    assert provider.exists("guideline.pdf") is True
    mock_s3.head_object.assert_called_with(
        Bucket="clinical-rag-cdss-storage",
        Key="documents/guideline.pdf"
    )

    # 3. Get stream
    mock_body = MagicMock()
    mock_body.read.return_value = content
    mock_s3.get_object.return_value = {
        "Body": mock_body,
        "ContentType": "application/pdf",
        "ContentLength": len(content)
    }

    stream, media_type, size = provider.get_stream("guideline.pdf")
    assert media_type == "application/pdf"
    assert size == len(content)
    assert stream.read() == content

    # 4. Delete
    assert provider.delete("guideline.pdf") is True
    mock_s3.delete_object.assert_called_once_with(
        Bucket="clinical-rag-cdss-storage",
        Key="documents/guideline.pdf"
    )


def test_s3_storage_not_found_mocked():
    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
        "GetObject"
    )
    provider = S3StorageProvider(
        bucket_name="clinical-rag-cdss-storage",
        endpoint_url="https://s3.us-east-005.backblazeb2.com",
        access_key_id="k",
        secret_access_key="s",
        region_name="us-east-005",
        s3_client=mock_s3
    )

    with pytest.raises(StorageFileNotFoundError):
        provider.get_stream("absent.pdf")


def test_s3_storage_client_initialization_with_b2_params():
    """Verify that S3StorageProvider initializes boto3.client with Backblaze B2 endpoint, region, and s3v4 config."""
    with patch("boto3.client") as mock_boto3:
        provider = S3StorageProvider(
            bucket_name="clinical-rag-cdss-storage",
            endpoint_url="https://s3.us-east-005.backblazeb2.com",
            access_key_id="test_key_id",
            secret_access_key="test_secret_key",
            region_name="us-east-005"
        )
        mock_boto3.assert_called_once()
        args, kwargs = mock_boto3.call_args
        assert args[0] == "s3"
        assert kwargs["endpoint_url"] == "https://s3.us-east-005.backblazeb2.com"
        assert kwargs["region_name"] == "us-east-005"
        assert kwargs["aws_access_key_id"] == "test_key_id"
        assert kwargs["aws_secret_access_key"] == "test_secret_key"
        assert kwargs["config"].signature_version == "s3v4"


def test_s3_storage_missing_config_raises():
    """Verify that ValueError is raised if required S3 parameters are missing."""
    with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
        S3StorageProvider(bucket_name="", endpoint_url="https://s3.us-east-005.backblazeb2.com", access_key_id="k", secret_access_key="s")

    with pytest.raises(ValueError, match="S3_ENDPOINT_URL"):
        S3StorageProvider(bucket_name="b", endpoint_url="", access_key_id="k", secret_access_key="s")

    with pytest.raises(ValueError, match="S3_ACCESS_KEY_ID"):
        S3StorageProvider(bucket_name="b", endpoint_url="https://s3.us-east-005.backblazeb2.com", access_key_id="", secret_access_key="s")


def test_safe_storage_config_redacts_credentials():
    """Verify get_safe_storage_config never leaks S3 keys."""
    from app.config import get_safe_storage_config
    cfg = get_safe_storage_config()
    assert "access_key_id" not in cfg
    assert "secret_access_key" not in cfg
    assert isinstance(cfg.get("access_key_set"), bool)
    assert isinstance(cfg.get("secret_key_set"), bool)


# ----------------- 4. IN-MEMORY PDF VALIDATION -----------------

def test_validate_pdf_structure_bytes_io():
    # Valid minimal PDF
    minimal_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    )
    bio = io.BytesIO(minimal_pdf)
    valid, msg, pages, txt = validate_pdf_structure(bio)
    # Even if selectable text is under 50 chars, header and structure validation works without disk access
    assert "Invalid file format" not in msg

    # Invalid header
    invalid_bio = io.BytesIO(b"Not a real PDF stream")
    valid_inv, msg_inv, _, _ = validate_pdf_structure(invalid_bio)
    assert valid_inv is False
    assert "Missing standard PDF header signature" in msg_inv


# ----------------- 5. TEST CLIENT FIXTURES -----------------

@pytest.fixture
def storage_test_db(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    # Seed users
    admin = User(
        id=1, username="test_admin", password_hash=hash_password("admin123"),
        role="ADMIN", name="Dr. Admin", email="admin@test.org", status="ACTIVE"
    )
    doctor_assigned = User(
        id=2, username="test_doc_assigned", password_hash=hash_password("doc123"),
        role="DOCTOR", name="Dr. Primary", email="primary@test.org", status="ACTIVE"
    )
    doctor_unassigned = User(
        id=3, username="test_doc_unassigned", password_hash=hash_password("doc123"),
        role="DOCTOR", name="Dr. Unassigned", email="unassigned@test.org", status="ACTIVE"
    )
    db.add_all([admin, doctor_assigned, doctor_unassigned])

    # Seed patient
    patient = Patient(
        id="PAT-STORAGE-001", name="Test Patient", age=45, gender="Male",
        department="General Medicine", health_status="Stable", status="ACTIVE",
        assigned_doctor_id=doctor_assigned.id
    )
    db.add(patient)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield db, TestingSession, tmp_path

    app.dependency_overrides.clear()
    db.close()


# ----------------- 6. STREAMING FILE DOWNLOAD & RBAC -----------------

def test_streaming_download_and_patient_isolation(storage_test_db):
    db, _, tmp_path = storage_test_db
    client = TestClient(app)

    # Set up local storage provider in temp dir
    test_provider = LocalStorageProvider(upload_dir=str(tmp_path))
    content = b"%PDF-1.4 clinical lab report dummy binary content for streaming test"
    file_path = test_provider.upload("patient_report.pdf", content, content_type="application/pdf")

    # Create patient-scoped Document record
    doc = Document(
        name="patient_report.pdf",
        file_path=file_path,
        status="completed",
        approval_status="ACTIVE",
        version="1.0",
        scope="patient",
        patient_id="PAT-STORAGE-001"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    with patch("app.main.get_storage", return_value=test_provider):
        # 1. Assigned doctor accesses -> 200 OK with StreamingResponse headers
        assigned_token = create_access_token({"sub": "test_doc_assigned", "role": "DOCTOR"})
        res_assigned = client.get(
            f"/api/documents/{doc.id}/file",
            headers={"Authorization": f"Bearer {assigned_token}"}
        )
        assert res_assigned.status_code == 200
        assert res_assigned.headers["content-type"] == "application/pdf"
        assert res_assigned.headers["content-length"] == str(len(content))
        assert 'inline; filename="patient_report.pdf"' in res_assigned.headers["content-disposition"]
        assert res_assigned.content == content

        # 2. Unassigned doctor accesses -> 403 Forbidden (Patient isolation enforced)
        unassigned_token = create_access_token({"sub": "test_doc_unassigned", "role": "DOCTOR"})
        res_unassigned = client.get(
            f"/api/documents/{doc.id}/file",
            headers={"Authorization": f"Bearer {unassigned_token}"}
        )
        assert res_unassigned.status_code == 403

        # 3. Admin accesses -> 200 OK (Superuser override)
        admin_token = create_access_token({"sub": "test_admin", "role": "ADMIN"})
        res_admin = client.get(
            f"/api/documents/{doc.id}/file",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_admin.status_code == 200
        assert res_admin.content == content


# ----------------- 7. DELETION & ARCHIVE SEMANTICS -----------------

def test_delete_document_removes_physical_storage(storage_test_db):
    db, _, tmp_path = storage_test_db
    client = TestClient(app)

    test_provider = LocalStorageProvider(upload_dir=str(tmp_path))
    content = b"content to be deleted"
    file_path = test_provider.upload("to_delete.txt", content, content_type="text/plain")
    assert os.path.exists(file_path)

    doc = Document(
        name="to_delete.txt",
        file_path=file_path,
        status="completed",
        approval_status="ACTIVE",
        scope="knowledge_base"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    with patch("app.main.get_storage", return_value=test_provider), \
         patch("app.main.remove_document_from_vector_store"):
        admin_token = create_access_token({"sub": "test_admin", "role": "ADMIN"})
        res = client.delete(
            f"/api/documents/{doc.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 200

        # Physical file should be deleted from storage
        assert test_provider.exists("to_delete.txt") is False


def test_archive_document_preserves_physical_storage(storage_test_db):
    db, _, tmp_path = storage_test_db
    client = TestClient(app)

    test_provider = LocalStorageProvider(upload_dir=str(tmp_path))
    content = b"content that should be archived and preserved"
    file_path = test_provider.upload("to_archive.txt", content, content_type="text/plain")
    assert os.path.exists(file_path)

    doc = Document(
        name="to_archive.txt",
        file_path=file_path,
        status="completed",
        approval_status="ACTIVE",
        scope="knowledge_base"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    with patch("app.main.get_storage", return_value=test_provider), \
         patch("app.main.remove_document_from_vector_store") as mock_remove:
        admin_token = create_access_token({"sub": "test_admin", "role": "ADMIN"})
        res = client.post(
            f"/api/documents/{doc.id}/archive",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 200

        # Chunks removed from vector retrieval
        mock_remove.assert_called_once_with(doc.id)

        # But physical storage object is preserved!
        assert test_provider.exists("to_archive.txt") is True


# ----------------- 8. DETERMINISTIC S3 KEY RESOLUTION (LEGACY HEX PREFIX) -----------------

@pytest.fixture
def mock_s3_key_resolution_provider():
    mock_s3 = MagicMock()
    provider = S3StorageProvider(
        bucket_name="clinical-rag-cdss-storage",
        endpoint_url="https://s3.us-east-005.backblazeb2.com",
        access_key_id="fake_key",
        secret_access_key="fake_secret",
        region_name="us-east-005",
        s3_client=mock_s3
    )
    return provider, mock_s3


def test_s3_key_resolution_pattern_matching():
    """Verify that get_canonical_key_candidate strictly matches 8-hex prefix followed by underscore."""
    provider = S3StorageProvider(
        bucket_name="b", endpoint_url="https://s3.us-east-005.backblazeb2.com",
        access_key_id="k", secret_access_key="s", s3_client=MagicMock()
    )
    # Valid matches
    assert provider.get_canonical_key_candidate("7ca67fea_hospital_guideline.pdf") == "documents/hospital_guideline.pdf"
    assert provider.get_canonical_key_candidate("documents/179b69ea_cardio.pdf") == "documents/cardio.pdf"
    assert provider.get_canonical_key_candidate(r"C:\uploads\ca6bf9ec_image.png") == "documents/image.png"
    assert provider.get_canonical_key_candidate("f26313af_pitch.pdf") == "documents/pitch.pdf"
    assert provider.get_canonical_key_candidate("1234ABCD_doc.pdf") == "documents/doc.pdf"

    # Non-matches (should return None)
    assert provider.get_canonical_key_candidate("hospital_guideline.pdf") is None
    assert provider.get_canonical_key_candidate("1234567_tooshort.pdf") is None
    assert provider.get_canonical_key_candidate("123456789_toolong.pdf") is None
    assert provider.get_canonical_key_candidate("zzzzzzzz_nothex.pdf") is None
    assert provider.get_canonical_key_candidate("temp_7ca67fea_file.pdf") is None
    assert provider.get_canonical_key_candidate("7ca67fea_") is None
    assert provider.get_canonical_key_candidate("7ca67fea_.") is None


def test_s3_key_resolution_case_a_canonical_exists(mock_s3_key_resolution_provider):
    """Test Case A: Canonical key exists -> canonical key returned/used."""
    provider, mock_s3 = mock_s3_key_resolution_provider
    canonical_key = "documents/hospital_guideline_cardio_2026.pdf"

    mock_s3.head_object.return_value = {"ContentLength": 100}
    mock_body = MagicMock()
    mock_body.read.return_value = b"canonical content"
    mock_s3.get_object.return_value = {"Body": mock_body, "ContentLength": 17, "ContentType": "application/pdf"}

    # exists()
    assert provider.exists(canonical_key) is True
    mock_s3.head_object.assert_called_with(Bucket=provider.bucket_name, Key=canonical_key)

    # get_stream()
    stream, media_type, size = provider.get_stream(canonical_key)
    assert stream.read() == b"canonical content"
    mock_s3.get_object.assert_called_with(Bucket=provider.bucket_name, Key=canonical_key)

    # resolve_storage_key()
    resolved = provider.resolve_storage_key(canonical_key)
    assert resolved == canonical_key


def test_s3_key_resolution_case_b_legacy_prefixed_canonical_exists(mock_s3_key_resolution_provider):
    """Test Case B: Legacy-prefixed key requested, canonical key exists -> canonical key resolved."""
    provider, mock_s3 = mock_s3_key_resolution_provider
    legacy_key = "documents/7ca67fea_hospital_guideline_cardio_2026.pdf"
    canonical_key = "documents/hospital_guideline_cardio_2026.pdf"

    # Exact key throws NoSuchKey, canonical key succeeds
    def mock_head_side_effect(**kwargs):
        if kwargs.get("Key") == legacy_key:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        if kwargs.get("Key") == canonical_key:
            return {"ContentLength": 200}
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")

    def mock_get_side_effect(**kwargs):
        if kwargs.get("Key") == legacy_key:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        if kwargs.get("Key") == canonical_key:
            mock_body = MagicMock()
            mock_body.read.return_value = b"canonical guideline content"
            return {"Body": mock_body, "ContentLength": 27, "ContentType": "application/pdf"}
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    mock_s3.head_object.side_effect = mock_head_side_effect
    mock_s3.get_object.side_effect = mock_get_side_effect

    # exists() resolves to True via candidate
    assert provider.exists(legacy_key) is True

    # get_stream() falls back to canonical key and reads content
    stream, media_type, size = provider.get_stream(legacy_key)
    assert stream.read() == b"canonical guideline content"

    # resolve_storage_key returns canonical key
    assert provider.resolve_storage_key(legacy_key) == canonical_key


def test_s3_key_resolution_case_c_legacy_prefixed_exact_takes_precedence(mock_s3_key_resolution_provider):
    """Test Case C: Legacy-prefixed key exists -> exact legacy key takes precedence."""
    provider, mock_s3 = mock_s3_key_resolution_provider
    legacy_key = "documents/7ca67fea_hospital_guideline_cardio_2026.pdf"
    canonical_key = "documents/hospital_guideline_cardio_2026.pdf"

    # Both keys exist in S3, with different content
    mock_s3.head_object.return_value = {"ContentLength": 50}

    def mock_get_side_effect(**kwargs):
        mock_body = MagicMock()
        if kwargs.get("Key") == legacy_key:
            mock_body.read.return_value = b"exact legacy content"
            return {"Body": mock_body, "ContentLength": 20, "ContentType": "application/pdf"}
        else:
            mock_body.read.return_value = b"canonical content"
            return {"Body": mock_body, "ContentLength": 17, "ContentType": "application/pdf"}

    mock_s3.get_object.side_effect = mock_get_side_effect

    # get_stream() must return exact legacy content
    stream, media_type, size = provider.get_stream(legacy_key)
    assert stream.read() == b"exact legacy content"
    mock_s3.get_object.assert_called_once_with(Bucket=provider.bucket_name, Key=legacy_key)

    # resolve_storage_key must return exact legacy key
    assert provider.resolve_storage_key(legacy_key) == legacy_key


def test_s3_key_resolution_case_d_non_matching_pattern_no_stripping(mock_s3_key_resolution_provider):
    """Test Case D: Filename does not match 8-hex-prefix pattern -> no stripping occurs."""
    provider, mock_s3 = mock_s3_key_resolution_provider
    key = "documents/zzzzzzzz_guideline.pdf"

    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
    mock_s3.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    # exists() makes only 1 call and returns False
    assert provider.exists(key) is False
    mock_s3.head_object.assert_called_once_with(Bucket=provider.bucket_name, Key=key)

    # get_stream() makes only 1 call and raises StorageFileNotFoundError
    with pytest.raises(StorageFileNotFoundError) as exc:
        provider.get_stream(key)
    assert "zzzzzzzz_guideline.pdf" in str(exc.value)
    mock_s3.get_object.assert_called_once_with(Bucket=provider.bucket_name, Key=key)

    # resolve_storage_key returns exact key without calling S3
    mock_s3.head_object.reset_mock()
    assert provider.resolve_storage_key(key) == key
    mock_s3.head_object.assert_not_called()


def test_s3_key_resolution_case_e_both_not_found(mock_s3_key_resolution_provider):
    """Test Case E: Both exact and canonical keys do not exist -> existing not-found behavior."""
    provider, mock_s3 = mock_s3_key_resolution_provider
    legacy_key = "documents/7ca67fea_nonexistent.pdf"

    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
    mock_s3.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    assert provider.exists(legacy_key) is False
    with pytest.raises(StorageFileNotFoundError) as exc:
        provider.get_stream(legacy_key)
    assert "7ca67fea_nonexistent.pdf" in str(exc.value)


def test_s3_key_resolution_case_f_delete_safety(mock_s3_key_resolution_provider):
    """Test Case F: delete() resolves the same way safely."""
    provider, mock_s3 = mock_s3_key_resolution_provider
    legacy_key = "documents/7ca67fea_hospital_guideline_cardio_2026.pdf"
    canonical_key = "documents/hospital_guideline_cardio_2026.pdf"

    # Sub-case 1: Only canonical key exists -> deletes canonical key
    def head_side_effect_1(**kwargs):
        if kwargs.get("Key") == legacy_key:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        if kwargs.get("Key") == canonical_key:
            return {"ContentLength": 100}
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")

    mock_s3.head_object.side_effect = head_side_effect_1
    assert provider.delete(legacy_key) is True
    mock_s3.delete_object.assert_called_once_with(Bucket=provider.bucket_name, Key=canonical_key)

    # Sub-case 2: Exact legacy key exists -> deletes exact legacy key only
    mock_s3.delete_object.reset_mock()
    mock_s3.head_object.side_effect = None
    mock_s3.head_object.return_value = {"ContentLength": 100}  # exact key exists
    assert provider.delete(legacy_key) is True
    mock_s3.delete_object.assert_called_once_with(Bucket=provider.bucket_name, Key=legacy_key)

    # Sub-case 3: Neither key exists -> attempts exact key, preserves idempotent return True
    mock_s3.delete_object.reset_mock()
    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
    assert provider.delete(legacy_key) is True
    mock_s3.delete_object.assert_called_once_with(Bucket=provider.bucket_name, Key=legacy_key)