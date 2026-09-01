import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App Directory Configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
VECTOR_STORE_DIR = os.environ.get("VECTOR_STORE_DIR", os.path.join(BASE_DIR, "vector_store"))
SEED_DIR = os.environ.get("SEED_DIR", os.path.join(BASE_DIR, "seed_data"))

# Ensure paths exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
os.makedirs(SEED_DIR, exist_ok=True)

# Database Configurations
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./clinical_rag_v2.db")

# Security & JWT Configurations
CDSS_API_KEY = os.environ.get("CDSS_API_KEY", "")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "cdss_clinical_rag_secret_key_2026_hospital_secure")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # 12 hours
ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_DEFAULT_PASSWORD", "Admin@123")

# LLM & Embedding Model Configurations
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
RERANK_MODEL_NAME = os.environ.get("RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Retrieval & Verification Configurations
SIMILARITY_THRESHOLD_SUPPORTED = 0.65
SIMILARITY_THRESHOLD_PARTIAL = 0.45
NLI_ENTAILMENT_THRESHOLD = 0.65
NLI_CONTRADICTION_THRESHOLD = 0.35

# Valid User Roles
ROLES = [
    "ADMIN",
    "DOCTOR",
    "FRONT_DESK",
    "INTERN",
    "NURSE",
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
