import os
import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

def run_eda() -> None:
    """
    Downloads the Wikipedia Movie Plots dataset from Kaggle and performs
    Exploratory Data Analysis (EDA) on the plot lengths of American and British movies.
    
    This is used to determine if text chunking strategies like RecursiveCharacterTextSplitter
    are necessary prior to embedding.
    """
    if not os.getenv("KAGGLE_USERNAME") or not os.getenv("KAGGLE_KEY"):
        print("Warning: KAGGLE_USERNAME and KAGGLE_KEY not found in environment.")
        print("Please set them to download the dataset automatically.")
        
    try:
        api = KaggleApi()
        api.authenticate()
        print("Downloading dataset jrobischon/wikipedia-movie-plots from Kaggle...")
        api.dataset_download_files("jrobischon/wikipedia-movie-plots", path="/tmp", unzip=True)
    except Exception as e:
        print(f"Failed to download from Kaggle: {e}")
    
    path = "/tmp/wiki_movie_plots_deduped.csv"
    if not os.path.exists(path):
        print(f"Dataset not found at {path}. Make sure it is downloaded.")
        return
        
    df = pd.read_csv(path)
    # Filter dataset based on Origin/Ethnicity
    filtered_origin = ["American", "British"]
    df = df[df["Origin/Ethnicity"].isin(filtered_origin)]
    
    # Calculate word and character lengths
    df["plot_length"] = df["Plot"].astype(str).str.len()
    df["plot_words"] = df["Plot"].astype(str).str.split().apply(len)
    
    print("--- EDA on Plot Lengths (American & British Movies) ---")
    print(f"Total movies analyzed: {len(df)}")
    
    print("\n--- Character count statistics ---")
    print(df["plot_length"].describe())
    
    print("\n--- Word count statistics ---")
    print(df["plot_words"].describe())
    
    # Analyze percentiles
    print("\n--- Percentiles (90%, 95%, 99%) ---")
    print(f"90% of plots are under {df['plot_length'].quantile(0.90):.0f} characters.")
    print(f"95% of plots are under {df['plot_length'].quantile(0.95):.0f} characters.")
    print(f"99% of plots are under {df['plot_length'].quantile(0.99):.0f} characters.")
    
    print("\nRecommendation:")
    print("If 95% of plots are below your embedding model's context window limit (e.g. 8192 tokens for text-embedding-3),")
    print("you may not need a RecursiveCharacterTextSplitter. However, chunking is still recommended for semantic precision.")

if __name__ == "__main__":
    run_eda()
