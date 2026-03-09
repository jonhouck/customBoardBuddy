import os
import time
import requests
import tiktoken
import fitz  # PyMuPDF
import uuid
from datetime import datetime, timezone
from dateutil import parser
from dotenv import load_dotenv

import openai
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

def get_indexed_urls(search_client: SearchClient) -> set[str]:
    """Fetch all source_urls currently indexed from Legistar to avoid reprocessing."""
    indexed_urls = set()
    try:
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

def get_latest_watermark(search_client: SearchClient, is_event: bool = False) -> str | None:
    """Check Azure AI Search for the most recently published Legistar document."""
    filter_str = "source_system eq 'Legistar'"
    if is_event:
        filter_str += " and document_type ne 'Attachment'"
    else:
        filter_str += " and document_type eq 'Attachment'"
        
    try:
        results = search_client.search(
            search_text="*",
            filter=filter_str,
            order_by=["date_published desc"],
            top=1,
            select=["date_published"]
        )
        for doc in results:
            return doc.get("date_published")
    except Exception as e:
        print(f"Error fetching watermark: {e}")
    return None

def fetch_matters(watermark: str | None = None, limit: int = 5) -> list[dict]:
    """Fetch matters from Legistar API, optionally newer than a watermark date."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Matters"
    params = {"$top": limit, "$orderby": "MatterIntroDate desc"}
    if watermark:
        legistar_date = watermark.replace("Z", "")
        params["$filter"] = f"MatterIntroDate gt datetime'{legistar_date}'"
        print(f"Fetching matters newer than {legistar_date} from Legistar API...")
    else:
        print(f"Fetching {limit} latest matters from Legistar API...")
        
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

def fetch_events(watermark: str | None = None, limit: int = 5) -> list[dict]:
    """Fetch events from Legistar API, optionally newer than a watermark date."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Events"
    params = {"$top": limit, "$orderby": "EventDate desc"}
    if watermark:
        legistar_date = watermark.replace("Z", "")
        params["$filter"] = f"EventDate gt datetime'{legistar_date}'"
        print(f"Fetching events newer than {legistar_date} from Legistar API...")
    else:
        print(f"Fetching {limit} latest events from Legistar API...")
        
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
                print(f"Error fetching events: {e}")
                break
        except Exception as e:
             print(f"Error fetching events: {e}")
             break
    return []

def fetch_matter_attachments(matter_id: int) -> list[dict]:
    """Fetch attachments metadata for a specific matter."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Matters/{matter_id}/Attachments"
    for attempt in range(3):
        try:
            # Set a timeout and handle potential connection drops
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                import time
                sleep_time = (attempt + 1) * 5
                print(f"  Rate limited fetching attachments. Waiting {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                break
        except Exception as e:
            import time
            print(f"  Error fetching attachments (attempt {attempt+1}): {e}")
            time.sleep(2)
    return []

def fetch_event_items(event_id: int) -> list[dict]:
    """Fetch event items (votes and actions) for a specific event."""
    url = f"{LEGISTAR_API_BASE_URL}/{LEGISTAR_CLIENT_NAME}/Events/{event_id}/EventItems"
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                import time
                sleep_time = (attempt + 1) * 5
                print(f"  Rate limited fetching items. Waiting {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                break
        except Exception as e:
            import time
            print(f"  Error fetching event items (attempt {attempt+1}): {e}")
            time.sleep(2)
    return []

def download_attachment(url: str) -> bytes | None:
    """Download attachment byte stream."""
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

def process_legistar_events(limit: int = 2):
    """Main workflow to process Granicus Legistar events."""
    openai_client = get_openai_client()
    search_client = get_search_client()

    watermark = get_latest_watermark(search_client, is_event=True)
    if watermark:
        print(f"Event High-water mark found: {watermark}")
    else:
        print("No Event high-water mark found. Fetching latest events.")

    events = fetch_events(watermark=watermark, limit=limit)
    if not events:
        print("No new events found.")
        return

    indexed_urls = get_indexed_urls(search_client)
    documents_to_upload = []

    for event in events:
        event_id = event.get("EventId")
        title = event.get("EventBodyName", "Unknown Committee")
        intro_date_str = event.get("EventDate")
        
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

        print(f"Processing Event ID: {event_id} - {title[:50]}...")
        
        files_to_process = []
        
        agenda_file = event.get("EventAgendaFile")
        if agenda_file:
            files_to_process.append(("Agenda", agenda_file))
            
        minutes_file = event.get("EventMinutesFile")
        if minutes_file:
            files_to_process.append(("Minutes", minutes_file))
            
        for doc_label, download_url in files_to_process:
            if not str(download_url).startswith("http"):
                continue
            
            if download_url in indexed_urls:
                print(f"    Skipped: {doc_label} is already indexed.")
                continue
            
            print(f"    Downloading: {doc_label}...")
            pdf_bytes = download_attachment(download_url)
            if not pdf_bytes:
                print(f"    Error: Failed to download {doc_label}")
                continue

            print(f"    Extracting text from {doc_label}...")
            text = extract_text_from_pdf_bytes(pdf_bytes)
            if not text:
                print(f"    Warning: No text extracted from {doc_label}")
                continue

            chunks = chunk_text(text)
            print(f"    Chunking complete: {len(chunks)} chunks generated.")
            for chunk in chunks:
                safe_title = f"{title[:450]} - {doc_label}" 
                
                doc = {
                    "id": str(uuid.uuid4()),
                    "chunk_text": chunk,
                    "content_vector": generate_embedding(chunk, openai_client),
                    "source_system": "Legistar",
                    "document_type": f"Event {doc_label}",
                    "matter_status": "Final",
                    "year": year,
                    "date_published": date_published,
                    "title": safe_title,
                    "source_url": download_url
                }
                documents_to_upload.append(doc)

            # Process Event Items for Actions, Votes & Attachments
            event_url = f"https://mwdh2o.legistar.com/MeetingDetail.aspx?ID={event_id}&GUID={event.get('EventGuid', '')}"
            
            print(f"    Fetching EventItems for votes and attachments...")
            event_items = fetch_event_items(event_id)
            if event_items:
                vote_texts = []
                for item in event_items:
                    # 1. Process EventItem Attachments (e.g. Board Letters, Presentations)
                    attachments = item.get("EventItemMatterAttachments", [])
                    if attachments:
                        for attachment in attachments:
                            attachment_name = attachment.get("MatterAttachmentName", "Unknown Attachment")
                            file_name = attachment.get("MatterAttachmentFileName", "")
                            download_url = attachment.get("MatterAttachmentHyperlink", "")
                            
                            if not str(file_name).lower().endswith(".pdf") or not str(download_url).startswith("http"):
                                continue
                                
                            if download_url in indexed_urls:
                                print(f"      Skipped EventItem Attachment: {attachment_name} is already indexed.")
                                continue
                                
                            print(f"      Downloading EventItem Attachment: {attachment_name}...")
                            pdf_bytes = download_attachment(download_url)
                            if not pdf_bytes:
                                continue
                                
                            text = extract_text_from_pdf_bytes(pdf_bytes)
                            if not text:
                                continue
                                
                            chunks = chunk_text(text)
                            print(f"      Chunking complete: {len(chunks)} chunks generated.")
                            safe_title = f"{title[:400]} - {attachment_name}" 
                            for chunk in chunks:
                                doc = {
                                    "id": str(uuid.uuid4()),
                                    "chunk_text": chunk,
                                    "content_vector": generate_embedding(chunk, openai_client),
                                    "source_system": "Legistar",
                                    "document_type": "Event Attachment",
                                    "matter_status": "Final",
                                    "year": year,
                                    "date_published": date_published,
                                    "title": safe_title,
                                    "source_url": download_url
                                }
                                documents_to_upload.append(doc)

                    # 2. Process Votes
                    item_title = item.get("EventItemTitle", "")
                    action_name = item.get("EventItemActionName", "No Action")
                    passed = item.get("EventItemPassedFlagName", "")
                    roll_call = item.get("EventItemRollCallFlag", 0)
                    
                    if item_title and action_name:
                        vote_text = f"Agenda Item: {item_title}\nAction: {action_name}"
                        if passed:
                            vote_text += f"\nPassed: {passed}"
                        if roll_call:
                            vote_text += f"\nRoll Call Done"
                        vote_texts.append(vote_text)
                
                # Only insert votes if they haven't been indexed for this event
                if event_url in indexed_urls:
                    print(f"    Skipped: Votes & Actions already indexed.")
                elif vote_texts:
                    combined_votes = "\n\n---\n\n".join(vote_texts)
                    chunks = chunk_text(combined_votes)
                    print(f"    Chunking complete: {len(chunks)} chunks generated from votes.")
                    safe_title = f"{title[:450]} - Votes & Actions" 
                        
                    for chunk in chunks:
                        doc = {
                            "id": str(uuid.uuid4()),
                            "chunk_text": chunk,
                            "content_vector": generate_embedding(chunk, openai_client),
                            "source_system": "Legistar",
                            "document_type": "Event Votes & Actions",
                            "matter_status": "Final",
                            "year": year,
                            "date_published": date_published,
                            "title": safe_title,
                            "source_url": event_url
                        }
                        documents_to_upload.append(doc)
                else:
                    print(f"    No actionable votes found.")
            else:
                print(f"    No EventItems found.")

    if documents_to_upload:
        print(f"Uploading {len(documents_to_upload)} event chunks to Azure Search...")
        try:
            results = search_client.upload_documents(documents=documents_to_upload)
            print(f"Uploaded {len(results)} chunks successfully.")
        except Exception as e:
            print(f"Error uploading documents: {e}")
    else:
        print("No event chunks to upload.")

def process_legistar_matters(limit: int = 2):
    """Main workflow to process Granicus Legistar matters."""
    openai_client = get_openai_client()
    search_client = get_search_client()

    watermark = get_latest_watermark(search_client, is_event=False)
    if watermark:
        print(f"Matter High-water mark found: {watermark}")
    else:
        print("No Matter high-water mark found. Fetching latest matters.")

    matters = fetch_matters(watermark=watermark, limit=limit)
    if not matters:
        print("No new matters found.")
        return

    indexed_urls = get_indexed_urls(search_client)
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
            file_name = attachment.get("MatterAttachmentFileName", "")
            download_url = attachment.get("MatterAttachmentHyperlink", "")
            
            if not str(file_name).lower().endswith(".pdf"):
                print(f"  Skipping non-pdf attachment: {attachment_name}")
                continue
                
            if not str(download_url).startswith("http"):
                print(f"  Skipping attachment, no valid download link: {attachment_name}")
                continue

            if download_url in indexed_urls:
                print(f"  Skipped: {attachment_name} is already indexed.")
                continue

            print(f"  Downloading & chunking: {attachment_name}...")

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
    parser_arg.add_argument("--limit", type=int, default=2, help="Number of items to fetch for testing")
    args = parser_arg.parse_args()
    
    print("--- Processing Worker Events ---")
    process_legistar_events(limit=args.limit)
    print("\n--- Processing Worker Matters ---")
    process_legistar_matters(limit=args.limit)
