from app.core.dependencies import get_qdrant_client, get_embeddings_model
from app.core.logger import logger

def get_movie_plots(query: str, limit: int = 5) -> list:
    """Uses unified Embeddings to search Qdrant for semantic plot matches securely."""
    logger.info(f"Initiating generic Qdrant extraction querying for: '{query}'")
    
    try:
        client = get_qdrant_client()
        embeddings_model = get_embeddings_model()
        
        # Deploy generic LangChain wrapper natively
        vector = embeddings_model.embed_query(query)
        
        search_results = client.query_points(
            collection_name="movie_plots",
            query=vector,
            limit=limit
        )
        
        return [hit.payload for hit in search_results.points]
    except Exception as e:
        logger.error(f"Semantic API Lookup aborted fatally unexpectedly: {e}")
        return []
