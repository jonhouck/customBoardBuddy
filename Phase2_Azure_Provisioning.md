# Phase 2 Azure Provisioning Requirements

To proceed with testing the Azure AI Search index schema and integration, we need specific Azure resources provisioned under the *MWDDev* subscription and the *rg-boardbuddy* resource group.

## 1. Resources to Provision

### A. Azure AI Search Service
- **Resource Group:** rg-boardbuddy
- **Service Name:** e.g., `boardbuddy-search-service`
- **Pricing Tier:** Basic or Standard (Must support Vector Search and Semantic Ranker)
- **Features Enablement:** Ensure Semantic Ranker is turned on (can be configured in the Azure AI Search resource -> Semantic Search blade).

### B. Azure OpenAI Service & App Deployments
*Since `gpt-5.2` is not available in USWEST3, `o3-mini` is an excellent choice for this system! It provides outstanding reasoning capabilities at a very cost-effective price tier, making it ideal for the complex retrieval, synthesis, and strict instruction following required by RAG.*

Please follow these exact steps to provision the models:

1. **Create the Azure OpenAI Resource:**
   - Go to the Azure Portal (portal.azure.com).
   - Create a new resource -> Azure OpenAI.
   - Place it in the `rg-boardbuddy` resource group under `MWDDev`. Let's name it `boardbuddy-openai-service`.

2. **Access Azure AI Foundry (formerly Azure OpenAI Studio):**
   - Once the service is created, go to the resource.
   - Click the button **"Go to Azure OpenAI Studio"** (or navigate to `https://oai.azure.com` / `https://ai.azure.com` and select your directory/resource).

3. **Deploy the Models (Step-by-step):**
   - In the left-hand navigation pane, find and click on **"Deployments"**.
   - Click on the **"+ Create new deployment"** or **"Deploy model"** button.
   - **For Embeddings (Required for indexing):**
     - Select Model: `text-embedding-3-large` (or `text-embedding-3-small` if large is unavailable).
     - Deployment Name: Let's explicitly name it `text-embedding-3-large`.
     - Click **Deploy**.
   - **For Chat/Synthesis (Recommended):**
     - Click **"+ Create new deployment"** again.
     - Select Model: `o3-mini`.
     - Deployment Name: Let's explicitly name it `o3-mini`.
     - Click **Deploy**.

## 2. Returning the Config back to the Project

You are completely correct. While Azure recently introduced a new SDK focused on "Projects", the most stable, modern, and universally supported method for connecting LangChain, LlamaIndex, or the raw OpenAI SDK is exactly what your portal is showing you: **Using the explicit Endpoint URL and API Key for your deployed models.** This guarantees compatibility with our RAG orchestration libraries.

Once the resources and deployments are successfully created, follow these steps to securely hand the keys back to the project:

1. Copy the `.env.example` file to a new file named `.env` in the root directory.
2. **For Azure OpenAI (AI Foundry):**
   - Go to your AI Foundry Portal -> **Deployments + Endpoint** page.
   - Look at the code snippet it provided you (the one with `endpoint = "https://boardbuddy-openai-service.cognitiveservices.azure.com/"`).
   - Copy that `endpoint` URL.
   - Copy the API Key they provide.
3. **For AI Search:** 
   - Go to your Azure AI Search resource in the Azure Portal and click **"Keys"** in the left menu. 
   - Copy the **Primary Admin Key** and the **Url** from the Overview tab.
4. Fill out the `.env` file with these exact values:

```env
# Azure AI Search Service
AZURE_SEARCH_SERVICE_ENDPOINT="https://<your-search-service>.search.windows.net" # From AI Search Overview Tab
AZURE_SEARCH_ADMIN_KEY="<your-search-admin-key>" # From AI Search Keys Tab
AZURE_SEARCH_INDEX_NAME="boardbuddy-index"

# Azure OpenAI / AI Foundry Settings
AZURE_OPENAI_API_KEY="<your-api-key>" # From AI Foundry Deployments + Endpoint page
AZURE_OPENAI_ENDPOINT="https://boardbuddy-openai-service.cognitiveservices.azure.com/" # Example from your prompt
AZURE_OPENAI_API_VERSION="2024-12-01-preview" # Using the latest version shown in your snippet
AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-large"
AZURE_OPENAI_CHAT_DEPLOYMENT="o3-mini"
```

Once your `.env` is populated with the endpoint and API key, let me know, and we will trigger the schema creation script!
