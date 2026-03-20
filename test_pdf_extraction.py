import asyncio
from ingestion.legistar_bulk_load import download_attachment, extract_text_from_pdf_bytes

url = "https://mwdh2o.legistar1.com/mwdh2o/attachments/f4be8fa9-5c2b-43e0-bc57-ab80ffcf6a73.pdf"
print(f"Downloading {url}...")
pdf_bytes = download_attachment(url)

if pdf_bytes:
    print(f"Downloaded {len(pdf_bytes)} bytes. Extracting text...")
    text = extract_text_from_pdf_bytes(pdf_bytes)
    print(f"Extracted {len(text)} characters of text.")
    print("First 200 chars:")
    print(text[:200])
else:
    print("Failed to download PDF.")
