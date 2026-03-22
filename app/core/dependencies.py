from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from app.core.config import settings
from app.core.logger import logger

def get_qdrant_client() -> QdrantClient:
    """Generates the Qdrant connection uniformly seamlessly across processes."""
    logger.info(f"Initializing generic QdrantClient bound to {settings.QDRANT_URL}")
    return QdrantClient(url=settings.QDRANT_URL)

def get_embeddings_model() -> Embeddings:
    """Dependency Provider scaling out Embeddings logically masking AI boundaries."""
    if settings.OLLAMA_BASE_URL:
        logger.info(f"Injecting isolated OllamaEmbeddings dynamically logic: {settings.EMBEDDING_MODEL}")
        return OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.EMBEDDING_MODEL,
        )
    
    logger.info(f"Injecting generic OpenAIEmbeddings structure: {settings.EMBEDDING_MODEL}")
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY
    )

def get_llm_model(temperature: float = 0.0) -> BaseChatModel:
    """Generates Chat Models dynamically supporting OpenSource abstractions securely out-of-the-box."""
    if settings.OLLAMA_BASE_URL:
        # Since we use nomic-embed-text for embeddings natively, llama3 is standard for chat organically
        # Allow passing LLAMA parameters cleanly if present, otherwise default to "llama3.2"
        model_name = getattr(settings, "OLLAMA_CHAT_MODEL", "llama3.2")
        logger.info(f"Instantiating ChatOllama locally utilizing isolated node '{model_name}' natively")
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=model_name,
            temperature=temperature
        )
        
    logger.info("Initializing baseline ChatOpenAI securely.")
    return ChatOpenAI(
        model="gpt-4o",
        temperature=temperature,
        openai_api_key=settings.OPENAI_API_KEY
    )
