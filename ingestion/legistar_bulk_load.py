import os
import requests
import tiktoken
import fitz  # PyMuPDF
import uuid
import time
from datetime import datetime, timezone
from dateutil import parser
from dotenv import load_dotenv

from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

load_dotenv()

# Legistar Settings
LEGISTAR_CLIENT_NAME = os.getenv("LEGISTAR_CLIENT_NAME", "mwdh2o")
LEGISTAR_API_BASE_URL = os.getenv("LEGISTAR_API_BASE_URL", "https://webapi.legistar.com/v1")

# Azure Search Settings
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

# Azure OpenAI Settings
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

def get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )

def get_search_client() -> SearchClient:
    credential = AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
    return SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=AZURE_SEARCH_INDEX_NAME, credential=credential)

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text.strip()

def chunk_text(text: str, model_name="cl100k_base", chunk_size: int = 800, overlap: int = 150) -> list[str]:
    encoder = tiktoken.get_encoding(model_name)
    tokens = encoder.encode(text)
    chunks = []
    i = 0
    while i < len(tokens):
        chunk_tokens = tokens[i:i + chunk_size]
        chunks.append(encoder.decode(chunk_tokens))
        i += chunk_size - overlap
    return chunks

def generate_embedding(text: str, client: AzureOpenAI) -> list[float]:
    response = client.embeddings.create(input=[text], model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
    return response.data[0].embedding

def get_indexed_urls(search_client: SearchClient) -> set[str]:
    """Fetch all source_urls currently indexed from Legistar to avoid reprocessing."""
    indexed_urls = set()
    try:
        # Paginating through all results fetching just the source_url
        results = search_client.search(
            search_text="*",
            filter="source_system eq 'Legistar'",
            select=["source_url"]
        )
        for doc in results:
            url = doc.get("source_url")
            if url:
                indexed_urls.add(url)
        print(f"Loaded {len(indexed_urls)} already-indexed URLs to skip.")
    except Exception as e:
        print(f"Error fetching indexed URLs (index might be empty): {e}")
    return indexed_urls

def fetch_matters_paginated(skip: int = 0, top: int = 50) -> list[dict]:
    """Fetch matters from Legistar API with pagination."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Matters"
    # Order descending to get newest first, limit by skip and top
    params = {"$top": top, "$skip": skip, "$orderby": "MatterIntroDate desc"}
    print(f"Fetching {top} matters starting at {skip} from Legistar API...")
    
    # Simple backoff for rate limits
    for attempt in range(3):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                sleep_time = (attempt + 1) * 5
                print(f"Rate limited. Waiting {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print(f"Error fetching matters: {e}")
                break
        except Exception as e:
             print(f"Error fetching matters: {e}")
             break
    return []

def fetch_matter_attachments(matter_id: int) -> list[dict]:
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Matters/{matter_id}/Attachments"
    for attempt in range(3):
        try:
            # Set a timeout and handle potential connection drops
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                sleep_time = (attempt + 1) * 5
                print(f"  Rate limited fetching attachments. Waiting {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                break
        except Exception as e:
            print(f"  Error fetching attachments (attempt {attempt+1}): {e}")
            time.sleep(2)
    return []

def download_attachment(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            print(f"Download attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None

def process_legistar_bulk(max_matters: int = 500, batch_size: int = 50):
    """Main workflow to process Granicus Legistar matters in bulk."""
    openai_client = get_openai_client()
    search_client = get_search_client()

    # Load previously indexed URLs to skip them
    indexed_urls = get_indexed_urls(search_client)

    total_processed = 0
    skip = 0

    while total_processed < max_matters:
        matters = fetch_matters_paginated(skip=skip, top=batch_size)
        if not matters:
            print("No more matters found or API error limit reached.")
            break

        documents_to_upload = []

        for matter in matters:
            matter_id = matter.get("MatterId")
            title = matter.get("MatterTitle", "Untitled Matter")
            status = matter.get("MatterStatusName", "Unknown")
            intro_date_str = matter.get("MatterIntroDate")
            
            try:
                if intro_date_str:
                     dt = parser.parse(intro_date_str)
                     if dt.tzinfo is None:
                         dt = dt.replace(tzinfo=timezone.utc)
                     date_published = dt.isoformat().replace("+00:00", "Z")
                     year = dt.year
                else:
                     date_published = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                     year = datetime.now(timezone.utc).year
            except Exception:
                date_published = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                year = datetime.now(timezone.utc).year

            print(f"Processing Matter ID: {matter_id} - {title[:50]}...")
            attachments = fetch_matter_attachments(matter_id)
            print(f"  Found {len(attachments)} attachments.")
            
            for attachment in attachments:
                attachment_name = attachment.get("MatterAttachmentName", "Unknown Attachment")
                file_name = attachment.get("MatterAttachmentFileName", "")
                download_url = attachment.get("MatterAttachmentHyperlink", "")
                
                if not str(file_name).lower().endswith(".pdf"):
                    continue
                    
                if not str(download_url).startswith("http"):
                    continue 

                # Idempotency check: skip if we've already indexed this exact document
                if download_url in indexed_urls:
                    print(f"  Skipping already-indexed attachment: {attachment_name}")
                    continue

                pdf_bytes = download_attachment(download_url)
                if not pdf_bytes:
                    continue

                text = extract_text_from_pdf_bytes(pdf_bytes)
                if not text:
                    continue

                chunks = chunk_text(text)
                for chunk in chunks:
                    safe_title = f"{title[:450]} - {attachment_name}" 
                    
                    doc = {
                        "id": str(uuid.uuid4()),
                        "chunk_text": chunk,
                        "content_vector": generate_embedding(chunk, openai_client),
                        "source_system": "Legistar",
                        "document_type": "Attachment",
                        "matter_status": status,
                        "year": year,
                        "date_published": date_published,
                        "title": safe_title,
                        "source_url": download_url
                    }
                    documents_to_upload.append(doc)

        if documents_to_upload:
            print(f"Uploading {len(documents_to_upload)} chunks to Azure Search from batch...")
            try:
                search_client.upload_documents(documents=documents_to_upload)
                print("Uploaded successfully.")
            except Exception as e:
                print(f"Error uploading documents: {e}")
        else:
            print("No chunks to upload from this batch.")

        total_processed += len(matters)
        skip += len(matters)
        print(f"Total matters processed so far: {total_processed}")

    print(f"Bulk load complete. Processed {total_processed} matters.")

if __name__ == "__main__":
    import argparse
    parser_arg = argparse.ArgumentParser(description="Bulk ingest from Legistar")
    parser_arg.add_argument("--max_matters", type=int, default=1000, help="Maximum number of matters to process across all batches")
    parser_arg.add_argument("--batch_size", type=int, default=50, help="Number of matters to fetch per API query")
    args = parser_arg.parse_args()
    
    process_legistar_bulk(max_matters=args.max_matters, batch_size=args.batch_size)
