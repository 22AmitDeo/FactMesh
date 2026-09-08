from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
from contextlib import asynccontextmanager

from app.config import settings
from app.api import api_router
from app.storage.db import init_db, SessionLocal
from app.services.relation_engine import RelationEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes DB schema and loads existing vectors on startup."""
    init_db()
    with SessionLocal() as db:
        try:
            RelationEngine.reindex_all_existing_facts(db)
        except Exception as e:
            pass
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Fact Knowledge Layer — Cross-document fact extraction, evidence grounding, and incremental relation reasoning.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router)

# Mount Static UI files
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "groq_configured": bool(settings.GROQ_API_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")
