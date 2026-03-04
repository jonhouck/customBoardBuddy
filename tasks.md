# BoardBuddy RAG Critical Path - Tasks List

- [x] **Phase 1: Scaffolding & Setup**
  - [x] Initialize Python environment and `requirements.txt`
  - [x] Create `.env.example` file mapping out all required environment variables
  - [x] Create basic directory structure (`/ingestion`, `/api`, `/ui`)
- [ ] **Phase 2: Azure AI Search Setup**
  - [ ] Write setup script for Azure AI Search index (`/ingestion/indexer.py`)
- [ ] **Phase 3: Granicus Legistar Ingestion**
  - [ ] Write script to query Legistar Web API (`/ingestion/legistar_worker.py`)
  - [ ] Chunk, embed, and push data to index
- [ ] **Phase 4: SharePoint Ingestion**
  - [ ] Write script using `msal` to authenticate with MS Graph API (`/ingestion/sharepoint_worker.py`)
  - [ ] Chunk, embed, and push SharePoint data to index
- [ ] **Phase 5: FastAPI RAG Backend**
  - [ ] Build `/chat` endpoint and orchestration (`/api/main.py`)
- [ ] **Phase 6: Frontend UI**
  - [ ] Build Streamlit/Chainlit application (`/ui/app.py`)
