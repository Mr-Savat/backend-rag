"""
Configuration settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # AI Provider Selection
    ai_provider: str = "openrouter"  # "gemini" or "openrouter"
    
    # Google AI
    google_api_key: str = "your_google_api_key_here"
    
    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # PostgreSQL direct connection (for pgvector)
    database_url: str = ""

    # CORS - allow all origins for production deployment
    cors_origins: str = "http://localhost:5173,https://smart-ai-knowledge-bot.vercel.app"
    
    # LangChain settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_retrieved_chunks: int = 5

    # Model settings (fallback)
    embedding_model: str = "BAAI/bge-small-en-v1.5"  
    chat_model: str = "gemini-2.5-flash"  # Fallback for Gemini

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()