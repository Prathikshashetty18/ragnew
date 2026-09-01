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
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./clinical_rag.db")

# Security Configurations
# API key to protect clinical server endpoints. If set, frontend must supply X-API-Key header.
CDSS_API_KEY = os.environ.get("CDSS_API_KEY", "")

# LLM & Embedding Model Configurations
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
RERANK_MODEL_NAME = os.environ.get("RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Retrieval & Verification Configurations
SIMILARITY_THRESHOLD_SUPPORTED = 0.65
SIMILARITY_THRESHOLD_PARTIAL = 0.45
