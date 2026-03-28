"""
AI service supporting multiple providers (Google Gemini, OpenRouter)
"""
from typing import Optional
from config import settings
import httpx

class AIService:
    def __init__(self):
        self.provider = settings.ai_provider
        print(f"🤖 AI Service initialized with provider: {self.provider}")
        
        if self.provider == "openrouter":
            if not settings.openrouter_api_key or settings.openrouter_api_key == "":
                print("⚠️  WARNING: OPENROUTER_API_KEY is not set in .env file")
            else:
                print(f"🔑 OpenRouter API key found (starts with: {settings.openrouter_api_key[:10]}...)")
    
    async def generate_response(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate a response using the configured AI provider"""
        
        if self.provider == "openrouter":
            return await self._generate_openrouter(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "gemini":
            return await self._generate_gemini(prompt, system_prompt, temperature)
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")
    
    async def _generate_openrouter(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate using OpenRouter"""
        
        # Check API key
        if not settings.openrouter_api_key:
            return "Error: OpenRouter API key is not configured. Please add OPENROUTER_API_KEY to your .env file."
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            print(f"📡 Calling OpenRouter API with model: {settings.openrouter_model}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://your-app.com",
                        "X-Title": "AI Knowledge System",
                    },
                    json={
                        "model": settings.openrouter_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                )
                
                print(f"📡 OpenRouter response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print("✅ OpenRouter response received")
                    return data["choices"][0]["message"]["content"]
                else:
                    error_msg = response.text
                    print(f"❌ OpenRouter API error: {error_msg}")
                    
                    if response.status_code == 401:
                        return "Error: Invalid OpenRouter API key. Please check your OPENROUTER_API_KEY in the .env file."
                    elif response.status_code == 429:
                        return "Error: Rate limit exceeded. Please try again later."
                    else:
                        return f"Error: OpenRouter API error (Status {response.status_code})"
            
        except httpx.TimeoutException:
            print("❌ OpenRouter request timeout")
            return "Error: Request timed out. Please try again."
        except Exception as e:
            print(f"❌ OpenRouter API error: {e}")
            return f"Error: {str(e)}"
    
    async def _generate_gemini(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate using Google Gemini"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.google_api_key)
            
            model = genai.GenerativeModel(settings.chat_model)
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            response = await model.generate_content_async(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                }
            )
            return response.text
        except ImportError:
            return "Error: google-generativeai not installed. Run: pip install google-generativeai"
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return f"Error: {str(e)}"

# Global instance
ai_service = AIService()