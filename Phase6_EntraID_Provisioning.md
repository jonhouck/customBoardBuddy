# Phase 6: Entra ID Provisioning for Frontend UI Authentication

**Goal:** Configure a Microsoft Entra ID App Registration so users can securely log into the BoardBuddy Streamlit frontend using their MWD credentials.

## Option A: Separate App Registration (Recommended for Separation of Concerns)
This is the preferred approach for separating the frontend UI login credentials from the backend daemon (Graph API) credentials.

1.  **Navigate directly** to the **Microsoft Entra ID** portal.
2.  Select **App registrations** > **New registration**.
3.  **Name:** `BoardBuddy RAG - Frontend UI` (or similar).
4.  **Supported account types:** Select **Accounts in this organizational directory only (Metropolitan Water District of Southern California)**.
5.  **Redirect URI (Platform: Web):** 
    *   For local testing: `http://localhost:8501`
    *   For production: Add your production URL (e.g., `https://boardbuddy.mwdh2o.com`)
6.  Click **Register**.

### Configure Authentication settings
1.  Go to the **Authentication** blade.
2.  Under **Implicit grant and hybrid flows**, check the box for **ID tokens (used for implicit and hybrid flows)**.
3.  Click **Save**.

### Generate a Client Secret
1.  Go to the **Certificates & secrets** blade.
2.  Click **New client secret**.
3.  Add a description (e.g., `Streamlit UI Auth`) and set an expiration.
4.  **CRITICAL:** Copy the **Value** of the client secret immediately. You won't be able to see it again.

## Option B: Use the Existing App Registration
If you want to use the same App Registration configured for the backend Graph API data ingestion:

1.  Navigate to your existing App Registration in Entra ID.
2.  Go to the **Authentication** blade.
3.  Under **Platform configurations**, click **Add a platform** -> **Web**.
4.  Add the **Redirect URIs**: 
    *   `http://localhost:8501` (for local development)
5.  Under **Implicit grant and hybrid flows**, check the box for **ID tokens (used for implicit and hybrid flows)**.
6.  Click **Save**.
7.  If you don't already have one, generate a Client Secret under **Certificates & secrets**.

---

## Update your `.env` File
Once provisioned, you MUST add these new variables to your local `.env` file (these are now represented in `.env.example`). 

If you used **Option A**, populate these with the new App Registration details. 
If you used **Option B**, you can reuse your `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` for these fields, but you must still explicitly set `UI_REDIRECT_URI`.

```ini
# Microsoft Entra ID (Frontend UI Authentication)
UI_CLIENT_ID="<your-ui-client-id>"
UI_CLIENT_SECRET="<your-ui-client-secret>"
UI_REDIRECT_URI="http://localhost:8501"
```
