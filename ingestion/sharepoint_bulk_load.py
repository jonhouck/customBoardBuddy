import os
import requests
import tiktoken
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import uuid
import time
from datetime import datetime, timezone
from dateutil import parser
from dotenv import load_dotenv

import msal
import openai
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

load_dotenv()

# Azure AD / MSAL Settings
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
GRAPH_AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# SharePoint Settings
SHAREPOINT_SITE_ID = os.getenv("SHAREPOINT_SITE_ID")
SHAREPOINT_DRIVE_ID = os.getenv("SHAREPOINT_DRIVE_ID")

# Azure Search Settings
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

# Azure OpenAI Settings
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

def get_graph_token() -> str | None:
    """Acquire a Microsoft Graph API access token using MSAL Confidential Client."""
    if not all([AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET]):
        print("Error: Missing Entra ID credentials in environment variables.")
        return None
        
    app = msal.ConfidentialClientApplication(
        AZURE_CLIENT_ID,
        authority=GRAPH_AUTHORITY,
        client_credential=AZURE_CLIENT_SECRET,
    )
    
    result = app.acquire_token_silent(GRAPH_SCOPE, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        
    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"Error acquiring Graph token: {result.get('error')} - {result.get('error_description')}")
        return None

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
    """Extract text from PDF bytes using PyMuPDF, with OCR fallback for scanned images."""
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
            
        # If extraction is virtually empty (e.g. less than 15 valid characters), it's likely a scan
        if len(text.strip()) < 15:
            print("    Scan detected. Falling back to local OCR...")
            ocr_text = ""
            for i, page in enumerate(doc):
                # Render page to an image
                pix = page.get_pixmap(dpi=150) # Use 150 DPI for reasonable speed/readability balance
                # Convert Pixmap to PIL Image
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                # Extract text mathematically from image
                page_text = pytesseract.image_to_string(img)
                ocr_text += page_text + "\n"
            text = ocr_text
            
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
    """Generate vector embedding for a given text with retry backoff."""
    for attempt in range(5):
        try:
            response = client.embeddings.create(input=[text], model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
            return response.data[0].embedding
        except openai.RateLimitError:
            sleep_time = (2 ** attempt) + 2  # 3, 4, 6, 10, 18 seconds
            print(f"    OpenAI Rate limit reached (429). Waiting {sleep_time} seconds before retry...")
            time.sleep(sleep_time)
        except Exception as e:
            print(f"    Error generating embedding: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            
    # Final attempt that will raise the exception if it fails
    response = client.embeddings.create(input=[text], model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
    return response.data[0].embedding

def ms_graph_request(url: str, token: str) -> dict | bytes | None:
    """Execute a MS Graph request with retry backoff for rate limiting (429)."""
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(4):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                if "application/json" in response.headers.get("Content-Type", ""):
                    return response.json()
                return response.content
            elif response.status_code == 429:
                raw_retry = response.headers.get("Retry-After")
                sleep_time = int(raw_retry) if raw_retry and raw_retry.isdigit() else (attempt + 1) * 10
                print(f"Graph API rate limited (429). Waiting {sleep_time} seconds...")
                time.sleep(sleep_time)
            elif response.status_code == 404:
                print(f"Graph API 404 Not Found: {url}")
                return None
            else:
                print(f"Graph API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Request error attempt {attempt+1}: {e}")
            time.sleep(5)
    print("Maximum retries reached for MS Graph.")
    return None

def fetch_sharepoint_files_batch(token: str, url: str) -> tuple[list[dict], str | None]:
    """Fetch one page of file metadata from SharePoint Document Library."""
    data = ms_graph_request(url, token)
    if not data or not isinstance(data, dict):
        return [], None
         
    files = []
    for item in data.get("value", []):
        if "file" in item and item.get("name", "").lower().endswith(".pdf"):
            files.append(item)
            
    next_link = data.get("@odata.nextLink")
    return files, next_link

def get_indexed_urls(search_client: SearchClient) -> set[str]:
    """Fetch all source_urls currently indexed from SharePoint to avoid reprocessing."""
    indexed_urls = set()
    try:
        results = search_client.search(
            search_text="*",
            filter="source_system eq 'SharePoint'",
            select=["source_url"]
        )
        for doc in results:
            url = doc.get("source_url")
            if url:
                indexed_urls.add(url)
        print(f"Loaded {len(indexed_urls)} already-indexed SharePoint URLs to skip.")
    except Exception as e:
        print(f"Error fetching indexed URLs (index might be empty): {e}")
    return indexed_urls

def process_sharepoint_bulk(max_files: int = 1000, start_url: str | None = None):
    """Main workflow to process historical SharePoint documents in bulk."""
    
    if not SHAREPOINT_DRIVE_ID:
        print("Error: SHAREPOINT_DRIVE_ID is missing from environment.")
        return
        
    print("Acquiring Graph API Token...")
    token = get_graph_token()
    if not token:
        return

    openai_client = get_openai_client()
    search_client = get_search_client()

    indexed_urls = get_indexed_urls(search_client)

    url = start_url or f"https://graph.microsoft.com/v1.0/drives/{SHAREPOINT_DRIVE_ID}/root/search(q='.pdf')"
    total_processed = 0

    print(f"Starting bulk ingestion up to {max_files} PDF files from SharePoint drive {SHAREPOINT_DRIVE_ID} using native PDF search...")

    while url and total_processed < max_files:
        print(f"Fetching SharePoint page... (Total processed so far: {total_processed})")
        
        # Token refresh occasionally to prevent timeout on very long bulk loads
        if total_processed > 0 and total_processed % 100 == 0:
             print("Refreshing Graph API Token...")
             token = get_graph_token()
             if not token:
                 print("Failed to refresh token. Exiting.")
                 break
                 
        files, next_url = fetch_sharepoint_files_batch(token, url)
        
        if not files and next_url:
            url = next_url
            continue
        elif not files:
            print("No more PDF files found or API error limit reached.")
            break

        documents_to_upload = []

        for f in files:
            if total_processed >= max_files:
                break
                
            file_id = f.get("id")
            title = f.get("name", "Untitled")
            web_url = f.get("webUrl", f"sharepoint_{file_id}")
            
            # Idempotency check 
            if web_url in indexed_urls:
                print(f"Skipping already-indexed file: {title}")
                total_processed += 1
                continue

            # Convert createdDateTime to Azure Search format
            created_at_str = f.get("createdDateTime")
            try:
                 dt = parser.parse(created_at_str)
                 if dt.tzinfo is None:
                     dt = dt.replace(tzinfo=timezone.utc)
                 date_published = dt.isoformat().replace("+00:00", "Z")
                 year = dt.year
            except Exception:
                 date_published = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                 year = datetime.now(timezone.utc).year

            print(f"Processing File ID: {file_id} - {title[:50]}...")
            
            # Fetch actual file content bytes
            download_url = f"https://graph.microsoft.com/v1.0/drives/{SHAREPOINT_DRIVE_ID}/items/{file_id}/content"
            pdf_bytes = ms_graph_request(download_url, token)
            
            if not pdf_bytes or isinstance(pdf_bytes, dict):
                print(f"  Failed to download bytes for {title}.")
                total_processed += 1
                continue

            print("  Extracting text...")
            text = extract_text_from_pdf_bytes(pdf_bytes)
            if not text:
                print("  No text extracted (scanned PDF or empty).")
                total_processed += 1
                continue

            chunks = chunk_text(text)
            print(f"  Generated {len(chunks)} chunks.")
            
            for chunk in chunks:
                doc = {
                    "id": str(uuid.uuid4()),
                    "chunk_text": chunk,
                    "content_vector": generate_embedding(chunk, openai_client),
                    "source_system": "SharePoint",
                    "document_type": "Historical Document",
                    "matter_status": "Unknown", 
                    "year": year,
                    "date_published": date_published,
                    "title": title[:500],
                    "source_url": web_url
                }
                documents_to_upload.append(doc)
                
            total_processed += 1

        if documents_to_upload:
            print(f"Uploading {len(documents_to_upload)} chunks to Azure Search from batch...")
            try:
                batch_limit = 500
                for i in range(0, len(documents_to_upload), batch_limit):
                    batch = documents_to_upload[i:i + batch_limit]
                    search_client.upload_documents(documents=batch)
                print("Uploaded successfully.")
            except Exception as e:
                print(f"Error uploading documents: {e}")
        else:
            print("No chunks to upload from this batch.")

        url = next_url

    print(f"Bulk load complete. Processed {total_processed} files.")

if __name__ == "__main__":
    import argparse
    parser_arg = argparse.ArgumentParser(description="Bulk ingest historical documents from SharePoint")
    parser_arg.add_argument("--max_files", type=int, default=1000, help="Maximum number of files to process")
    args = parser_arg.parse_args()
    
    process_sharepoint_bulk(max_files=args.max_files)
