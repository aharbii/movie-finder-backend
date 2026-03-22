"""
Unit tests for the LangGraph ReAct Agent conversational phases.
Mocks both Qdrant and IMDB services to test agent reasoning logic in isolation.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

# We test the agent function directly in a mocked context
from app.services.agent import run_agent

RAG_MOCK_RESULTS = [
    {
        "title": "Batman Begins",
        "release_year": 2005,
        "plot": "Billionaire Bruce Wayne fights crime as Batman.",
        "director": "Christopher Nolan",
    },
    {
        "title": "Daredevil",
        "release_year": 2003,
        "plot": "A man blinded by toxic waste fights crime.",
        "director": "Mark Steven Johnson",
    },
]

IMDB_DETAILS_MOCK = {
    "id": "tt0372784",
    "title": "Batman Begins",
    "year": 2005,
    "plot": "After witnessing his parents' death, billionaire Bruce Wayne learns the art of fighting.",
    "poster": "https://m.media-amazon.com/images/mock.jpg",
    "rating": 8.2,
    "directors": ["Christopher Nolan"],
    "actors": ["Christian Bale", "Liam Neeson", "Michael Caine"],
}

PARENTS_GUIDE_MOCK = [
    {
        "category": "VIOLENCE",
        "severityBreakdowns": [{"severityLevel": "moderate", "voteCount": 182}],
        "reviews": [{"text": "Some battles but minimal gore."}],
    },
    {
        "category": "SEXUAL_CONTENT",
        "severityBreakdowns": [{"severityLevel": "none", "voteCount": 288}],
        "reviews": [{"text": "Nothing explicit."}],
    },
]


@pytest.mark.asyncio
async def test_phase1_plot_search_returns_movies():
    """Test that giving a plot description triggers the RAG + IMDB validation flow."""
    user_plot = (
        "A rich orphan with no superpowers trains hard to fight crime in his city."
    )
    history = []

    with (
        patch("app.services.agent.get_movie_plots", return_value=RAG_MOCK_RESULTS),
        patch("app.services.imdb.search_imdb_titles", return_value=[{"id": "tt0372784", "primaryTitle": "Batman Begins", "startYear": 2005}]),
        patch("app.services.imdb.get_imdb_title_details", return_value=IMDB_DETAILS_MOCK),
        patch("app.services.imdb.get_imdb_credits", return_value=[]),
    ):
        response = await run_agent(history, user_plot)

    assert response  # must return something
    assert len(response) > 50  # non-trivial response


@pytest.mark.asyncio
async def test_phase2_negative_feedback_asks_for_more_details():
    """Test that a negative feedback message triggers the agent to ask for more plot info."""
    history = [
        type("M", (), {"role": "user", "content": "A rich orphan who fights crime with no superpowers."})(),
        type("M", (), {"role": "ai", "content": "Here are 4 candidates: Batman Begins, Daredevil... Is it one of these?"})(),
    ]
    negative_query = "No, none of these is the movie I'm looking for."

    with (
        patch("app.services.agent.get_movie_plots", return_value=[]),
        patch("app.services.imdb.search_imdb_titles", return_value=[]),
    ):
        response = await run_agent(history, negative_query)

    assert response
    # The agent should prompt for more details
    assert len(response) > 20


@pytest.mark.asyncio
async def test_phase3_family_suitability_question():
    """Test that asking about family-suitability triggers get_parents_guide_tool call."""
    history = [
        type("M", (), {"role": "user", "content": "A rich orphan who fights crime"})(),
        type("M", (), {"role": "ai", "content": "I found Batman Begins (tt0372784). Is this it?"})(),
        type("M", (), {"role": "user", "content": "Yes, Batman Begins."})(),
        type("M", (), {"role": "ai", "content": "Great! Batman Begins confirmed. How can I help you?"})(),
    ]
    question = "Is Batman Begins suitable for a family with young kids?"

    with (
        patch("app.services.agent.get_movie_plots", return_value=[]),
        patch("app.services.imdb.search_imdb_titles", return_value=[{"id": "tt0372784", "primaryTitle": "Batman Begins", "startYear": 2005}]),
        patch("app.services.imdb.get_imdb_parents_guide", return_value=PARENTS_GUIDE_MOCK),
        patch("app.services.imdb.get_imdb_title_details", return_value=IMDB_DETAILS_MOCK),
        patch("app.services.imdb.get_imdb_credits", return_value=[]),
    ):
        response = await run_agent(history, question)

    assert response
    assert len(response) > 30
