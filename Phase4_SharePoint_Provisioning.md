# Phase 4: SharePoint Ingestion Provisioning Requirements

To proceed with syncing historical BoardBuddy documents from SharePoint, we require an Entra ID Application configuration and specific SharePoint identifiers. As outlined in the project processes, please provision these external dependencies.

## 1. Entra ID App Registration
Please provision an App Registration (likely in the MWDDev subscription/tenant) that can perform background daemon-style authentication to Microsoft Graph.

**Requirements:**
- **App Name**: e.g., `BoardBuddy-SharePoint-Ingestion`
- **Supported account types**: Accounts in this organizational directory only.
- **API Permissions (Microsoft Graph)**: 
  - `Sites.Read.All` (Application permission)
  - `Files.Read.All` (Application permission)
- **Grant Admin Consent**: The permissions must have tenant-wide admin consent granted.
- **Client Secret**: Create a new client secret and record the value.

**Provide the following back to the project (add to your local `.env` file):**
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

## 2. SharePoint Site ID and Drive ID
We also need the exact Microsoft Graph identifiers for the target SharePoint site and document library (Drive). Since the Graph Explorer is encountering a redirect loop with your organization, we can safely and easily retrieve these IDs directly from the SharePoint REST API built into your browser.

**Step-by-Step Instructions:**
1. Open your web browser and sign in to your MWD Microsoft 365 account.
2. Navigate to the homepage of your target SharePoint site (e.g., `https://<your-tenant>.sharepoint.com/sites/<your-site-name>`).
3. **Get the Site ID:**
   - In the address bar, append `/_api/site/id` to your site's URL and press Enter.
     - *Example:* `https://<your-tenant>.sharepoint.com/sites/<your-site-name>/_api/site/id`
   - Your browser will display a short XML response containing a `<d:Id>` tag.
   - Copy the UUID inside that tag. 
   - Note: The Graph API `Site ID` format expects `<tenant.sharepoint.com>,<site-id-uuid>,<web-id-uuid>`. Often, just providing the `<tenant.sharepoint.com>,<site-id-uuid>` works. So you will format the variable like: `mwdsocal.sharepoint.com,YOUR-COPIED-UUID`.
4. **Get the Drive ID:**
   - Go back to the address bar and change the end of the URL to `/_api/v2.0/drives` and press Enter.
     - *Example:* `https://<your-tenant>.sharepoint.com/sites/<your-site-name>/_api/v2.0/drives`
   - This returns a list of all document libraries on your site in JSON format.
   - Look through the `"value"` array for the document library you want to parse (the `"name"` field is typically `"Documents"` or `"Shared Documents"`, or a custom name you established).
   - Copy the `"id"` value for that specific drive. It will look like a long alphanumeric string (e.g., `b!xyz...`).

**Provide the following back to the project (add to your local `.env` file):**
- `SHAREPOINT_SITE_ID`
- `SHAREPOINT_DRIVE_ID`

---

Once these steps are completed and the `.env` file is populated with the values, we can proceed with constructing and testing the target SharePoint worker.
