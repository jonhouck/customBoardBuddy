import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch('api.main.get_azure_openai_client')
@patch('api.main.get_azure_search_client')
def test_chat_endpoint(mock_search_client, mock_openai_client):
    # Set up mock OpenAI client
    mock_openai_instance = MagicMock()
    
    # Mock embeddings response
    mock_embed_response = MagicMock()
    mock_embed_response.data = [MagicMock(embedding=[0.1] * 3072)]
    mock_openai_instance.embeddings.create.return_value = mock_embed_response
    
    # Mock chat completions response
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [MagicMock(message=MagicMock(content="This is a mocked response based on the context."))]
    mock_openai_instance.chat.completions.create.return_value = mock_chat_response
    
    mock_openai_client.return_value = mock_openai_instance
    
    # Set up mock Search client
    mock_search_instance = MagicMock()
    
    # Mock search results Iterator
    mock_result_1 = {
        "@search.score": 0.99,
        "id": "item1",
        "chunk_text": "This is a mock chunk of text containing the answer.",
        "title": "Mock Document 1",
        "source_url": "https://example.com/doc1",
        "document_type": "PDF",
        "date_published": "2024-01-01T00:00:00Z"
    }
    mock_search_instance.search.return_value = iter([mock_result_1])
    
    mock_search_client.return_value = mock_search_instance
    
    # Make request
    request_data = {
        "query": "What is the answer?"
    }
    
    response = client.post("/chat", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "response" in data
    assert data["response"] == "This is a mocked response based on the context."
    assert "citations" in data
    assert len(data["citations"]) == 1
    assert data["citations"][0]["title"] == "Mock Document 1"
    
    # Verify exactly how APIs were called
    mock_openai_instance.embeddings.create.assert_called_once()
    mock_search_instance.search.assert_called_once()
    mock_openai_instance.chat.completions.create.assert_called_once()
