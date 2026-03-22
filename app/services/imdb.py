import httpx
from app.core.config import settings

def search_imdb_titles(query: str) -> list:
    """Fetches a list of candidate titles from IMDBApi based on a search query."""
    url = "https://api.imdbapi.dev/search/titles"
    params = {"query": query}
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        return data.get("titles", [])
    except Exception as e:
        print(f"Error searching IMDB titles for {query}: {e}")
        return []

def get_imdb_title_details(title_id: str) -> dict:
    """Fetches real-time structured data including Poster URL and Plot from IMDBApi."""
    url = f"https://api.imdbapi.dev/titles/{title_id}"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        movie = response.json()
        
        return {
            "id": movie.get("id"),
            "title": movie.get("primaryTitle"),
            "year": movie.get("startYear"),
            "plot": movie.get("plot", "No plot available."),
            "poster": movie.get("primaryImage", {}).get("url") if movie.get("primaryImage") else "https://placehold.co/300x450?text=No+Poster",
            "rating": movie.get("rating", {}).get("aggregateRating"),
            "directors": [d.get("displayName") for d in movie.get("directors", [])]
        }
    except Exception as e:
        print(f"Error fetching IMDB details for {title_id}: {e}")
        return {}

def get_imdb_parents_guide(title_id: str) -> list:
    """Fetches the parents guide (violence, profanity, etc.) for a title."""
    url = f"https://api.imdbapi.dev/titles/{title_id}/parentsGuide"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json().get("parentsGuide", [])
    except Exception as e:
        print(f"Error fetching IMDB parents guide for {title_id}: {e}")
        return []

def get_imdb_credits(title_id: str) -> list:
    """Fetches the cast and crew for a title."""
    url = f"https://api.imdbapi.dev/titles/{title_id}/credits"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        # Filter for actors to keep payload size manageable
        actors = [c for c in data.get("credits", []) if c.get("category") in ("actor", "actress")]
        return actors[:15] # Return top 15 actors
    except Exception as e:
        print(f"Error fetching IMDB credits for {title_id}: {e}")
        return []
