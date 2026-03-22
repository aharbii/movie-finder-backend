import json
import warnings
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Suppress LangGraph deprecation warnings for the prebuilt ReAct agent
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from langgraph.prebuilt import create_react_agent

from app.core.dependencies import get_llm_model
from app.core.logger import logger

from app.services.qdrant import get_movie_plots
from app.services.imdb import (
    search_imdb_titles,
    get_imdb_title_details,
    get_imdb_parents_guide,
    get_imdb_credits
)


@tool
def query_vector_database_tool(plot_description: str) -> str:
    """Searches the offline vector database of movie plots based on a natural language description. Returns up to 4 potential matches with title, release year, plot, and any available metadata like director."""
    results = get_movie_plots(plot_description, limit=4)
    if not results:
        return "No movies matched the description in the vector database."
    return json.dumps(results)


@tool
def validate_and_fetch_imdb_movie_tool(title: str, expected_year: int = None) -> str:
    """Validates a movie title against IMDB and fetches real-time data: Poster URL, non-spoiled Plot, Director, Rating, and Top Actors. Provide expected_year from the RAG metadata to ensure the correct movie is matched (prevents mixing up remakes or similarly-named films)."""
    candidates = search_imdb_titles(title)
    if not candidates:
        return json.dumps({"error": f"No IMDB matches found for '{title}'"})

    best_match = None
    if expected_year:
        for c in candidates:
            if c.get("startYear") == expected_year:
                best_match = c
                break

    if not best_match:
        best_match = candidates[0]

    details = get_imdb_title_details(best_match.get("id"))
    actors = get_imdb_credits(best_match.get("id"))
    details["actors"] = [a.get("name", {}).get("displayName") for a in actors]

    return json.dumps(details)


@tool
def get_parents_guide_tool(title_id: str) -> str:
    """Fetches the detailed IMDB parents guide (violence, profanity, drug use, frightening scenes, sexual content) for a specific IMDB Title ID (e.g. 'tt0372784'). Use this to answer questions about family-friendliness or suitability for children."""
    guide = get_imdb_parents_guide(title_id)
    if not guide:
        return "No parents guide information available for this title."
    return json.dumps(guide)


@tool
def get_extended_credits_tool(title_id: str) -> str:
    """Fetches the comprehensive cast list for a specific IMDB Title ID (e.g. 'tt0372784'). Use this when the user asks who the actors are."""
    credits_list = get_imdb_credits(title_id)
    if not credits_list:
        return "No credits available for this title."
    return json.dumps(credits_list)


SYSTEM_PROMPT = """You are an enterprise movie assistant that uses offline RAG retrieval and real-time IMDB data. Follow these strict phases:

═══ PHASE 1 – PLOT SEARCH ═══
When the user describes a movie plot:
1. Call `query_vector_database_tool` to retrieve candidate movies.
2. For EVERY returned movie, call `validate_and_fetch_imdb_movie_tool` using its title and release_year to cross-validate and fetch the real IMDB ID, non-spoiled plot, actors, director, and poster.
   - If the RAG year matches the IMDB year AND director matches, you have high confidence it is the correct film.
   - If metadata conflicts, note the discrepancy but still present the movie.
3. Present EXACTLY all retrieved movies in structured Markdown:

### [Movie Title] ([Year])
![Poster](poster_url)
**Director**: ...  **Rating**: ...  **Actors**: ...
**Plot**: [Non-spoiled IMDB plot here]

4. End with: "Is it one of these movies? Reply with the correct title, or say 'no' and describe more about the plot."

═══ PHASE 2 – NEGATIVE FEEDBACK ═══
If the user says none matched:
- Apologize briefly and ask for more specific details: key scenes, character traits, setting, era, or any actor they remember.
- Then call `query_vector_database_tool` again with the enriched description.

═══ PHASE 3 – POSITIVE FEEDBACK & Q&A ═══
When the user confirms a movie (e.g. "Yes, Batman Begins"):
- Acknowledge warmly and confirm the IMDB ID from Phase 1 context.
- For follow-up questions:
  - "Who are the actors?" → call `get_extended_credits_tool` with the IMDB title ID.
  - "Is it family-friendly?" / "Can my kid watch?" → call `get_parents_guide_tool` with the IMDB title ID, then reason through violence/profanity/sexual content levels to give a clear recommendation.
  - Other factual questions → use data already retrieved in Phase 1 before calling any new tool.

CRITICAL RULES:
- NEVER hallucinate actor names, ratings, or plot details. Always rely on tool output.
- Always use the `expected_year` parameter in `validate_and_fetch_imdb_movie_tool` to prevent mixing up movies.
- When using parents guide data, summarize each category (VIOLENCE, PROFANITY, etc.) with its dominant severity level and give a reasoned final recommendation."""


async def run_agent(history: list, latest_query: str) -> str:
    """Invokes the LangGraph AI ReAct Agent with conversational history."""
    logger.info(f"Initiating Movie Agent with {len(history)} messages of history.")
    llm = get_llm_model(temperature=0.0)
    tools = [
        query_vector_database_tool,
        validate_and_fetch_imdb_movie_tool,
        get_parents_guide_tool,
        get_extended_credits_tool
    ]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        agent_executor = create_react_agent(llm, tools)

    lc_history = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in history[:-1]:
        msg_role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else "")
        msg_content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else "")
        if msg_role == "user":
            lc_history.append(HumanMessage(content=msg_content))
        elif msg_role == "ai":
            lc_history.append(AIMessage(content=msg_content))

    lc_history.append(HumanMessage(content=latest_query))

    response = await agent_executor.ainvoke({
        "messages": lc_history
    })

    return str(response["messages"][-1].content)
