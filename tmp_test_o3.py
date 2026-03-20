import os
import sys
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview"
)

deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "o3-mini")

try:
    print("Testing with system role...")
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    )
    print("System role success:", response.choices[0].message.content)
except Exception as e:
    print("System role failed:", e)

try:
    print("\nTesting with developer role...")
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    )
    print("Developer role success:", response.choices[0].message.content)
except Exception as e:
    print("Developer role failed:", e)

try:
    print("\nTesting with large context...")
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
