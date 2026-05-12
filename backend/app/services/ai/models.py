"""AI model initialization for ANTS."""
import os
from langchain_litellm import ChatLiteLLM
from langchain_core.embeddings import Embeddings
import litellm
from dotenv import load_dotenv

from app.core.logging import setup_logging

load_dotenv(override=True)
logger = setup_logging(__name__)


# Global variables to store LLM instances
_llm = None


def _initialize_llm() -> ChatLiteLLM:
    """Initialize and return a ChatLiteLLM instance backed by LiteLLM."""
    provider = os.getenv("LLM_PROVIDER", "")
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    api_version = os.getenv("LLM_API_VERSION")

    model_name = os.getenv("LLM_MODEL")
    if not model_name:
        raise ValueError("LLM_MODEL environment variable is not set")

    full_model = f"{provider}/{model_name}" if provider else model_name

    logger.info(f"Initializing LiteLLM ChatLiteLLM: model={full_model}")

    return ChatLiteLLM(
        model=full_model,
        temperature=0.2,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
    )


def get_llm() -> ChatLiteLLM:
    """Get the initialized LLM instance."""
    global _llm
    if _llm is None:
        _llm = _initialize_llm()
    return _llm


class _LiteLLMEmbeddings(Embeddings):
    """LangChain Embeddings wrapper backed by litellm."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version

    def _call_litellm(self, texts: list[str]) -> list[list[float]]:
        kwargs: dict = dict(model=self.model, input=texts)
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_version:
            kwargs["api_version"] = self.api_version
        response = litellm.embedding(**kwargs)
        return [item["embedding"] for item in response["data"]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call_litellm(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._call_litellm([text])[0]


def get_embedding_model() -> _LiteLLMEmbeddings:
    """Return a LiteLLM-backed embedding model."""
    provider = os.getenv("EMBED_PROVIDER", "")
    model_name = os.getenv("EMBED_MODEL", "embed-v-4-0")
    full_model = f"{provider}/{model_name}" if provider else model_name

    return _LiteLLMEmbeddings(
        model=full_model,
        api_key=os.getenv("EMBED_API_KEY"),
        api_base=os.getenv("EMBED_API_BASE"),
        api_version=os.getenv("EMBED_API_VERSION"),
    )