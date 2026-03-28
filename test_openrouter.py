import os
from dotenv import load_dotenv
import httpx

# Load .env
load_dotenv()

# Get API key
api_key = os.getenv("OPENROUTER_API_KEY")
print(f"API Key: {api_key[:30]}..." if api_key else "No API key found")

if not api_key:
    print("❌ No API key in .env")
    exit(1)

# Test with direct request
try:
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek/deepseek-chat",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10,
        },
        timeout=30
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ Success!")
    else:
        print("❌ Failed")
        
except Exception as e:
    print(f"Error: {e}")