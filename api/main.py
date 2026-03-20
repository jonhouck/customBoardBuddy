from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from azure.search.documents.models import VectorizedQuery, QueryType
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
    contexts: Optional[List[str]] = None
    
class ChatResponse(BaseModel):
    response: str
    citations: List[Citation]

SYSTEM_PROMPT = """You are BoardBuddy, an authoritative, helpful, and highly accurate AI assistant for the Metropolitan Water District of Southern California (MWD).
Your primary role is to answer questions based *only* on the provided context, which includes official MWD documents, board matters, and SharePoint files.

Guidelines:
1. Answer the user's question directly and concisely based on the currently provided context.
2. If the answer cannot be found in the current context, clearly state that you do not have enough information. Do not hallucinate or guess.
3. Be professional and objective in your tone.
4. CITATIONS MANDATORY: You MUST ALWAYS cite your sources for ANY factual claim you make, explicitly using bracketed numbers corresponding to the Document index (e.g., [1], [2]). Every single bullet point and factual sentence MUST end with a citation.
5. HISTORY IS FOR CONTEXT ONLY: Do NOT use facts, citations, or document numbers from the conversation history to answer the current question. The conversation history contains old reference numbers; ignore them. Only use the documents provided in the immediate "Context information" block.
6. FORMATTING: Use clean, easily readable markdown. Provide enough detail and narrative context to be fully understandable, but keep paragraphs concise and scannable so as not to overwhelm the user. Steer away from exhaustive nested bullet lists in favor of a balanced, descriptive narrative with descriptive headings. ONLY use bullet points if explicitly requested or if absolutely necessary.
7. INLINE LINKS: ONLY provide inline markdown links (`[Document Title](URL)`) if the user explicitly asks you to provide a document or link. Otherwise, strictly use bracketed numbers like [1] for citations, which will be rendered in a separate sources tab.
8. PRIORITIZE PRIMARY DOCUMENTS: When answering questions about what items went to the board or related to meeting details, prioritize referencing primary documents (like "Agenda" or "Meeting Minutes") over simple "Attachment" files if both are available in the context.
9. OUTPUT FORMAT: You MUST output your response in JSON format with two keys:
    - "response": Your comprehensive answer in markdown format, using bracketed citations [1], [2], etc.
    - "snippets": A dictionary mapping the citation index (as a string) to a list of exact verbatim quotes from the context that justify your answer. IF you are providing a broad summary of many documents, you MAY leave the snippet list empty (e.g., `[]`) for a given index to save space, but you MUST STILL INCLUDE the bracketed citation [1] in the `response` text!
    Example: 
    {
      "response": "The contract was awarded to Myers and Sons [1].",
      "snippets": {
        "1": ["Award a $1,718,000 construction contract to Myers and Sons"]
      }
    }
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
            top=settings.AZURE_SEARCH_TOP_K,
            query_type=QueryType.SEMANTIC,
            semantic_configuration_name="boardbuddy-semantic-config"
        )
        
        MAX_LLM_CONTEXT_CHUNKS = 30
        unique_docs = {}
        chunks_processed = 0
        citations = []
        context_parts = []
        
        for result in search_results:
            if chunks_processed >= MAX_LLM_CONTEXT_CHUNKS:
                break
                
            text = result.get("chunk_text", "")
            if not text:
                continue
                
            chunks_processed += 1
            

            title = result.get("title", "Unknown Title")
            url = result.get("source_url")
            doc_type = result.get("document_type", "Unknown")
            date_pub = result.get("date_published")
            
            # Format date to string if present
            if date_pub:
                date_pub = str(date_pub)
                
            # Sanitize URL to prevent 404s due to unencoded spaces
            if url:
                url = url.replace(" ", "%20")
            else:
                url = f"NO_URL_{title}_{date_pub}"
                
            # Deduplicate broadly by title to avoid redundant sources
            doc_key = title.strip().lower()
            
            if doc_key in unique_docs:
                idx = unique_docs[doc_key]
                citations[idx].content += f"\n\n{text}"
                # If the URL was empty previously but we found one now, adopt it
                if not citations[idx].url and url and not url.startswith("NO_URL_"):
                    citations[idx].url = url
            else:
                new_idx = len(citations)
                unique_docs[doc_key] = new_idx
                citations.append(
                    Citation(
                        title=title,
                        url=url,
                        document_type=doc_type,
                        date_published=date_pub,
                        content=text
                    )
                )
                
        for i, cit in enumerate(citations):
            context_parts.append(f"Document [{i+1}]:\nTitle: {cit.title}\nType: {cit.document_type}\nDate: {cit.date_published}\nURL: {cit.url}\nContent: {cit.content}\n")
            
        context_string = "\n".join(context_parts)
        
        # 4. Construct the prompt for the LLM
        messages = [{"role": "developer", "content": SYSTEM_PROMPT}]
        
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
            "content": f"Context information is below.\n---------------------\n{context_string}\n---------------------\nIMPORTANT RULES:\n1. ONLY use the context above to answer the question. Do NOT rely on facts or old citations from the conversation history.\n2. YOU MUST CITE YOUR SOURCES. Place bracketed numbers like [1] or [2] at the end of EVERY factual claim, bullet point, or sentence. Failure to include citations means failure.\n3. ONLY provide direct inline markdown links `[Title](URL)` if the user explicitly asks for them.\n\nQuestion: {query}"
        })
        
        # 5. Generate Response using o3-mini
        completion = openai_client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=messages,
            max_completion_tokens=5000,
            response_format={"type": "json_object"}
        )
        
        import json
        raw_content = completion.choices[0].message.content
        try:
            # Strip markdown if present
            clean_content = raw_content
            if clean_content.startswith("```json"):
                clean_content = clean_content.split("```json", 1)[1]
                if clean_content.endswith("```"):
                    clean_content = clean_content.rsplit("```", 1)[0]
            clean_content = clean_content.strip()
                
            response_json = json.loads(clean_content)
            answer = response_json.get("response", "")
            snippets_dict = response_json.get("snippets", {})
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            answer = raw_content
            snippets_dict = {}
        
        # 6. Post-process citations to only return what was used and re-map indices for the UI
        cited_indices = set()
        
        # Match brackets containing strictly numbers and separators
        for match in re.finditer(r'\[(\d+(?:\s*[,;&]\s*\d+)*)\]', answer):
            content = match.group(1)
            # Find all numbers in the bracket
            for num_match in re.finditer(r'\d+', content):
                idx = int(num_match.group(0))
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
            content = match.group(1)
            
            # Find all numbers in the bracket and map them
            mapped_nums = []
            for num_match in re.finditer(r'\d+', content):
                idx = int(num_match.group(0))
                if idx in mapping:
                    mapped_nums.append(str(mapping[idx]))
            
            # Format cleanly as [1, 2] if valid citations were found inside
            if mapped_nums:
                return f"[{', '.join(mapped_nums)}]"
            else:
                return match.group(0) # Keep original text if no valid mapping found
            
        # Perform replacement
        remapped_answer = re.sub(r'\[(\d+(?:\s*[,;&]\s*\d+)*)\]', replace_citation, answer)
        
        def extract_context_blocks(full_text: str, quotes: List[str]) -> List[str]:
            paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
            contexts_found = []
            
            for quote in quotes:
                if not quote.strip():
                    continue
                quote_lower = quote.lower().strip()
                found = False
                for i, p in enumerate(paragraphs):
                    if quote_lower in p.lower():
                        start_idx = max(0, i - 1)
                        end_idx = min(len(paragraphs), i + 2)
                        context_paras = paragraphs[start_idx:end_idx]
                        
                        # Apply highlight to the exact paragraph where it was found
                        highlighted_paras = []
                        import html
                        for cp in context_paras:
                            safe_cp = html.escape(cp)
                            if quote_lower in safe_cp.lower():
                                # Case-insensitive replace with highlight
                                pattern = re.compile(re.escape(quote.strip()), re.IGNORECASE)
                                safe_cp = pattern.sub(lambda m: f"<span style='color: #ba4d01; font-weight: bold;'>{m.group(0)}</span>", safe_cp)
                            highlighted_paras.append(safe_cp)
                        
                        contexts_found.append("<br><br>".join(highlighted_paras))
                        found = True
                        break
                if not found:
                    # fallback if LLM slightly altered it
                    contexts_found.append(f"<span style='color: #ba4d01; font-weight: bold;'>{html.escape(quote)}</span>")
                    
            return contexts_found

        # Build the final citations array
        final_citations = []
        for old_idx in limited_indices:
            cit = citations[old_idx - 1]
            cit_snippets = snippets_dict.get(str(old_idx), [])
            if not isinstance(cit_snippets, list):
                cit_snippets = [cit_snippets] if isinstance(cit_snippets, str) else []
            
            cit.contexts = extract_context_blocks(cit.content, cit_snippets)
            final_citations.append(cit)
        
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
