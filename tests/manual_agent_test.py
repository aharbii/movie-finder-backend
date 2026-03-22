import asyncio
from app.services.agent import run_agent

class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content

async def test_flow():
    print("--- Test 1: Plot Given ---")
    history = []
    latest_query = "super hero who is an orphan and does not have any super powers, but he is rich and trained so hard to be able to fight the crime in his city"
    response = await run_agent(history, latest_query)
    print("AI Response:\\n", response)

if __name__ == "__main__":
    asyncio.run(test_flow())
