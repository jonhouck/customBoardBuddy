import sys
import logging
from api.config import get_settings, get_azure_openai_client

logging.basicConfig(level=logging.INFO)

settings = get_settings()
client = get_azure_openai_client()
deployment = settings.AZURE_OPENAI_CHAT_DEPLOYMENT

print(f"Testing deployment: {deployment}")

try:
    print("\n--- Testing with DEVELOPER role ---")
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! Reply with 1 word."}
        ]
    )
    print("Developer role success:", response.choices[0].message.content)
except Exception as e:
    print("Developer role failed:", e)

try:
    print("\n--- Testing with SYSTEM role ---")
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! Reply with 1 word."}
        ]
    )
    print("System role success:", response.choices[0].message.content)
except Exception as e:
    print("System role failed:", e)

try:
    print("\n--- Testing Large Context Payload limit ---")
    large_context = "test " * 20000 # 20k words
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Context: {large_context}\n\nSay hi."}
        ]
    )
    print("Large context success:", response.choices[0].message.content)
except Exception as e:
    print("Large context failed:", e)

