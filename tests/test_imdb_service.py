"""
Unit tests for the IMDB service layer.
All tests mock httpx to avoid real network calls.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from app.services.imdb import (
    search_imdb_titles,
    get_imdb_title_details,
    get_imdb_parents_guide,
    get_imdb_credits,
)

# Shared fixtures
MOCK_SEARCH_RESPONSE = {
    "titles": [
        {
            "id": "tt0372784",
            "primaryTitle": "Batman Begins",
            "startYear": 2005,
            "primaryImage": {"url": "https://m.media-amazon.com/mock_poster.jpg"},
        }
    ]
}

MOCK_DETAILS_RESPONSE = {
    "id": "tt0372784",
    "primaryTitle": "Batman Begins",
    "startYear": 2005,
    "plot": "After witnessing his parents' death, billionaire Bruce Wayne learns the art of fighting.",
    "primaryImage": {"url": "https://m.media-amazon.com/mock_poster.jpg"},
    "rating": {"aggregateRating": 8.2},
    "directors": [{"displayName": "Christopher Nolan"}],
}

MOCK_PARENTS_GUIDE = {
    "parentsGuide": [
        {
            "category": "VIOLENCE",
            "severityBreakdowns": [
                {"severityLevel": "moderate", "voteCount": 182},
            ],
        },
        {
            "category": "SEXUAL_CONTENT",
            "severityBreakdowns": [
                {"severityLevel": "none", "voteCount": 288},
            ],
        }
    ]
}

MOCK_CREDITS = {
    "credits": [
        {
            "name": {"id": "nm0000288", "displayName": "Christian Bale"},
            "category": "actor",
            "characters": ["Bruce Wayne"],
        },
        {
            "name": {"id": "nm0000553", "displayName": "Liam Neeson"},
            "category": "actor",
            "characters": ["Ducard"],
        },
    ]
}


def make_mock_response(data: dict, status_code: int = 200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


class TestSearchImdbTitles:
    def test_success_returns_titles(self):
        with patch("httpx.get", return_value=make_mock_response(MOCK_SEARCH_RESPONSE)):
            result = search_imdb_titles("Batman Begins")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "tt0372784"
        assert result[0]["primaryTitle"] == "Batman Begins"

    def test_empty_response_returns_empty_list(self):
        with patch("httpx.get", return_value=make_mock_response({"titles": []})):
            result = search_imdb_titles("nonexistent movie")
        assert result == []

    def test_network_error_returns_empty_list(self):
        with patch("httpx.get", side_effect=Exception("Connection error")):
            result = search_imdb_titles("Batman Begins")
        assert result == []


class TestGetImdbTitleDetails:
    def test_success_returns_structured_data(self):
        with patch("httpx.get", return_value=make_mock_response(MOCK_DETAILS_RESPONSE)):
            result = get_imdb_title_details("tt0372784")
        assert result["id"] == "tt0372784"
        assert result["title"] == "Batman Begins"
        assert result["year"] == 2005
        assert "plot" in result
        assert "poster" in result
        assert result["directors"] == ["Christopher Nolan"]
        assert result["rating"] == 8.2

    def test_missing_poster_returns_placeholder(self):
        data = dict(MOCK_DETAILS_RESPONSE)
        data["primaryImage"] = None
        with patch("httpx.get", return_value=make_mock_response(data)):
            result = get_imdb_title_details("tt0372784")
        assert "placehold.co" in result["poster"]

    def test_network_error_returns_empty(self):
        with patch("httpx.get", side_effect=Exception("Timeout")):
            result = get_imdb_title_details("tt0372784")
        assert result == {}


class TestGetImdbParentsGuide:
    def test_success_returns_guide_list(self):
        with patch("httpx.get", return_value=make_mock_response(MOCK_PARENTS_GUIDE)):
            result = get_imdb_parents_guide("tt0372784")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["category"] == "VIOLENCE"

    def test_empty_response_returns_empty_list(self):
        with patch("httpx.get", return_value=make_mock_response({"parentsGuide": []})):
            result = get_imdb_parents_guide("tt0372784")
        assert result == []

    def test_network_error_returns_empty_list(self):
        with patch("httpx.get", side_effect=Exception("Timeout")):
            result = get_imdb_parents_guide("tt0372784")
        assert result == []


class TestGetImdbCredits:
    def test_success_returns_filtered_actors(self):
        with patch("httpx.get", return_value=make_mock_response(MOCK_CREDITS)):
            result = get_imdb_credits("tt0372784")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"]["displayName"] == "Christian Bale"

    def test_filters_non_actor_roles(self):
        data = {
            "credits": [
                {"name": {"displayName": "Christopher Nolan"}, "category": "director"},
                {"name": {"displayName": "Christian Bale"}, "category": "actor", "characters": ["Batman"]},
            ]
        }
        with patch("httpx.get", return_value=make_mock_response(data)):
            result = get_imdb_credits("tt0372784")
        # Only actors should be returned
        assert len(result) == 1
        assert result[0]["name"]["displayName"] == "Christian Bale"

    def test_network_error_returns_empty_list(self):
        with patch("httpx.get", side_effect=Exception("Timeout")):
            result = get_imdb_credits("tt0372784")
        assert result == []
