# BoardBuddy Local Deployment Guide

This guide explains how to launch the complete BoardBuddy RAG application locally to verify functionality.

## Prerequisites
1. **Python Environment Activated:** Ensure your virtual environment is active (e.g., `source .venv/bin/activate`).
2. **Environment Variables:** Verify your `.env` file is fully populated, especially with the new `UI_CLIENT_ID`, `UI_CLIENT_SECRET`, and `UI_REDIRECT_URI` for Entra ID UI authentication.

## Launching the Application

BoardBuddy consists of two separate services that must run simultaneously. You will need **two separate terminal windows**.

### Terminal 1: Start the FastAPI Backend
This service handles the orchestration, vector search, and LLM communication.

1. Open a new terminal and navigate to the `customBoardBuddy` directory.
2. Activate your virtual environment.
3. Run the following command:
   ```bash
   uvicorn api.main:app --reload
   ```
4. Confirm it is running by looking for `Application startup complete.` in the console payload. It will normally bind to `http://127.0.0.1:8000`.

### Terminal 2: Start the Streamlit Frontend UI
This service runs the user interface and handles the initial Entra ID login.

1. Open a second terminal and navigate to the `customBoardBuddy` directory.
2. Activate your virtual environment.
3. Run the following command:
   ```bash
   streamlit run ui/app.py
   ```
4. Streamlit will automatically open a new browser tab pointing to `http://localhost:8501`.

## Testing the Application

1. **Authentication:** When you visit `http://localhost:8501`, you should be prompted to "Sign in with Microsoft". Proceed through the Entra ID login using your MWD credentials.
2. **The Interface:** Once authenticated, you will see the BoardBuddy chat interface styled with MWD branding.
3. **Querying Data:** 
   * **Note on Async Indexing:** Because your bulk load script (`ingestion.legistar_bulk_load`) is currently running, the Azure AI Search Index is actively being populated. 
   * **Live Search:** You **do not** need to wait for the scripts to finish to test the app. Azure AI Search makes documents available for querying the moment they are indexed. You can ask questions about the Legistar matters that have already been processed in the partial run.
   * Try asking a general question like: *"Can you summarize recent matters regarding water conservation?"*
4. **Citations:** Verify that the AI's response includes clickable citations that link back to the source documents.

## Running Background Ingestion (For Reference)
If you need to run or resume data ingestion in the background in a third terminal:
- **Legistar:** `python -m ingestion.legistar_bulk_load --max_events 5000 --max_matters 5000 --batch_size 50`
- **SharePoint:** `python -m ingestion.sharepoint_bulk_load --max_files 1000 --batch_size 50`
