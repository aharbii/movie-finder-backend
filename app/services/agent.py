from app.core.dependencies import get_llm_model
from app.core.logger import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool

from app.services.qdrant import get_movie_plots
from app.services.imdb import get_movie_metadata

@tool
def search_movies_tool(query: str, limit: int = 5) -> str:
    """Searches the database of movie plots for matches to the given user description."""
    results = get_movie_plots(query, limit)
    if not results:
        return "No movies matched the description."
    return "\\n".join([f"Title: {r['title']}, Year: {r['release_year']}, Plot snippet: {r['plot'][:200]}" for r in results])

@tool
def fetch_imdb_movie_tool(title: str) -> str:
    """Fetches real-time structured data including Poster URL and precise metadata from IMDB."""
    meta = get_movie_metadata(title)
    if not meta:
        return "Could not fetch metadata for this movie."
    return str(meta)

async def run_agent(history: list, latest_query: str) -> str:
    """Invokes the LangGraph AI React Agent with conversational history."""
    
    logger.info(f"Initiating Tool-Calling generic Agent leveraging {len(history)} tokens of conversational latency.")
    llm = get_llm_model(temperature=0.0)
    tools = [search_movies_tool, fetch_imdb_movie_tool]
    
    system_prompt = (
        "You are a helpful AI movie recommendation assistant. "
        "If the user asks for a movie based on a plot, use the search_movies_tool. "
        "If the user asks for more specific metadata or the poster of a movie, use the fetch_imdb_movie_tool. "
        "Always integrate movie posters (as markdown images) in your feedback if available from IMDB."
    )
    
    # Modernized stable LangGraph implementation dynamically avoiding modifier kwargs
    agent_executor = create_react_agent(llm, tools)
    
    lc_history = [SystemMessage(content=system_prompt)]
    # Safely transpose internal schema models generically to LangChain primitive classes
    for msg in history[:-1]:
        # Utilizing fallback getattr allows for generic dict or Pydantic representations dynamically
        msg_role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else "")
        msg_content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else "")
        if msg_role == "user":
            lc_history.append(HumanMessage(content=msg_content))
        elif msg_role == "ai":
            lc_history.append(AIMessage(content=msg_content))
            
    # Append the newest user context directly mapped
    lc_history.append(HumanMessage(content=latest_query))
            
    response = await agent_executor.ainvoke({
        "messages": lc_history
    })
    
    # LangGraph structural payloads append all sequences logically returning the final state message string
    return str(response["messages"][-1].content)
