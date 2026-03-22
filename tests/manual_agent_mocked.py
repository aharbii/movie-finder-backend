import asyncio
import json
from unittest.mock import patch

from app.services.agent import run_agent

class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content

def mock_get_movie_plots(query: str, limit: int = 4):
    """Mocks Qdrant response natively."""
    return [
        {
            "title": "Batman Begins",
            "release_year": 2005,
            "plot": "After witnessing his parents' death, billionaire Bruce Wayne learns the art of fighting to confront injustice."
        },
        {
            "title": "Daredevil",
            "release_year": 2003,
            "plot": "A man blinded by toxic waste which also enhanced his remaining senses fights crime as an acrobatic martial arts superhero."
        }
    ]

async def test_flow():
    print("--- Test 1: Plot Given (Mocked Qdrant) ---")
    history = []
    latest_query = "super hero who is an orphan and does not have any super powers, but he is rich and trained so hard to be able to fight the crime in his city"
    
    with patch("app.services.agent.get_movie_plots", side_effect=mock_get_movie_plots):
        response = await run_agent(history, latest_query)
        print("AI Response:\\n", response)

if __name__ == "__main__":
    asyncio.run(test_flow())
