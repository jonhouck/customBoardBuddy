import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import traceback

try:
    # Load environment variables from the project directory
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    key = os.environ.get("AZURE_SEARCH_API_KEY")
    index_name = os.environ.get("AZURE_SEARCH_INDEX", "board-buddy-index")

    if not endpoint or not key:
        print("Missing AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_API_KEY environment variables.")
        exit(1)

    print(f"Connecting to Azure AI Search: {endpoint}")
    print(f"Index name: {index_name}")

    search_client = SearchClient(endpoint=endpoint,
                                 index_name=index_name,
                                 credential=AzureKeyCredential(key))

    count = search_client.get_document_count()
    print(f"\\nSUCCESS! Total chunks currently in the index: {count:,}")
except Exception as e:
    print(f"Error connecting or getting count: {e}")
    traceback.print_exc()
