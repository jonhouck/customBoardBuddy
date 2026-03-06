import streamlit as st
import requests
import os
from dotenv import load_dotenv
from auth import ensure_authenticated, logout

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="BoardBuddy RAG",
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

# Sidebar
with st.sidebar:
    st.title("💧 BoardBuddy")
    st.write(f"Welcome, **{user_name}**")
    if st.button("Sign Out"):
        logout()
        
    st.divider()
    st.subheader("About")
    st.write("BoardBuddy is an AI assistant powered by Azure OpenAI and Azure AI Search.")
    st.write("It searches official Metropolitan Water District of Southern California documents, board matters, and archives to answer your questions.")

# Main Chat Interface
st.title("BoardBuddy Assistant")
st.markdown("Ask questions about MWD board matters, agendas, minutes, presentations, and historical documents.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"].replace("$", r"\$"))
        
        # Display citations if available
        if "citations" in message and message["citations"]:
            with st.expander(f"Sources ({len(message['citations'])})"):
                for idx, cit in enumerate(message["citations"]):
                    source_date = cit.get("date_published", "Unknown Date")
                    doc_type = cit.get("document_type", "Document")
                    title = cit.get("title", "Unknown Title")
                    url = cit.get("url", "#")
                    
                    st.markdown(f"**[{idx+1}]** <a class='citation-link' href='{url}' target='_blank'>{title}</a>", unsafe_allow_html=True)
                    st.markdown(f"<div class='source-meta'>Type: {doc_type} | Date: {source_date}</div>", unsafe_allow_html=True)

# Accept user input
if prompt := st.chat_input("Ask a question... (e.g., 'What was the budget for the Pure Water project in 2023?')"):
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt.replace("$", r"\$"))

    # Display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking... ⏳")
        
        # Prepare request payload
        api_url = "http://localhost:8000/chat"
        
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
