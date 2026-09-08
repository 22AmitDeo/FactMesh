from fastapi import APIRouter
from app.api.documents import router as documents_router
from app.api.facts import router as facts_router
from app.api.relations import router as relations_router

api_router = APIRouter()
api_router.include_router(documents_router)
api_router.include_router(facts_router)
api_router.include_router(relations_router)

__all__ = ["api_router"]
