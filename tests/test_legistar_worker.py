
from unittest.mock import patch, MagicMock
from ingestion.legistar_worker import (
    chunk_text,
    extract_text_from_pdf_bytes,
    fetch_matters,
    fetch_matter_attachments,
    process_legistar_matters
)

def test_chunk_text():
    # Generate some dummy text
    text = "word " * 1000
    # chunk size 800, overlap 150
    chunks = chunk_text(text, chunk_size=800, overlap=150)
    assert len(chunks) > 0
    assert len(chunks[0].split()) <= 1000  # rough check

@patch('ingestion.legistar_worker.fitz.open')
def test_extract_text_from_pdf_bytes(mock_fitz_open):
    # Setup mock
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Test PDF Content"
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    text = extract_text_from_pdf_bytes(b"dummy pdf bytes")
    assert "Test PDF Content" in text

@patch('ingestion.legistar_worker.requests.get')
def test_fetch_matters(mock_get):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = [{"MatterId": 123, "MatterTitle": "Test Matter"}]
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    matters = fetch_matters(limit=1)
    assert len(matters) == 1
    assert matters[0]["MatterId"] == 123

@patch('ingestion.legistar_worker.requests.get')
def test_fetch_matter_attachments(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = [{"MatterAttachmentId": 456, "MatterAttachmentFileName": "http://example.com/test.pdf"}]
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    attachments = fetch_matter_attachments(123)
    assert len(attachments) == 1
    assert attachments[0]["MatterAttachmentId"] == 456

@patch('ingestion.legistar_worker.get_search_client')
@patch('ingestion.legistar_worker.get_openai_client')
@patch('ingestion.legistar_worker.fetch_matters')
@patch('ingestion.legistar_worker.fetch_matter_attachments')
@patch('ingestion.legistar_worker.download_attachment')
@patch('ingestion.legistar_worker.extract_text_from_pdf_bytes')
def test_process_legistar_matters(
    mock_extract, mock_download, mock_attachments, mock_matters, mock_openai, mock_search
):
    # Setup mocks
    mock_matters.return_value = [
        {"MatterId": 1, "MatterTitle": "Matter 1", "MatterStatusName": "Adopted", "MatterIntroDate": "2024-05-01T00:00:00"}
    ]
    mock_attachments.return_value = [
        {"MatterAttachmentName": "Doc 1", "MatterAttachmentFileName": "http://example.com/1.pdf"}
    ]
    mock_download.return_value = b"pdfbytes"
    mock_extract.return_value = "Extracted text content for chunking."

    # Mock Azure OpenAI client
    mock_openai_instance = MagicMock()
    mock_openai_response = MagicMock()
    mock_openai_data = MagicMock()
    mock_openai_data.embedding = [0.1, 0.2, 0.3]
    mock_openai_response.data = [mock_openai_data]
    mock_openai_instance.embeddings.create.return_value = mock_openai_response
    mock_openai.return_value = mock_openai_instance

    # Mock Azure Search client
    mock_search_instance = MagicMock()
    mock_search.return_value = mock_search_instance

    process_legistar_matters(limit=1)

    # Verify search upload was called
    mock_search_instance.upload_documents.assert_called_once()
    uploaded_docs = mock_search_instance.upload_documents.call_args[1]["documents"]
    assert len(uploaded_docs) == 1
    assert uploaded_docs[0]["source_system"] == "Legistar"
    assert uploaded_docs[0]["document_type"] == "Attachment"
    assert uploaded_docs[0]["source_url"] == "http://example.com/1.pdf"
