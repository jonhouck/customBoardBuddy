import streamlit as st
import requests
import os
import difflib
import html
import re
from dotenv import load_dotenv
from auth import ensure_authenticated, logout

def highlight_verbatim_quotes(source_text: str, answer_text: str, min_match_length: int = 30) -> str:
    """Highlights verbatim quotes from the answer within the source text."""
    if not source_text:
        return ""
        
    # Strip HTML tags but preserve text content and newlines
    clean_source = re.sub(r'<[^>]+>', ' ', source_text)
    # Condense multiple spaces but preserve explicit newlines
    clean_source = re.sub(r'[ \t]+', ' ', clean_source).strip()
    clean_source = re.sub(r'\n{3,}', '\n\n', clean_source)
    
    if not answer_text:
        return html.escape(clean_source).replace('\n', '<br>')
        
    matcher = difflib.SequenceMatcher(None, clean_source.lower(), answer_text.lower())
    blocks = matcher.get_matching_blocks()
    valid_blocks = [b for b in blocks if b.size >= min_match_length]
    
    highlighted = ""
    last_idx = 0
    
    for block in blocks:
        if block.size >= min_match_length:
            # Escape the unhighlighted part
            highlighted += html.escape(clean_source[last_idx:block.a])
            # Escape the matched part and wrap in styling span using MWD Orange 1
            match_text = html.escape(clean_source[block.a:block.a + block.size])
            highlighted += f'<span style="color: #ba4d01; font-weight: bold;">{match_text}</span>'
            last_idx = block.a + block.size
            
    highlighted += html.escape(clean_source[last_idx:])
    return highlighted.replace('\n', '<br>')

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="BoardBuddy",
    page_icon="💧",
    layout="wide"
)

# Load CSS
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
            
load_css()

# Enforce Authentication
if not ensure_authenticated():
    st.stop()  # Halt execution until authenticated

user = st.session_state["user"]
user_name = user.get("name", "MWD User")
access_token = st.session_state.get("access_token")

@st.cache_data(show_spinner=False)
def fetch_profile_picture(token):
    if not token:
        return None
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get("https://graph.microsoft.com/v1.0/me/photo/$value", headers=headers, timeout=2)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None

user_avatar = fetch_profile_picture(access_token) or "👤"

# Sidebar
with st.sidebar:
    seal_path = os.path.join(os.path.dirname(__file__), "assets", "mwd_seal.png")
    if os.path.exists(seal_path):
        st.image(seal_path, use_container_width=True)
    else:
        st.title("💧 BoardBuddy")

    st.write(f"Welcome, **{user_name}**")
    if st.button("Sign Out"):
        logout()
        
    if st.button("Start New Conversation"):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.subheader("About")
    st.write("BoardBuddy is an AI assistant powered by Azure OpenAI and Azure AI Search.")
    st.write("It searches official Metropolitan Water District of Southern California documents, board matters, and archives to answer your questions.")

# Main Chat Interface
col1, col2 = st.columns([0.75, 0.25])
with col1:
    st.title("BoardBuddy Assistant")
    st.markdown("Ask questions about MWD board matters, agendas, minutes, presentations, and historical documents.")

with col2:
    st.write("") # Vertical spacing
    st.write("")
    
    # Define limitations content
    limitations_text = """
**How it works**  
BoardBuddy uses *Semantic Search*. When you ask a question, it searches the archives for paragraphs of text that share the same *meaning* as your question. It then hands these text snippets to the AI to read and summarize. 

**Wait, what can't it do?**  
Because it searches by *meaning* and not by *math*, BoardBuddy cannot perform database operations like sorting, calculating maximums, averages, or counting totals across thousands of documents. 
For example, if you ask *"What was the most expensive item in 2023?"*, BoardBuddy cannot sort a database from highest to lowest. It will only locate a few documents that mention "costs" and "2023", and mistakenly guess the highest number it sees in that very small pile.

**Tips for Best Results:**
*   ✅ **DO** ask for summaries (e.g., *"What was the outcome of the Pure Water program vote?"*)
*   ✅ **DO** ask for conceptual overviews (e.g., *"What are our policies regarding drought conservation?"*)
*   ✅ **DO** ask to explain specific documents (e.g., *"Can you summarize the findings in the latest Delta Conveyance report?"*)
*   ❌ **DON'T** ask for rankings (e.g., *"What was the most expensive project?"*)
*   ❌ **DON'T** ask for exact calculations or tallies (e.g., *"How many board letters were approved last year?"*)
    """
    
    # Use st.popover instead of a button/dialog to prevent rerunning the script and killing background RAG processes
    with st.popover("How to Use & Limitations", use_container_width=True):
        st.markdown("### ℹ️ How to Use & Limitations")
        st.markdown(limitations_text)


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    avatar_val = user_avatar if message["role"] == "user" else "💧"
    with st.chat_message(message["role"], avatar=avatar_val):
        st.markdown(message["content"].replace("$", r"\$"))
        
        # Display citations if available
        if "citations" in message and message["citations"]:
            with st.expander(f"Sources ({len(message['citations'])})"):
                for idx, cit in enumerate(message["citations"]):
                    source_date = cit.get("date_published") or "Unknown Date"
                    doc_type = cit.get("document_type") or "Document"
                    
                    title = str(cit.get("title") or "").strip()
                    # Strip newlines to prevent Streamlit Markdown parser from generating broken HTML / empty bubbles
                    title = " ".join(title.split())
                    if not title:
                        title = "Unknown Title"
                        
                    url = str(cit.get("url") or "").strip()
                    if url and url != "#":
                        st.markdown(f"**[{idx+1}]** <a class='citation-link' href='{url}' target='_blank'>{title}</a>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**[{idx+1}]** <span class='citation-link'>{title}</span>", unsafe_allow_html=True)
                        
                    st.markdown(f"<div class='source-meta'>Type: {doc_type} | Date: {source_date}</div>", unsafe_allow_html=True)
                    if cit.get("content"):
                        with st.expander("Show relevant text"):
                            highlighted_text = highlight_verbatim_quotes(cit.get("content"), message.get("content", ""))
                            st.markdown(highlighted_text, unsafe_allow_html=True)

# Accept user input
if prompt := st.chat_input("Ask a question... (e.g., 'What was the budget for the Pure Water project in 2023?')"):
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(prompt.replace("$", r"\$"))

    # Display assistant response
    with st.chat_message("assistant", avatar="💧"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking... ⏳")
        
        # Prepare request payload
        api_url = os.getenv("API_URL", "http://localhost:8000")
        if not api_url.endswith("/chat"):
            api_url = api_url.rstrip("/") + "/chat"
        
        # Filter history to only include role and content (drop massive citations array)
        filtered_history = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in st.session_state.messages[:-1]
        ]
        
        payload = {
            "query": prompt,
            "history": filtered_history
        }
        
        try:
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("response", "No response returned.")
            citations = data.get("citations", [])
            
            # Display answer
            message_placeholder.markdown(answer.replace("$", r"\$"))
            
            # Record in session state
            st.session_state.messages.append({
                "role": "assistant", 
                "content": answer,
                "citations": citations
            })
            
            # Re-render to show expander for citations immediately
            st.rerun()
            
        except requests.exceptions.RequestException as e:
            st.error(f"Error communicating with backend: {e}")
            message_placeholder.markdown("Sorry, I encountered an error connecting to the BoardBuddy service.")
