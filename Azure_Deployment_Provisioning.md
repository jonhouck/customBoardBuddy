# Azure Deployment Provisioning Guide

This guide details the Azure resources that need to be provisioned to host the BoardBuddy application and configure the CI/CD deployment pipeline via GitHub Actions.

All resources should be provisioned in the **MWDDev** subscription under the existing **rg-boardbuddy** resource group.

## 1. Required Resources to Provision

### A. Azure App Service Plan
You need a hosting plan to run your App Services. Since we have both a Python backend and a Python frontend, a Linux plan is required.
*   **Name:** `plan-boardbuddy-dev` (or similar)
*   **Operating System:** Linux
*   **Region:** (Match your resource group's region, e.g., West US)
*   **Pricing Tier:** Start with Basic (B1) or Standard (S1) for dev/test.

### B. Azure App Service (Backend API)
This will host the FastAPI application (`api/main.py`).
*   **Name:** `app-boardbuddy-api-dev` (must be globally unique)
*   **Publish:** Code
*   **Runtime Stack:** Python 3.11
*   **Operating System:** Linux
*   **App Service Plan:** The one created in Step A.
*   **Configuration:** Under Configuration > General settings, set the Startup Command to:
    ```bash
    uvicorn api.main:app --host 0.0.0.0 --port 8000
    ```

### C. Azure App Service (Frontend UI)
This will host the Streamlit application (`ui/app.py`).
*   **Name:** `app-boardbuddy-ui-dev` (must be globally unique)
*   **Publish:** Code
*   **Runtime Stack:** Python 3.11
*   **Operating System:** Linux
*   **App Service Plan:** The one created in Step A.
*   **Configuration:** Under Configuration > General settings, set the Startup Command to:
    ```bash
    python -m streamlit run ui/app.py --server.port 8000 --server.address 0.0.0.0
    ```

### D. Azure Key Vault & IAM Role Assignments (CRITICAL)
To securely store environment variables (Entra ID secrets, Azure AI Search keys, Foundry endpoints, etc.) and avoid putting them in GitHub.
*   **Name:** `kv-boardbuddy-dev` (must be globally unique)
*   **Region:** (Match your resource group's region)
*   **Pricing Tier:** Standard
*   **Role-Based Access Control (RBAC) Setup:**
    Azure Key Vault now uses RBAC by default. You need to grant access explicitly.
    1. **For Yourself:** Navigate to the Key Vault -> **Access control (IAM)** -> **Add role assignment**. Assign yourself the **Key Vault Secrets Officer** role so you have permission to create and manage secrets.
    2. **For the App Services:** 
        * First, go to each App Service (Backend and Frontend) in the portal. Under Settings, select **Identity**, and under the **System assigned** tab, set Status to **On** and Save.
        * Return to the Key Vault -> **Access control (IAM)** -> **Add role assignment**. Assign the **Key Vault Secrets User** role. Under the "Members" tab, select "Managed identity", and then select the system-assigned identities for your newly created App Services.

### E. Populate Key Vault Secrets
Once your Key Vault is created and you have the "Key Vault Secrets Officer" role, you need to migrate your `.env` variables into the Key Vault as secrets.
1. In the Key Vault, go to **Objects > Secrets**.
2. Click **Generate/Import**.
3. Create a secret for each of the sensitive variables from your local `.env` file.
    * *Note on formatting:* Azure Key Vault secret names can only contain alphanumeric characters and dashes (`-`). You must replace underscores (`_`) with dashes (`-`). For example, `AZURE_SEARCH_API_KEY` becomes `AZURE-SEARCH-API-KEY`. Our application code will automatically map these dashed names back to their underscored versions.
    * Ensure you include your Entra ID Client Secrets, AI Search Keys, etc.

### F. Entra ID App Registrations (Update)
Since your Streamlit UI URL is changing from `localhost` to the new Azure App Service URL (e.g., `https://app-boardbuddy-ui-dev.azurewebsites.net`):
1. Navigate to Entra ID -> App Registrations -> Select your UI app.
2. Go to the **Authentication** blade.
3. Add the new URL (including the callback path `https://app-boardbuddy-ui-dev.azurewebsites.net/oauth2/callback`) to the **Redirect URIs**.

*(Note on App Service URLs: The default `.azurewebsites.net` URLs can be long. For production, we can easily configure a Custom Domain (e.g., `boardbuddy.mwdh2o.com`) via the **Custom Domains** setting in the App Service and binding a TLS/SSL certificate. For dev, it's usually fastest to stick with the default to save time, but we can set up a custom domain now if you have access to MWD's DNS records to add the required CNAME and TXT validation records!)*

---

## 2. GitHub Actions CI/CD Preparation

To allow GitHub Actions to securely deploy code to these App Services, you need to set up a deployment credential. The recommended approach is **OpenID Connect (OIDC)** or downloading the **Publish Profile**. 

For simplicity using Publish Profiles:
1. Go to your Backend App Service in the Azure Portal.
2. Ensure Basic Authentication is enabled for deployment:
    * In the left menu, select **Configuration** -> **General settings**.
    * Scroll down to the **Basic Auth** section.
    * Ensure that **SCM Basic Auth Publishing** is set to **On**.
    * Save the configuration.
3. Once enabled, go back to the Overview page and click **Download publish profile**.
4. Repeat steps 1-3 for your Frontend App Service.

## 3. What to Provide Back

Once provisioning is complete, please provide the following information so I can configure the application and write the GitHub Actions workflows:

1.  **Key Vault Name:** (e.g., `kv-boardbuddy-dev`)
2.  **Backend App Service Name:** (e.g., `app-boardbuddy-api-dev`)
3.  **Frontend App Service Name:** (e.g., `app-boardbuddy-ui-dev`)
4.  **Backend Target URL:** (e.g., `https://app-boardbuddy-api-dev.azurewebsites.net`)
5.  Please confirm you have downloaded the **Publish Profiles** for both App Services, and I will instruct you on how to add them to GitHub Secrets in the next step.
