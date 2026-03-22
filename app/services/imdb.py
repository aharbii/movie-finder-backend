import httpx
from app.core.config import settings

def get_movie_metadata(title: str) -> dict:
    """Fetches real-time structured data including Poster URL from IMDBApi.dev."""
    url = f"https://api.imdbapi.dev/search/titles"
    params = {"query": title}
    
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        # Depending on API structure, grab the first best match
        if "results" in data and len(data["results"]) > 0:
            return data["results"][0]
        return data
        
    except Exception as e:
        print(f"Error fetching IMDB data for {title}: {e}")
        return {
            "error": "Could not fetch precise IMDB data",
            "title": title,
            "poster": "https://via.placeholder.com/300x450?text=No+Poster+Found"
        }
