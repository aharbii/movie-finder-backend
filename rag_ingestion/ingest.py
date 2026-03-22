import os
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

import argparse
import pandas as pd
from tqdm import tqdm
from typing import Optional, List
from pydantic import BaseModel
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from kaggle.api.kaggle_api_extended import KaggleApi

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
        raise ValueError("KAGGLE_USERNAME and KAGGLE_KEY environment variables are required.")
    
    print("Authenticating with Kaggle API...")
    api = KaggleApi()
    api.authenticate()
    
    print("Downloading dataset jrobischon/wikipedia-movie-plots from Kaggle...")
    api.dataset_download_files('jrobischon/wikipedia-movie-plots', path='/tmp', unzip=True)
    
    csv_path = "/tmp/wiki_movie_plots_deduped.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Expected unzipped file at {csv_path} not found.")
    
    return pd.read_csv(csv_path)

def ingest(qdrant_url: str, testing_limit: Optional[int] = None) -> None:
    """
    Ingests movie plots from the localized Kaggle CSV into a Qdrant collection.
    Limits ingestion if 'testing_limit' is set, to preserve API usage during testing.

    Args:
        qdrant_url (str): The URL of the Qdrant instance.
        testing_limit (Optional[int]): If provided, only this many records will be processed.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable is missing.")

    df = download_dataset()
    
    # Filter dataset based on Origin/Ethnicity
    filtered_origin: List[str] = ["American", "British"]
    print(f"Filtering dataset to origins: {filtered_origin}")
    df = df[df["Origin/Ethnicity"].isin(filtered_origin)]
    
    # Apply testing limit logic to optimize costs locally
    if testing_limit and testing_limit > 0:
        print(f"TESTING LIMIT applied: Shrinking dataset from {len(df)} to {testing_limit} records to save OpenAI costs.")
        df = df.head(testing_limit)
    else:
        print(f"Filtered dataset down to {len(df)} records. No test limit applied.")

    q_client = QdrantClient(url=qdrant_url)
    
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    if ollama_url:
        o_client = OpenAI(base_url=f"{ollama_url.rstrip('/')}/v1", api_key="ollama")
        embed_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        vector_size = int(os.getenv("EMBEDDING_DIMENSION", 768))
    else:
        if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-testkey":
            raise ValueError("OPENAI_API_KEY is completely missing or is set to a placeholder while OLLAMA_BASE_URL is empty. Supply a real key or provide Ollama URL config.")
        o_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        embed_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        vector_size = int(os.getenv("EMBEDDING_DIMENSION", 1536))

    collection_name = "movie_plots"

    print(f"Recreating Qdrant collection: {collection_name}")
    q_client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    # We embed the entire Wikipedia plot as a single chunk since EDA and common bounds 
    # indicate plots fit well within the 8192 token limit of text-embedding-3-small.
    points: List[PointStruct] = []
    print("Embedding Movie Plots...")
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        title: str = str(row.get("Title", "Unknown"))
        genre: str = str(row.get("Genre", "Unknown"))
        cast: str = str(row.get("Cast", "Unknown"))
        plot: str = str(row.get("Plot", ""))
        
        full_text = f"Title: {title}\\nGenre: {genre}\\nCast: {cast}\\nPlot: {plot}"
        
        try:
            response = o_client.embeddings.create(input=[full_text], model=embed_model)
            embedding = response.data[0].embedding
        except Exception as e:
            print(f"Fatal error encountered during embedding generation on row {idx}: {e}")
            raise e

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
    
    print("Ingestion complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Movies to Qdrant")
    parser.add_argument("--qdrant", default="http://localhost:6333", help="Qdrant node URL")
    
    args = parser.parse_args()
    
    # Enforce testing limit from environment to prevent runaway token usage during CI or local testing
    test_limit = os.getenv("TESTING_LIMIT")
    test_limit_val = int(test_limit) if test_limit and test_limit.isdigit() else None
    
    ingest(args.qdrant, testing_limit=test_limit_val)
