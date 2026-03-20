import asyncio
from api.config import get_settings, get_azure_search_client
from azure.search.documents.models import QueryType

async def test_search():
    settings = get_settings()
    search_client = get_azure_search_client()

    url = "https://mwdh2o.legistar1.com/mwdh2o/attachments/f4be8fa9-5c2b-43e0-bc57-ab80ffcf6a73.pdf"
    
    # We can't easily filter by exact url because of reserved characters sometimes, 
    # but we can try exact search string
    search_results = search_client.search(
        search_text=f'"{url}"',
        select=["id", "title", "document_type", "source_url"]
    )
    
    count = 0
    for i, result in enumerate(search_results):
        count += 1
        print(f"Found Chunk {i+1}: {result.get('title')}")
        
    print(f"Total chunks found: {count}")

asyncio.run(test_search())
