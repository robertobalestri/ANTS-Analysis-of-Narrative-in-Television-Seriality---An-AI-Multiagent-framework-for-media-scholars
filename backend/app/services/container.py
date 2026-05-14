"""Dependency injection container for ANTS services."""
from functools import lru_cache
from app.services.ai.models import get_llm, get_embedding_model
from app.services.ai.vector import VectorStoreService
from app.services.ai.llm import LLMService
from app.repositories import DatabaseSessionManager


@lru_cache()
def get_llm_service() -> LLMService:
    """Get LLMService singleton."""
    return LLMService()


@lru_cache()
def get_vector_store_service() -> VectorStoreService:
    """Get VectorStoreService singleton."""
    return VectorStoreService()


@lru_cache()
def get_db_manager() -> DatabaseSessionManager:
    """Get DatabaseSessionManager singleton."""
    return DatabaseSessionManager()


def get_llm_model():
    """Get the raw LLM model instance."""
    return get_llm()


def get_embedding():
    """Get embedding model instance."""
    return get_embedding_model()
