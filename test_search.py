import asyncio
from api.config import get_settings, get_azure_search_client, get_azure_openai_client
from azure.search.documents.models import VectorizedQuery, QueryType

async def test_search():
    settings = get_settings()
    search_client = get_azure_search_client()
    openai_client = get_azure_openai_client()

    query = "03102025 OWA 8-1 Presentation"
    print(f"Searching for: {query}")
    
    emb_response = openai_client.embeddings.create(
        input=query,
        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    )
    query_vector = emb_response.data[0].embedding

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=5,
        fields="content_vector"
    )

    search_results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        select=["id", "title", "document_type", "source_url"],
        top=5,
        query_type=QueryType.SEMANTIC,
        semantic_configuration_name="boardbuddy-semantic-config"
    )

    for i, result in enumerate(search_results):
        print(f"Result {i+1}: {result.get('title')} ({result.get('document_type')}) - {result.get('source_url')}")

asyncio.run(test_search())
