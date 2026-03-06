from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from azure.search.documents.models import VectorizedQuery
import logging
import re

from api.config import get_settings, get_azure_search_client, get_azure_openai_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BoardBuddy RAG API",
    description="FastAPI backend for BoardBuddy RAG application",
    version="1.0.0"
)

# Allow CORS for frontend (Streamlit/Chainlit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[Dict[str, str]]] = None

class Citation(BaseModel):
    title: str
    url: Optional[str] = None
    document_type: str
    date_published: Optional[str] = None
    content: str
    
class ChatResponse(BaseModel):
    response: str
    citations: List[Citation]

SYSTEM_PROMPT = """You are BoardBuddy, an authoritative, helpful, and highly accurate AI assistant for the Metropolitan Water District of Southern California (MWD).
Your primary role is to answer questions based *only* on the provided context, which includes official MWD documents, board matters, and SharePoint files.

Guidelines:
1. Answer the user's question directly and concisely based on the context.
2. If the answer cannot be found in the context, clearly state that you do not have enough information to answer the question. Do not hallucinate or guess.
3. Be professional and objective in your tone.
4. Base your response strongly on the provided citations.
5. You must cite your sources using bracketed numbers (e.g., [1]). Always synthesize information comprehensively. If summarizing a large list or dataset, provide a complete summary of all relevant items from the context unless the user asks for a brief one.
"""

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    settings = get_settings()
    
    try:
        search_client = get_azure_search_client()
        openai_client = get_azure_openai_client()
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        raise HTTPException(status_code=500, detail="Internal server error initializing clients.")
        
    query = request.query
    search_query = query
    
    try:
        # 1. Query Rewriting (if history exists)
        if request.history and len(request.history) > 0:
            rewrite_prompt = "Given the following conversation history and the user's latest question, rewrite the latest question into a single, standalone search query that contains all necessary context (e.g., specific dates, meeting names, topics) to find relevant documents in a search engine. Do not answer the question, just provide the standalone search query."
            
            rewrite_messages = [{"role": "system", "content": rewrite_prompt}]
            # Provide up to last 5 messages for context
            for msg in request.history[-5:]:
                rewrite_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            rewrite_messages.append({"role": "user", "content": f"Latest question: {query}\n\nStandalone search query:"})
            
            rewrite_completion = openai_client.chat.completions.create(
                model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
                messages=rewrite_messages
            )
            search_query = rewrite_completion.choices[0].message.content.strip().strip('"')
            logger.info(f"Original query: '{query}' -> Rewritten: '{search_query}'")

        # 2. Embed the search query
        emb_response = openai_client.embeddings.create(
            input=search_query,
            model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        )
        query_vector = emb_response.data[0].embedding
        
        # 3. Perform Hybrid Search on Azure Search
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=settings.AZURE_SEARCH_TOP_K,
            fields="content_vector"
        )
        
        # Perform search
        search_results = search_client.search(
            search_text=search_query,
            vector_queries=[vector_query],
            select=["id", "chunk_text", "title", "source_url", "document_type", "date_published"],
            top=settings.AZURE_SEARCH_TOP_K
        )
        
        citations = []
        context_parts = []
        
        for i, result in enumerate(search_results):
            score = result.get("@search.score", 0)
            text = result.get("chunk_text", "")
            title = result.get("title", "Unknown Title")
            url = result.get("source_url")
            doc_type = result.get("document_type", "Unknown")
            date_pub = result.get("date_published")
            
            # Format date to string if present
            if date_pub:
                date_pub = str(date_pub)
                
            citations.append(
                Citation(
                    title=title,
                    url=url,
                    document_type=doc_type,
                    date_published=date_pub,
                    content=text
                )
            )
            
            context_parts.append(f"Document [{i+1}]:\nTitle: {title}\nType: {doc_type}\nDate: {date_pub}\nContent: {text}\n")
            
        context_string = "\n".join(context_parts)
        
        # 4. Construct the prompt for the LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Inject conversation history
        if request.history:
            for msg in request.history[-10:]:
                # Only adding 'user' and 'assistant' roles, ensuring it's safe for Chat Completions
                role = msg.get("role", "user")
                if role not in ["user", "assistant", "system", "developer"]:
                    role = "user"
                messages.append({"role": role, "content": msg.get("content", "")})
                
        # Append the final prompt with context
        messages.append({
            "role": "user", 
            "content": f"Context information is below.\n---------------------\n{context_string}\n---------------------\nGiven the context information above, please answer the following question: {query}"
        })
        
        # 5. Generate Response using o3-mini
        completion = openai_client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=messages
        )
        
        answer = completion.choices[0].message.content
        
        # 6. Post-process citations to only return what was used and re-map indices for the UI
        cited_indices = set()
        for match in re.finditer(r'\[(\d+)\]', answer):
            idx = int(match.group(1))
            if 1 <= idx <= len(citations):
                cited_indices.add(idx)
        
        # Sort them by their original score/relevance
        cited_indices = sorted(list(cited_indices))
        
        # Limit to the requested max returned citations
        limited_indices = cited_indices[:settings.AZURE_SEARCH_RETURN_K]
        
        # Create mapping from old index to new 1-based index
        mapping = {}
        for new_idx, old_idx in enumerate(limited_indices, start=1):
            mapping[old_idx] = new_idx
            
        def replace_citation(match):
            idx = int(match.group(1))
            if idx in mapping:
                return f"[{mapping[idx]}]"
            # Remove the citation if it was truncated, to avoid broken frontend links
            return ""
            
        # Perform replacement
        remapped_answer = re.sub(r'\[(\d+)\]', replace_citation, answer)
        
        # Build the final citations array
        final_citations = [citations[old_idx - 1] for old_idx in limited_indices]
        
        # If no citations were used or matched, return an empty list
        if not final_citations:
            final_citations = []
            remapped_answer = answer # keep original answer if we didn't process anything successfully
        
        return ChatResponse(
            response=remapped_answer,
            citations=final_citations
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
