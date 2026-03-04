# Project Requirements: BoardBuddy RAG

## 1. Project Overview & Objectives
**Goal:** Build a custom Retrieval-Augmented Generation (RAG) application to provide a plain-English conversational interface for municipal board documents (agendas, minutes, presentations, board letters).
**The Problem:** Board subject matter repeats frequently over months or years. Standard keyword searches produce excessive noise (e.g., returning a 2021 preliminary reading instead of a 2024 final adoption). 
**The Solution:** A unified RAG architecture utilizing **Semantic Chunking**, **Hybrid Search**, **Semantic Reranking**, and strict **Metadata Filtering** to retrieve exact contextual documents before passing them to the LLM. 

This custom solution bypasses Microsoft Copilot Studio restrictions in an M365 GCC tenant by extracting data directly via APIs and keeping processing within a secure Azure AI Foundry compliance boundary.

## 2. Architecture & Tech Stack
*   **Language:** Python 3.11+
*   **Backend / API:** FastAPI
*   **Orchestration Framework:** LlamaIndex (preferred for heavy data ingestion/chunking) or LangChain
*   **LLM & Embeddings:** Azure AI Foundry 
    *   Models: `text-embedding-3-small` or `text-embedding-ada-002` for vectors; `gpt-4o` for chat.
*   **Vector Database:** Azure AI Search (Unified index configured for Hybrid Search + Semantic Ranker)
*   **Frontend UI:** Streamlit or Chainlit (for rapid deployment of a chat UI with citation support)
*   **Authentication:** MSAL (Microsoft Authentication Library) for Entra ID app auth
*   **Document Parsing:** `PyMuPDF` (fitz) or `pdfplumber` for PDF text extraction

## 3. Data Sources & Integration Strategy
We are unifying two distinct data sources into a single Azure AI Search index.

### Source A: Modern Data (Granicus Legistar)
*   **API:** Granicus Legistar REST API (`https://webapi.legistar.com/v1/mwdh2o`)
*   **Endpoints to target:**
    *   `/Matters`: Legislative items, statuses, and sponsors.
    *   `/Events`: Meeting dates and agendas.
    *   `/Attachments`: Downloadable PDF/Word documents associated with matters.
*   **Action:** Extract JSON metadata, download attached PDFs, extract text, and chunk.

### Source B: Historical Data 2021 & Older (SharePoint)
*   **API:** Microsoft Graph API (`graph.microsoft.com` or `graph.microsoft.us` if routing through GCC High)
*   **Auth:** Entra ID Application using MSAL Client Credentials flow (`Sites.Read.All`, `Files.Read.All`).
*   **Action:** Traverse specific SharePoint Document Libraries, download PDFs/DOCX, extract text, deduce metadata from file properties, and chunk.

## 4. Data Schema & Metadata Strategy (CRITICAL)
To solve the "search noise" problem, the ingestion pipeline MUST extract and attach the following metadata to every chunk before inserting it into Azure AI Search. The index must be configured to allow filtering on these fields:

*   `id` (String, Key): Unique chunk identifier.
*   `chunk_text` (String, Searchable): The actual extracted text.
*   `content_vector` (Collection(Edm.Single), Searchable): The vector embedding.
*   `source_system` (String, Filterable, Facetable): "SharePoint" or "Legistar".
*   `document_type` (String, Filterable, Facetable): e.g., "Agenda", "Minutes", "Board Letter", "Presentation", "Attachment".
*   `matter_status` (String, Filterable): e.g., "Adopted", "Introduced", "Draft".
*   `year` (Int32, Filterable, Sortable): The year the document was published.
*   `date_published` (DateTimeOffset, Filterable, Sortable): Exact meeting/document date.
*   `title` (String, Searchable): Document title or matter name.
*   `source_url` (String, Retrievable): Direct deep link to the source document for UI citations.

## 5. RAG Pipeline Logic (The "Noise" Fixer)
When a user submits a plain-English query via the frontend:
1.  **Query Analysis (Pre-filtering):** Use a lightweight LLM call to extract dates, document types, or statuses from the user's prompt (e.g., *"What did we decide about the zoning budget in 2023?"* -> Extract filter: `year eq 2023`).
2.  **Hybrid Retrieval:** Execute a Hybrid Search against Azure AI Search using the vectorized prompt AND keyword BM25 match, applying the metadata filters extracted in Step 1.
3.  **Semantic Reranking:** Pass the retrieved results through Azure's Semantic Ranker to re-order the chunks based on actual contextual relevance to the user's question.
4.  **Generation:** Pass the top N reranked chunks to the Azure Foundry GPT-4o model with a strict system prompt to synthesize the answer.
5.  **Citation:** The LLM must be instructed to explicitly cite its sources using the `title` and `source_url`.

## 6. Implementation Phases (Agent Instructions)
**Agent:** Please execute this project methodically in the following phases. Wait for user review and confirmation before moving to the next phase. Keep the code modular. Rely on a `.env` file for all credentials.

### Phase 1: Scaffolding & Setup
*   Initialize Python environment and `requirements.txt`.
*   Create a `.env.example` file mapping out all required environment variables (Azure keys, Entra ID tenant/client IDs, Legistar Client Name).
*   Create the basic directory structure (`/ingestion`, `/api`, `/ui`).

### Phase 2: Azure AI Search Setup (`/ingestion/indexer.py`)
*   Write a setup script to programmatically create the Azure AI Search index with the correct vector profiles, semantic configurations, and metadata schema defined in Section 4.

### Phase 3: Granicus Legistar Ingestion (`/ingestion/legistar_worker.py`)
*   Write an idempotent script to query the Legistar Web API.
*   Fetch a small test batch of Matters and their Attachments.
*   Download PDFs, extract text, chunk the text semantically (e.g., 800 tokens, 150 overlap), embed using Azure AI Foundry, and push to the index.

### Phase 4: SharePoint Ingestion (`/ingestion/sharepoint_worker.py`)
*   Write a script using `msal` to authenticate with Microsoft Graph API.
*   Target a specific Drive/Site, fetch files, extract text, chunk, embed, and push to the index. Include robust error handling and Graph API rate-limit backoff handling.

### Phase 5: FastAPI RAG Backend (`/api/main.py`)
*   Build the `/chat` endpoint.
*   Implement the orchestrator handling Query Analysis, Hybrid Retrieval, Semantic Reranking, and LLM Generation.

### Phase 6: Frontend UI (`/ui/app.py`)
*   Build the Streamlit or Chainlit application.
*   Connect it to the FastAPI backend.
*   Render the chat interface, streaming text, and clickable source citations. Include an optional sidebar for users to manually force metadata filters (e.g., "Search only 2024").