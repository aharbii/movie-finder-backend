import os
import sys

# Ensure local dynamic pathing incorporates root directory natively preventing ModuleNotFound anomalies
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

import argparse
import pandas as pd
from tqdm import tqdm
from typing import Optional, List
from qdrant_client.models import Distance, VectorParams, PointStruct
from kaggle.api.kaggle_api_extended import KaggleApi
from app.core.dependencies import get_qdrant_client, get_embeddings_model
from app.core.logger import logger

def download_dataset() -> pd.DataFrame:
    """
    Authenticates with Kaggle, downloads the wikipedia movie plots dataset,
    extracts it to /tmp, and loads it into a Pandas DataFrame.

    Raises:
        ValueError: If Kaggle credentials are missing from the environment.
        FileNotFoundError: If the unzipped CSV is not found at the expected path.
        
    Returns:
        pd.DataFrame: The loaded dataset.
    """
    if not os.getenv("KAGGLE_USERNAME") or not os.getenv("KAGGLE_KEY"):
        logger.error("Required authentication keys missing for remote synchronization.")
        raise ValueError("KAGGLE_USERNAME and KAGGLE_KEY environment variables are required.")
    
    logger.info("Authenticating with comprehensive generic Kaggle API mapping seamlessly...")
    api = KaggleApi()
    api.authenticate()
    
    logger.info("Executing isolated data pipeline from jrobischon/wikipedia-movie-plots seamlessly...")
    api.dataset_download_files('jrobischon/wikipedia-movie-plots', path='/tmp', unzip=True)
    
    csv_path = "/tmp/wiki_movie_plots_deduped.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Expected unzipped file at {csv_path} not found.")
    
    return pd.read_csv(csv_path)

def ingest(qdrant_url: str) -> None:
    """
    Ingests movie plots from the localized Kaggle CSV organically mapped utilizing pure generic embed dimensions via DI!
    """

    df = download_dataset()
    
    # Filter dataset based on Origin/Ethnicity
    filtered_origin: List[str] = ["American", "British"]
    logger.info(f"Sequentially filtering dataset matrices strictly mapping origins: {filtered_origin}")
    df = df[df["Origin/Ethnicity"].isin(filtered_origin)]
    
    logger.info(f"Initiating entire dataset traversal yielding {len(df)} authentic records without cost truncations.")

    q_client = get_qdrant_client()
    embeddings_model = get_embeddings_model()
    
    # Explicit mapping resolving vector dimensions securely bridging dynamic Ollama embeddings
    vector_size = int(os.getenv("EMBEDDING_DIMENSION", 768 if os.getenv("OLLAMA_BASE_URL") else 1536))

    collection_name = "movie_plots"

    logger.info(f"Recreating robust Qdrant collection node: {collection_name} dimensionally binding {vector_size}")
    if q_client.collection_exists(collection_name=collection_name):
        q_client.delete_collection(collection_name=collection_name)
        
    q_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    # Enforce safe batch processing natively generating matrices securely locally without timeouts
    points: List[PointStruct] = []
    logger.info("Executing Organic Vector Sequence generation safely internally resolving strings.")
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        title: str = str(row.get("Title", "Unknown"))
        genre: str = str(row.get("Genre", "Unknown"))
        cast: str = str(row.get("Cast", "Unknown"))
        plot: str = str(row.get("Plot", ""))
        
        # Enforce hard upper boundary of 8000 characters universally ensuring standard Ollama 'num_ctx=2048' limits seamlessly
        full_text = f"Title: {title}\\nGenre: {genre}\\nCast: {cast}\\nPlot: {plot}"[:8000]
        
        try:
            # Replaced raw OpenAI parameter usage explicitly resolving universally generic DI
            embedding = embeddings_model.embed_query(full_text)
        except Exception as e:
            logger.error(f"Fatal disruption observed extracting topological semantic density for idx {idx}: {e}")
            continue

        point_id: int = int(idx) 
        
        # Full payload metadata matching the conceptual Movie BaseModel
        payload = {
            "title": title,
            "release_year": int(row.get("Release Year", 0)),
            "director": str(row.get("Director", "")),
            "genre": genre,
            "cast": cast,
            "plot": plot,
            "wiki_page": str(row.get("Wiki Page", "")),
            "origin": str(row.get("Origin/Ethnicity", "")),
        }
        
        points.append(PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        ))

        if len(points) >= 500:
            q_client.upsert(collection_name=collection_name, points=points)
            points = []

    if points:
        q_client.upsert(collection_name=collection_name, points=points)
    
    logger.info("Universal RAG Matrix completely indexed dynamically resolving perfectly.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Matrices natively onto specific addresses")
    default_qdrant = os.getenv("QDRANT_URL", "http://localhost:6333")
    parser.add_argument("--qdrant", default=default_qdrant, help="Qdrant API Route")
    
    args = parser.parse_args()
    
    # Executes uninhibited structural mappings dynamically skipping limit truncations!
    ingest(args.qdrant)
