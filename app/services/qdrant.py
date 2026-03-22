import os
from openai import OpenAI
from qdrant_client import QdrantClient
from app.core.config import settings

def get_movie_plots(query: str, limit: int = 5) -> list:
    """Uses OpenAI embeddings to search Qdrant for semantic plot matches."""
    
    client = QdrantClient(url=settings.QDRANT_URL)
    
    if settings.OLLAMA_BASE_URL:
        o_client = OpenAI(base_url=f"{settings.OLLAMA_BASE_URL.rstrip('/')}/v1", api_key="ollama")
        embed_model = getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
    else:
        o_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        embed_model = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
        
    response = o_client.embeddings.create(input=[query], model=embed_model)
    vector = response.data[0].embedding
    
    search_results = client.search(
        collection_name="movie_plots",
        query_vector=vector,
        limit=limit
    )
    
    return [hit.payload for hit in search_results]
