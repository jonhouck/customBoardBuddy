import asyncio
from api.main import chat_endpoint, ChatRequest
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    history = [
        {"role": "user", "content": "What was the cost for the 6,000 gallon above ground diesel tank that went to the EO&T committee in February 2026, where is it, and who was the contract awarded to?"},
        {"role": "assistant", "content": "The contract was valued at $767,063. It was for the installation of a new 6,000-gallon aboveground diesel fuel tank at the Lake Mathews facility, and the contract was awarded to Western Pump Inc. [1][2]"},
        {"role": "user", "content": "What other items were brought to that same EO&T committee meeting?"},
        {"role": "assistant", "content": "At the February 9, 2026 meeting, in addition to discussing the diesel tank contract (item 7-1), the committee also approved the January 12, 2026 meeting minutes (a consent calendar item) and considered an agenda item (item 8-1) to certify the Final Environmental Impact Report and take related CEQA actions [1]."},
    ]
    
    # Test query 1
    req1 = ChatRequest(
        query="What's on the upcoming agenda for the March 2026 board meeting?",
        history=history
    )
    res1 = await chat_endpoint(req1)
    
    # Add to history
    history.append({"role": "user", "content": req1.query})
    history.append({"role": "assistant", "content": res1.response})
    
    # Test query 2
    req2 = ChatRequest(
        query="Alright, what was on the agenda for the February 2026 full board meeting?",
        history=history
    )
    res2 = await chat_endpoint(req2)

asyncio.run(main())
