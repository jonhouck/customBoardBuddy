# GitHub Actions CI/CD Secrets Setup

Before the GitHub Actions workflows can successfully deploy your code to Azure App Services, you need to configure the deployment credentials (the Publish Profiles you downloaded) as GitHub Secrets in this repository.

## Adding the Secrets to GitHub

1. Open your web browser and navigate to this repository on GitHub (`https://github.com/jonhouck/customBoardBuddy`).
2. Click on the **Settings** tab (the gear icon near the top right, under the repository name).
3. In the left-hand sidebar, scroll down to the **Security** section, expand **Secrets and variables**, and click on **Actions**.
4. Click the green button: **New repository secret**.

You need to add two secrets, one for the Backend API and one for the Frontend UI.

### Secret 1: Backend API Publish Profile
*   **Name:** `AZURE_WEBAPP_PUBLISH_PROFILE_API`
*   **Secret:** Open the Publish Profile file you downloaded for `app-boardbuddy-api-dev` using a text editor (like VS Code or Notepad). Copy the **entire contents** of the file and paste it here.
*   Click **Add secret**.

### Secret 2: Frontend UI Publish Profile
*   **Name:** `AZURE_WEBAPP_PUBLISH_PROFILE_UI`
*   **Secret:** Open the Publish Profile file you downloaded for `app-boardbuddy-ui-dev` using a text editor. Copy the **entire contents** of the file and paste it here. 
*   Click **Add secret**.

---

## Important Note on Environment Variables

The GitHub Actions workflows we created (`deploy-api.yml` and `deploy-ui.yml`) are configured to *only* deploy the application code. 

**They do not manage environment variables.** 

Because we configured Azure Key Vault to store secrets and assigned Managed Identities to the App Services to retrieve them, you do **not** need to put your `.env` variables into GitHub Secrets. 

However, you **must** configure the App Service Configuration settings so your apps know how to connect to the Key Vault.

### In the Azure Portal for BOTH App Services (API and UI):
1. Navigate to the App Service.
2. In the left-hand menu, under **Settings**, select **Environment variables**.
3. Under the **App settings** tab, click **+ Add**.
4. You need to add key-value pairs that reference your Key Vault secrets. For each secret in your Key Vault:
    *   **Name:** (The name of your environment variable from your `.env` file, e.g., `AZURE_OPENAI_API_KEY`)
    *   **Value:** `@Microsoft.KeyVault(SecretUri=https://kv-boardbuddy-dev.vault.azure.net/secrets/[YOUR-SECRET-NAME]/)`
        *(Replace `[YOUR-SECRET-NAME]` with the dashed version of the secret name you created in the Key Vault, e.g., `AZURE-OPENAI-API-KEY`)*
5. **CRITICAL FOR PYTHON CI/CD**: You must add one setting to tell Azure's deployment engine (Oryx) to install dependencies when it receives the zip file from GitHub Actions.
    *   **Name:** `SCM_DO_BUILD_DURING_DEPLOYMENT`
    *   **Value:** `true`
6. **CRITICAL FOR UI APP SERVICE ONLY**: You must add one setting that does not come from Key Vault.
    *   **Name:** `API_URL`
    *   **Value:** `https://app-boardbuddy-api-dev-hxdqhdamdxayasg6.westus3-01.azurewebsites.net/chat`
7. Click **Apply** at the bottom of the "Add/Edit" pane, and then **Apply** again at the bottom of the main "Environment variables" page to save.

If you haven't already, please commit the new workflow files (`.github/workflows/deploy-api.yml` and `.github/workflows/deploy-ui.yml`) and push them to the repository to trigger the first deployment.
