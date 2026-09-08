import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    PROJECT_NAME: str = "Fact Knowledge Layer"
    VERSION: str = "0.1.0"
    
    # LLM configurations
    _raw_groq = os.getenv("GROQ_API_KEY", "")
    GROQ_API_KEY: str = "" if "your_" in _raw_groq else _raw_groq
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    _raw_gemini = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    GEMINI_API_KEY: str = "" if "your_" in _raw_gemini else _raw_gemini
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    # Embeddings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'factmesh.db'}")
    
    # File upload directory
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
    
    # Concurrency and retrieval limits
    MAX_CONCURRENT_PAGES: int = int(os.getenv("MAX_CONCURRENT_PAGES", "3"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.50"))
    TOP_K_CANDIDATES: int = int(os.getenv("TOP_K_CANDIDATES", "5"))

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
