import importlib
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import app.config as config
from app.main import app


@pytest.fixture(autouse=True)
def restore_config_env():
    """Ensure app.config is restored to clean state after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
    importlib.reload(config)


# ----------------- CONFIG TESTS -----------------

def test_default_database_url_anchored_to_base_dir():
    """Verify DEFAULT_DATABASE_URL is anchored to BASE_DIR and absolute."""
    assert os.path.isabs(config.DEFAULT_SQLITE_PATH)
    assert config.DEFAULT_SQLITE_PATH.endswith("clinical_rag_v2.db")
    assert config.BASE_DIR in os.path.abspath(config.DEFAULT_SQLITE_PATH)
    assert config.DEFAULT_DATABASE_URL.startswith("sqlite:///")
    assert config.DEFAULT_DATABASE_URL.endswith("clinical_rag_v2.db")


def test_database_url_env_override():
    """Verify DATABASE_URL respects explicit environment variable override."""
    custom_url = "sqlite:////custom/path/clinical_rag_test.db"
    with patch.dict(os.environ, {"DATABASE_URL": custom_url}):
        importlib.reload(config)
        assert config.DATABASE_URL == custom_url


def test_server_host_and_port_defaults():
    """Verify HOST and PORT default to 127.0.0.1 and 8000."""
    with patch.dict(os.environ, {}, clear=True):
        importlib.reload(config)
        assert config.HOST == "127.0.0.1"
        assert config.PORT == 8000


def test_server_host_and_port_overrides():
    """Verify HOST and PORT respect environment variables."""
    with patch.dict(os.environ, {"HOST": "0.0.0.0", "PORT": "8080"}):
        importlib.reload(config)
        assert config.HOST == "0.0.0.0"
        assert config.PORT == 8080


def test_ai_key_configs_present():
    """Verify GEMINI_API_KEY and GOOGLE_API_KEY exist and respect env."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-key-123", "GOOGLE_API_KEY": "google-key-456"}):
        importlib.reload(config)
        assert config.GEMINI_API_KEY == "gemini-key-123"
        assert config.GOOGLE_API_KEY == "google-key-456"


def test_allowed_origins_custom():
    """Verify ALLOWED_ORIGINS parses comma-separated string."""
    origins_str = "https://hospital.example.com, https://app.example.com"
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins_str}):
        importlib.reload(config)
        assert config.ALLOWED_ORIGINS == ["https://hospital.example.com", "https://app.example.com"]


def test_allowed_origins_default_fallback():
    """Verify ALLOWED_ORIGINS falls back to default local ports when empty."""
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": ""}):
        importlib.reload(config)
        assert "http://localhost:5173" in config.ALLOWED_ORIGINS
        assert "http://127.0.0.1:5173" in config.ALLOWED_ORIGINS
        assert "http://localhost:3000" in config.ALLOWED_ORIGINS
        assert "http://127.0.0.1:3000" in config.ALLOWED_ORIGINS


def test_production_without_jwt_secret_raises():
    """Verify production mode strictly requires JWT_SECRET_KEY and raises RuntimeError."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET_KEY": ""}):
        with pytest.raises(RuntimeError, match="CRITICAL CONFIGURATION ERROR: JWT_SECRET_KEY"):
            importlib.reload(config)


def test_production_with_jwt_secret_succeeds():
    """Verify production mode succeeds when JWT_SECRET_KEY is provided."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET_KEY": "prod-secure-token-12345"}):
        importlib.reload(config)
        assert config.IS_PRODUCTION is True
        assert config.JWT_SECRET_KEY == "prod-secure-token-12345"


def test_development_fallback_jwt_secret():
    """Verify development mode falls back to default JWT secret without error."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development", "JWT_SECRET_KEY": ""}):
        importlib.reload(config)
        assert config.IS_PRODUCTION is False
        assert config.JWT_SECRET_KEY == "dev_insecure_jwt_secret_do_not_use_in_production"


# ----------------- HEALTH PROBE ENDPOINT TESTS -----------------

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_root_endpoint_health(client):
    """Verify GET / returns 200 OK and health payload."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Clinical RAG Hospital CDSS"


def test_health_endpoint_health(client):
    """Verify GET /health returns 200 OK and health payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Clinical RAG Hospital CDSS"


def test_api_health_endpoint_preserved(client):
    """Verify original GET /api/health endpoint is preserved and returns detailed status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Clinical RAG Hospital CDSS"
    assert "groq_api_key_configured" in data
    assert "timestamp" in data
