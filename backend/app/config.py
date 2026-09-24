import os
import re
from typing import Optional
from dotenv import load_dotenv

# App Directory Configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables: explicitly load backend/.env first, then fallback
_backend_env = os.path.join(BASE_DIR, ".env")
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
load_dotenv()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
VECTOR_STORE_DIR = os.environ.get("VECTOR_STORE_DIR", os.path.join(BASE_DIR, "vector_store"))
SEED_DIR = os.environ.get("SEED_DIR", os.path.join(BASE_DIR, "seed_data"))

# Ensure paths exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
os.makedirs(SEED_DIR, exist_ok=True)

# Upload File Size Configuration
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "25"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Database Configurations
DEFAULT_SQLITE_PATH = os.path.normpath(os.path.join(BASE_DIR, "clinical_rag_v2.db")).replace("\\", "/")
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"

_raw_env_url = os.environ.get("DATABASE_URL", "").strip()
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

if not _raw_env_url:
    _raw_database_url = TURSO_DATABASE_URL or DEFAULT_DATABASE_URL
elif _raw_env_url.startswith("sqlite:///"):
    _sqlite_sub = _raw_env_url[len("sqlite:///"):].strip()
    _is_special = not _sqlite_sub or _sqlite_sub == ":memory:"
    _is_posix_abs = _sqlite_sub.startswith("/") or _sqlite_sub.startswith("\\")
    _is_win_abs = len(_sqlite_sub) >= 2 and _sqlite_sub[1] == ":"
    if not (_is_special or _is_posix_abs or _is_win_abs):
        # Anchor relative SQLite path to BASE_DIR (backend/)
        _anchored = os.path.normpath(os.path.join(BASE_DIR, _sqlite_sub)).replace("\\", "/")
        _raw_database_url = f"sqlite:///{_anchored}"
    else:
        _raw_database_url = _raw_env_url
else:
    _raw_database_url = _raw_env_url

# Normalize libSQL / Turso connection URL if provided
if _raw_database_url.startswith("libsql://"):
    DATABASE_URL = _raw_database_url.replace("libsql://", "sqlite+libsql://", 1)
else:
    DATABASE_URL = _raw_database_url

# Ensure Turso libSQL URLs have secure=true query param if applicable
if "libsql" in DATABASE_URL and "secure=" not in DATABASE_URL:
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{separator}secure=true"

def get_safe_database_url(url: Optional[str] = None) -> str:
    """Returns database URL with sensitive auth tokens redacted for safe logging."""
    target = url or DATABASE_URL
    if "authToken=" in target:
        return re.sub(r'authToken=[^&]+', 'authToken=***', target)
    return target

# Storage Configurations
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").lower()
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "").strip()
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", os.environ.get("R2_BUCKET_NAME", "")).strip()
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", os.environ.get("R2_ACCESS_KEY_ID", "")).strip()
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", os.environ.get("R2_SECRET_ACCESS_KEY", "")).strip()
S3_REGION = os.environ.get("S3_REGION", "").strip()

# Infer region from S3_ENDPOINT_URL if not explicitly set (e.g. https://s3.us-east-005.backblazeb2.com -> us-east-005)
if not S3_REGION and S3_ENDPOINT_URL:
    b2_match = re.search(r's3\.([a-z0-9-]+)\.backblazeb2\.com', S3_ENDPOINT_URL)
    if b2_match:
        S3_REGION = b2_match.group(1)
    else:
        aws_match = re.search(r's3[.-]([a-z0-9-]+)\.amazonaws\.com', S3_ENDPOINT_URL)
        if aws_match:
            S3_REGION = aws_match.group(1)
if not S3_REGION:
    S3_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Backward compatibility alias for Cloudflare R2 if S3_ENDPOINT_URL was not set
if not S3_ENDPOINT_URL and os.environ.get("R2_ACCOUNT_ID"):
    S3_ENDPOINT_URL = f"https://{os.environ.get('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
    S3_REGION = "auto"

def get_safe_storage_config() -> dict:
    """Returns storage configuration with credentials redacted for safe logging."""
    return {
        "backend": STORAGE_BACKEND,
        "bucket": S3_BUCKET_NAME if STORAGE_BACKEND == "s3" else "N/A (local)",
        "endpoint": S3_ENDPOINT_URL if STORAGE_BACKEND == "s3" else "N/A (local)",
        "region": S3_REGION if STORAGE_BACKEND == "s3" else "N/A (local)",
        "access_key_set": bool(S3_ACCESS_KEY_ID),
        "secret_key_set": bool(S3_SECRET_ACCESS_KEY),
    }

# Server Network Configuration (Defaults for deployment / CLI)
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

# Environment Mode & Origins
ENVIRONMENT = os.environ.get("ENVIRONMENT", os.environ.get("APP_ENV", "development")).lower()
IS_PRODUCTION = ENVIRONMENT in ["production", "prod"]

raw_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "")
if raw_allowed_origins.strip():
    ALLOWED_ORIGINS = [orig.strip() for orig in raw_allowed_origins.split(",") if orig.strip()]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Security & JWT Configurations
CDSS_API_KEY = os.environ.get("CDSS_API_KEY", "")
_jwt_secret_env = os.environ.get("JWT_SECRET_KEY", "")

if IS_PRODUCTION and not _jwt_secret_env:
    raise RuntimeError(
        "CRITICAL CONFIGURATION ERROR: JWT_SECRET_KEY environment variable is required in production mode. "
        "Application startup aborted."
    )
elif _jwt_secret_env:
    JWT_SECRET_KEY = _jwt_secret_env
else:
    # Explicit development fallback for local testing
    JWT_SECRET_KEY = "dev_insecure_jwt_secret_do_not_use_in_production"

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # 12 hours
ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_DEFAULT_PASSWORD", "Admin@123")

# LLM & Embedding Model Configurations
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
RERANK_MODEL_NAME = os.environ.get("RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RAG_RERANKER_MODEL = RERANK_MODEL_NAME

# Retrieval & Verification Configurations
SIMILARITY_THRESHOLD_SUPPORTED = float(os.environ.get("SIMILARITY_THRESHOLD_SUPPORTED", "0.58"))
SIMILARITY_THRESHOLD_PARTIAL = float(os.environ.get("SIMILARITY_THRESHOLD_PARTIAL", "0.38"))
NLI_ENTAILMENT_THRESHOLD = float(os.environ.get("NLI_ENTAILMENT_THRESHOLD", "0.58"))
NLI_CONTRADICTION_THRESHOLD = float(os.environ.get("NLI_CONTRADICTION_THRESHOLD", "0.35"))

# Multi-RAG Retrieval Configurations
RAG_DENSE_TOP_K = int(os.environ.get("RAG_DENSE_TOP_K", "40"))
RAG_BM25_TOP_K = int(os.environ.get("RAG_BM25_TOP_K", "40"))
RAG_RRF_TOP_K = int(os.environ.get("RAG_RRF_TOP_K", "40"))
RAG_RRF_K = int(os.environ.get("RAG_RRF_K", "60"))
RAG_RERANK_TOP_K = int(os.environ.get("RAG_RERANK_TOP_K", "8"))
RAG_CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "600"))
RAG_CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "120"))
RAG_ENABLE_QUERY_REWRITE = os.environ.get("RAG_ENABLE_QUERY_REWRITE", "true").lower() in ["1", "true", "yes"]
RAG_ENABLE_BM25 = os.environ.get("RAG_ENABLE_BM25", "true").lower() in ["1", "true", "yes"]
RAG_ENABLE_RERANKER = os.environ.get("RAG_ENABLE_RERANKER", "true").lower() in ["1", "true", "yes"]
RAG_DEBUG = os.environ.get("RAG_DEBUG", "false").lower() in ["1", "true", "yes"]
RAG_INSUFFICIENT_EVIDENCE_THRESHOLD = float(os.environ.get("RAG_INSUFFICIENT_EVIDENCE_THRESHOLD", "0.35"))
RAG_BM25_INDEX_PATH = os.environ.get("RAG_BM25_INDEX_PATH", os.path.join(VECTOR_STORE_DIR, "bm25_index.pkl"))

# Valid User Roles
ROLES = [
    "ADMIN",
    "DOCTOR",
    "FRONT_DESK",
    "INTERN",
    "NURSE",
    "RADIOLOGIST",
    "LABORATORY_TECHNICIAN",
    "OTHER_STAFF"
]

# Valid Document States
DOCUMENT_STATUSES = [
    "PENDING",
    "APPROVED",
    "ACTIVE",
    "FLAGGED",
    "ARCHIVED",
    "DELETED"
]

# Valid Patient States
PATIENT_STATUSES = [
    "ACTIVE",
    "DISCHARGED",
    "ARCHIVED",
    "DELETED"
]

# Controlled Doctor Specialties
DOCTOR_SPECIALTIES = [
    "General Medicine",
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "Dermatology",
    "Gastroenterology",
    "Pulmonology",
    "Emergency Medicine"
]
