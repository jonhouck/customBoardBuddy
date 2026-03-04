import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We need to test:
# 1. Azure AI Search
# 2. Azure OpenAI Chat Deployment
# 3. Azure OpenAI Embedding Deployment

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX_NAME")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

errors = []

print("Running Resource Verification...")

# 1. Test Azure Search
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_KEY:
        errors.append("Missing Azure Search credentials in .env")
    else:
        index_client = SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
        index = index_client.get_index(AZURE_SEARCH_INDEX)
        print(f"✅ Azure Search Index '{AZURE_SEARCH_INDEX}' found.")
except Exception as e:
    errors.append(f"Azure Search validation failed: {e}")

# 2. Test Azure OpenAI Chat
try:
    from openai import AzureOpenAI
    
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        errors.append("Missing Azure OpenAI credentials in .env")
    else:
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,  
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        # Just sending a tiny ping message to chat completions
        response = client.chat.completions.create(
            model=AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        print(f"✅ Azure OpenAI Chat Deployment '{AZURE_OPENAI_CHAT_DEPLOYMENT}' is accessible.")
        
        # Test embeddings
        emb_response = client.embeddings.create(
            input="test",
            model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        )
        print(f"✅ Azure OpenAI Embedding Deployment '{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}' is accessible.")
except Exception as e:
    errors.append(f"Azure OpenAI validation failed: {e}")

if errors:
    print("\n❌ Errors Encountered:")
    for err in errors:
        print(f"- {err}")
    sys.exit(1)
else:
    print("\n✅ All required resources are accessible.")
    sys.exit(0)
