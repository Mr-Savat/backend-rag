# """
# Configuration settings loaded from environment variables.
# """
# from pydantic_settings import BaseSettings
# from typing import List


# class Settings(BaseSettings):
#     # Google AI
#     google_api_key: str = "your_google_api_key_here"

#     # Supabase
#     supabase_url: str = "https://etbrxyoceccpzlmjjicu.supabase.co"
#     supabase_anon_key: str = "sb_publishable_bbqc4yZfQpxgfjj46-6PBw_LWr6xBSQ"
#     supabase_service_role_key: str = ""

#     # PostgreSQL direct connection (for pgvector)
#     database_url: str = ""

#     # CORS
#     cors_origins: str = "http://localhost:5173,http://localhost:3000"

#     # LangChain settings
#     chunk_size: int = 1000
#     chunk_overlap: int = 200
#     max_retrieved_chunks: int = 5

#     # Model settings
#     embedding_model: str = "models/text-embedding-004"
#     chat_model: str = "gemini-2.0-flash"

#     @property
#     def cors_origin_list(self) -> List[str]:
#         return [origin.strip() for origin in self.cors_origins.split(",")]

#     class Config:
#         env_file = ".env"
#         env_file_encoding = "utf-8"


# settings = Settings()


"""
Configuration settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Google AI
    google_api_key: str = "your_google_api_key_here"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # PostgreSQL direct connection (for pgvector)
    database_url: str = ""

     # CORS - allow all origins for production deployment
    cors_origins: str = "*"
    
    # LangChain settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_retrieved_chunks: int = 5

    # Model settings
    embedding_model: str = "intfloat/e5-small-v2"
    chat_model: str = "gemini-2.5-flash"  # Keep Gemini for chat

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
