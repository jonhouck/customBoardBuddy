import os, requests
from dotenv import dotenv_values

try:
    config = dotenv_values(".env")
    endpoint = config.get("AZURE_SEARCH_ENDPOINT")
    key = config.get("AZURE_SEARCH_API_KEY")
    idx = config.get("AZURE_SEARCH_INDEX", "board-buddy-index")

    url = f"{endpoint}/indexes/{idx}/docs/$count?api-version=2023-11-01"
    r = requests.get(url, headers={"api-key": key}, timeout=15)
    
    with open("tmp_chunk_count.txt", "w") as f:
        f.write(r.text)
except Exception as e:
    with open("tmp_chunk_count.txt", "w") as f:
        f.write(f"Error: {str(e)}")
