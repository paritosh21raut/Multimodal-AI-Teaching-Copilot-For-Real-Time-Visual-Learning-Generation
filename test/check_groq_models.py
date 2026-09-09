"""
Check available Groq models
"""

import os
from openai import OpenAI

api_key = os.getenv("GROQ_API_KEY", "")
print(f"API Key present: {bool(api_key)}")

if not api_key:
    print("GROQ_API_KEY not set!")
    exit()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)

try:
    models = client.models.list()
    print("\nAvailable Groq models:")
    print("-" * 50)
    for m in models.data:
        print(f"  {m.id}")
except Exception as e:
    print(f"Error: {e}")