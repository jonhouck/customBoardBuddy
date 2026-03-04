import os
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
)

def create_or_update_index():
    # Load environment variables
    load_dotenv()
    endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

    if not endpoint or not admin_key or not index_name:
        raise ValueError("Missing Azure Search environment variables in .env file.")

    # Initialize the Search Index Client
    credential = AzureKeyCredential(admin_key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    # 1. Define the Index Schema Fields
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="chunk_text", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchField(
            name="content_vector", 
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True, 
            vector_search_dimensions=3072, # Dimension size for text-embedding-3-large
            vector_search_profile_name="boardbuddy-vector-profile"
        ),
        SimpleField(name="source_system", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="matter_status", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="year", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="date_published", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SimpleField(name="source_url", type=SearchFieldDataType.String, filterable=False, retrievable=True),
    ]

    # 2. Configure Vector Search (HNSW)
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-config",
                parameters={"m": 4, "efConstruction": 400, "efSearch": 500, "metric": "cosine"}
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="boardbuddy-vector-profile",
                algorithm_configuration_name="hnsw-config"
            )
        ]
    )

    # 3. Configure Semantic Search
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="boardbuddy-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="chunk_text")]
                )
            )
        ]
    )

    # 4. Construct the Index
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search
    )

    # 5. Create or Update Index in Azure
    print(f"Creating or updating index '{index_name}' at {endpoint}...")
    result = index_client.create_or_update_index(index)
    print(f"Successfully configured index: {result.name}")

if __name__ == "__main__":
    create_or_update_index()
