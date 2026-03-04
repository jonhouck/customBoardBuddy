import msal
import os
import streamlit as st

def get_msal_app():
    """Initializes the MSAL Confidential Client Application."""
    client_id = os.getenv("UI_CLIENT_ID")
    client_secret = os.getenv("UI_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    if not all([client_id, client_secret, tenant_id]):
        st.error("Missing UI Entra ID environment variables. Please check your .env file.")
        return None
        
    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

def get_login_url():
    """Generates the authorization URL for user login."""
    app = get_msal_app()
    if not app:
        return None
        
    redirect_uri = os.getenv("UI_REDIRECT_URI", "http://localhost:8501")
    
    # We request the basic profile and openid scopes
    scopes = ["User.Read"]
    
    auth_url = app.get_authorization_request_url(
        scopes,
        redirect_uri=redirect_uri
    )
    return auth_url

def acquire_token_by_auth_code(auth_code: str):
    """Acquires a token using the authorization code from the redirect."""
    app = get_msal_app()
    if not app:
        return None
        
    redirect_uri = os.getenv("UI_REDIRECT_URI", "http://localhost:8501")
    scopes = ["User.Read"]
    
    result = app.acquire_token_by_authorization_code(
        auth_code,
        scopes=scopes,
        redirect_uri=redirect_uri
    )
    
    return result

def ensure_authenticated():
    """
    Checks if the user is authenticated via session state.
    If not, handles the auth code from the URL or prompts login.
    """
    if "user" in st.session_state:
        # Already logged in
        return True
        
    # Check if we are handling a redirect from Entra ID
    query_params = st.query_params
    if "code" in query_params:
        auth_code = query_params["code"]
        result = acquire_token_by_auth_code(auth_code)
        
        if result and "id_token_claims" in result:
            # Successfully authenticated, save user info to session
            st.session_state["user"] = result.get("id_token_claims")
            # Clear the query params to clean up the URL
            st.query_params.clear()
            st.rerun()
            return True
        else:
            st.error(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
            
    # Not logged in, render the login button
    login_url = get_login_url()
    if login_url:
        st.title("BoardBuddy RAG")
        st.markdown("### Welcome to BoardBuddy!")
        st.markdown("Please sign in with your MWD credentials to access the internal knowledge base.")
        st.markdown(f'<a href="{login_url}" target="_self"><button style="background-color: #4795ff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">Sign in with Microsoft</button></a>', unsafe_allow_html=True)
    return False

def logout():
    """Clears the session state."""
    if "user" in st.session_state:
        del st.session_state["user"]
    st.rerun()
