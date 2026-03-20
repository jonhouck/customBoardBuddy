import requests
import json

url = "http://127.0.0.1:8000/chat"
payload = {
    "query": "Tell me about the recent board matters.",
    "history": []
}

headers = {
    "Content-Type": "application/json"
}

try:
    print("Testing /chat endpoint...")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
        data = response.json()
        print(f"Response length: {len(data.get('response', ''))}")
        print(f"Citations found: {len(data.get('citations', []))}")
    else:
        print("Error Payload:")
        print(response.text)
except Exception as e:
    print(f"Failed to connect to API: {e}")
