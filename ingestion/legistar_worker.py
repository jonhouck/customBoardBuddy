import os
import requests
import tiktoken
import fitz  # PyMuPDF
import uuid
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
    """Extract text from PDF bytes using PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text.strip()

def chunk_text(text: str, model_name="cl100k_base", chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Chunk text semantically using tiktoken."""
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
    """Generate vector embedding for a given text."""
    response = client.embeddings.create(input=[text], model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
    return response.data[0].embedding

def fetch_matters(limit: int = 5) -> list[dict]:
    """Fetch recent matters from Legistar API."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Matters"
    # Just a simple top query for testing
    params = {"$top": limit, "$orderby": "MatterIntroDate desc"}
    print(f"Fetching {limit} matters from Legistar API...")
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def fetch_matter_attachments(matter_id: int) -> list[dict]:
    """Fetch attachments metadata for a specific matter."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Matters/{matter_id}/Attachments"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return []

def download_attachment(url: str) -> bytes | None:
    """Download attachment byte stream."""
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    return None

def process_legistar_matters(limit: int = 2):
    """Main workflow to process Granicus Legistar matters."""
    matters = fetch_matters(limit=limit)
    if not matters:
        print("No matters found.")
        return

    openai_client = get_openai_client()
    search_client = get_search_client()

    documents_to_upload = []

    for matter in matters:
        matter_id = matter.get("MatterId")
        title = matter.get("MatterTitle", "Untitled Matter")
        status = matter.get("MatterStatusName", "Unknown")
        intro_date_str = matter.get("MatterIntroDate")
        
        # Parse date and convert to ISO 8601 UTC with format required by Azure Search: YYYY-MM-DDThh:mm:ssZ
        try:
            if intro_date_str:
                 # Will parse "2025-01-14T00:00:00" natively
                 dt = parser.parse(intro_date_str)
                 # Ensure timezone aware
                 if dt.tzinfo is None:
                     dt = dt.replace(tzinfo=timezone.utc)
                 
                 # format using isoformat but replace +00:00 with Z
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
            link = attachment.get("MatterAttachmentFileName") # Often acts as a URL depending on configuration
            
            if not link or not str(link).endswith(".pdf"):
                print(f"  Skipping non-pdf attachment: {attachment_name}")
                continue
                
            print(f"  Downloading & chunking: {attachment_name}...")
            # For this simple script, we assume the FileName holds the URL or we construct it.
            # In Legistar, "MatterAttachmentFileName" is sometimes a direct URL, or we might need "MatterAttachmentLink"
            download_url = attachment.get("MatterAttachmentFileName")
            
            # Note: Often "MatterAttachmentLink" or a constructed URL is used. 
            # We'll try MatterAttachmentFileName if it looks like http, otherwise constructing
            if not str(download_url).startswith("http"):
                  continue # Skip if we can't figure out the URL easily in this prototype

            pdf_bytes = download_attachment(download_url)
            if not pdf_bytes:
                continue

            text = extract_text_from_pdf_bytes(pdf_bytes)
            if not text:
                continue

            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                # Only use first 500 chars of title to stay safe
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
        print(f"Uploading {len(documents_to_upload)} chunks to Azure Search...")
        try:
            results = search_client.upload_documents(documents=documents_to_upload)
            print(f"Uploaded {len(results)} chunks successfully.")
        except Exception as e:
            print(f"Error uploading documents: {e}")
    else:
        print("No chunks to upload.")

if __name__ == "__main__":
    import argparse
    parser_arg = argparse.ArgumentParser(description="Ingest from Legistar")
    parser_arg.add_argument("--limit", type=int, default=2, help="Number of matters to fetch for testing")
    args = parser_arg.parse_args()
    
    process_legistar_matters(limit=args.limit)
