import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool

from app.services.qdrant import get_movie_plots
from app.services.imdb import get_movie_metadata

@tool
def search_movies_tool(query: str, limit: int = 5) -> str:
    """Searches the database of movie plots for matches to the given user description."""
    results = get_movie_plots(query, limit)
    if not results:
        return "No movies matched the description."
    return "\\n".join([f"Title: {r['title']}, Year: {r['release_year']}, Plot snippet: {r['chunk_text'][:200]}" for r in results])

@tool
def fetch_imdb_movie_tool(title: str) -> str:
    """Fetches real-time structured data including Poster URL and precise metadata from IMDB."""
    meta = get_movie_metadata(title)
    if not meta:
        return "Could not fetch metadata for this movie."
    return str(meta)

async def run_agent(history: list, latest_query: str) -> str:
    """Invokes the LangChain AI agent with conversational history."""
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    tools = [search_movies_tool, fetch_imdb_movie_tool]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI movie recommendation assistant. "
                   "If the user asks for a movie based on a plot, use the search_movies_tool. "
                   "If the user asks for more specific metadata or the poster of a movie, use the fetch_imdb_movie_tool. "
                   "Always integrate movie posters (as markdown images) in your feedback if available from IMDB."),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    lc_history = []
    # Convert db models accurately, ignoring the last user msg
    for msg in history[:-1]:
        if msg.role == "user":
            lc_history.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            lc_history.append(AIMessage(content=msg.content))
            
    response = await agent_executor.ainvoke({
        "input": latest_query,
        "chat_history": lc_history
    })
    
    return response["output"]
