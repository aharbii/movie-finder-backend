import os
from app.core.dependencies import get_qdrant_client, get_embeddings_model
from app.core.logger import logger

# Disable LangSmith telemetry to prevent noise during local development
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")


def get_movie_plots(query: str, limit: int = 4) -> list:
    """Searches Qdrant vector DB for semantic plot matches.
    Returns a list of payloads with full metadata including title, release_year, plot, director, etc.
    """
    logger.info(f"Querying Qdrant for: '{query}'")

    try:
        client = get_qdrant_client()
        embeddings_model = get_embeddings_model()
        vector = embeddings_model.embed_query(query)

        search_results = client.query_points(
            collection_name="movie_plots",
            query=vector,
            limit=limit,
            with_payload=True,
        )

        results = []
        for hit in search_results.points:
            payload = hit.payload or {}
            results.append({
                "title": payload.get("title", "Unknown"),
                "release_year": payload.get("release_year") or payload.get("year"),
                "plot": payload.get("plot", ""),
                "director": payload.get("director", ""),
                "origin": payload.get("origin", ""),
                "wiki_page": payload.get("wiki_page", ""),
                "score": round(hit.score, 4) if hasattr(hit, "score") else None,
            })

        logger.info(f"Qdrant returned {len(results)} results for query.")
        return results

    except Exception as e:
        logger.error(f"Qdrant query failed: {e}")
        return []
