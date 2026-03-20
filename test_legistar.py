import requests

MATTERS_URL = "https://webapi.legistar.com/v1/mwdh2o/matters?$filter=substringof('Richardson', MatterTitle)"
response = requests.get(MATTERS_URL)
matters = response.json()
print(f"Found {len(matters)} matters with 'Richardson'")
for m in matters:
    print(f"Matter: {m['MatterTitle']} (ID: {m['MatterId']}, File: {m['MatterFile']})")
    # Get attachments
    attachments_url = f"https://webapi.legistar.com/v1/mwdh2o/matters/{m['MatterId']}/attachments"
    att_response = requests.get(attachments_url)
    attachments = att_response.json()
    for att in attachments:
        print(f"  - Attachment: {att['MatterAttachmentName']} ({att['MatterAttachmentHyperlink']})")
