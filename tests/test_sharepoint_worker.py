from unittest.mock import patch, MagicMock
from ingestion.sharepoint_worker import (
    chunk_text,
    extract_text_from_pdf_bytes,
    fetch_sharepoint_files,
    ms_graph_request,
    process_sharepoint
)

def test_chunk_text():
    text = "word " * 1000
    chunks = chunk_text(text, chunk_size=800, overlap=150)
    assert len(chunks) > 0
    assert len(chunks[0].split()) <= 1000 

@patch('ingestion.sharepoint_worker.fitz.open')
def test_extract_text_from_pdf_bytes(mock_fitz_open):
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Test PDF Content"
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    text = extract_text_from_pdf_bytes(b"dummy pdf bytes")
    assert "Test PDF Content" in text

@patch('ingestion.sharepoint_worker.requests.get')
def test_ms_graph_request(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"value": "test"}
    mock_get.return_value = mock_response

    result = ms_graph_request("http://test.com", "fake_token")
    assert result == {"value": "test"}

@patch('ingestion.sharepoint_worker.requests.get')
def test_ms_graph_request_bytes(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.content = b"pdfbytes"
    mock_get.return_value = mock_response

    result = ms_graph_request("http://test.com", "fake_token")
    assert result == b"pdfbytes"

@patch('ingestion.sharepoint_worker.ms_graph_request')
def test_fetch_sharepoint_files(mock_ms_request):
    mock_ms_request.return_value = {
        "value": [
            {"id": "1", "name": "test.pdf", "file": {}, "webUrl": "http://sp.com/test.pdf"},
            {"id": "2", "name": "folder", "folder": {}}, # Should be skipped
            {"id": "3", "name": "test.docx", "file": {}} # Should be skipped for now
        ]
    }
    
    files = fetch_sharepoint_files("fake_token", "fake_drive", limit=5)
    assert len(files) == 1
    assert files[0]["id"] == "1"

@patch('ingestion.sharepoint_worker.SHAREPOINT_DRIVE_ID', 'test_drive')
@patch('ingestion.sharepoint_worker.get_graph_token')
@patch('ingestion.sharepoint_worker.get_search_client')
@patch('ingestion.sharepoint_worker.get_openai_client')
@patch('ingestion.sharepoint_worker.fetch_sharepoint_files')
@patch('ingestion.sharepoint_worker.get_indexed_urls')
@patch('ingestion.sharepoint_worker.ms_graph_request')
@patch('ingestion.sharepoint_worker.extract_text_from_pdf_bytes')
def test_process_sharepoint(
    mock_extract, mock_ms_request, mock_indexed, mock_fetch, mock_openai, mock_search, mock_token
):
    mock_token.return_value = "fake_token"
    mock_indexed.return_value = set()
    mock_fetch.return_value = [
        {"id": "file1", "name": "Board_Meeting.pdf", "webUrl": "http://sp/1.pdf", "createdDateTime": "2024-05-01T00:00:00Z"}
    ]
    mock_ms_request.return_value = b"pdfbytes"
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

    process_sharepoint(limit=1)

    # Verify search upload was called
    mock_search_instance.upload_documents.assert_called_once()
    uploaded_docs = mock_search_instance.upload_documents.call_args[1]["documents"]
    assert len(uploaded_docs) == 1
    assert uploaded_docs[0]["source_system"] == "SharePoint"
    assert uploaded_docs[0]["document_type"] == "Historical Document"
    assert uploaded_docs[0]["source_url"] == "http://sp/1.pdf"
