"""
Configuration settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import List, Dict


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
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,https://smart-ai-knowledge-bot.vercel.app,https://frontend-rag-sooty.vercel.app"

    # ============ CHUNKING SETTINGS ============
    # Default chunking settings
    chunk_size: int = 500  # Reduced from 1000 to 500 tokens (optimal for RAG)
    chunk_overlap: int = 100  # 20% overlap (recommended)
    max_retrieved_chunks: int = 5
    
    # Document type specific chunk sizes (in tokens)
    chunk_sizes: Dict[str, int] = {
        "faq": 300,        # Short Q&A, one question per chunk
        "text": 500,       # General text
        "markdown": 600,   # Structured documents with headers
        "document": 700,   # Long-form documents
        "code": 200,       # Code snippets (functions/classes)
        "table": 800,      # Tables (preserve row context)
        "legal": 1000,     # Legal documents (long context)
    }
    
    # Overlap percentages by document type
    chunk_overlaps: Dict[str, int] = {
        "faq": 50,         # 15% overlap
        "text": 100,       # 20% overlap
        "markdown": 120,   # 20% overlap
        "document": 140,   # 20% overlap
        "code": 40,        # 20% overlap
        "table": 160,      # 20% overlap
        "legal": 200,      # 20% overlap
    }
    
    # Separators for different content types
    separators: Dict[str, List[str]] = {
        "default": ["\n\n", "\n", ". ", " ", ""],
        "code": ["\nclass ", "\ndef ", "\n\n", "\n", " "],
        "markdown": ["\n\n", "\n", ". ", " ", ""],
        "table": ["\n\n", "\n"],
    }
    
    # Whether to preserve document structure (headers, sections)
    preserve_structure: bool = True
    
    # Whether to add metadata to chunks
    add_chunk_metadata: bool = True

    # ============ RETRIEVAL SETTINGS ============
    max_retrieved_chunks: int = 5  # Number of chunks to retrieve
    similarity_threshold: float = 0.7  # Minimum similarity score (0-1)
    rerank_enabled: bool = True  # Use reranking for better results
    
    # ============ RAG SETTINGS ============
    rag_temperature: float = 0.3  # Lower = more factual
    rag_max_tokens: int = 2048  # Max tokens for AI response

    # ============ MODEL SETTINGS ============
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    chat_model: str = "gemini-2.5-flash"  # Fallback for Gemini

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_chunk_size(self, doc_type: str = "text") -> int:
        """Get optimal chunk size for document type"""
        return self.chunk_sizes.get(doc_type, self.chunk_size)
    
    def get_chunk_overlap(self, doc_type: str = "text") -> int:
        """Get optimal chunk overlap for document type"""
        return self.chunk_overlaps.get(doc_type, self.chunk_overlap)
    
    def get_separators(self, doc_type: str = "text") -> List[str]:
        """Get separators for document type"""
        if doc_type in self.separators:
            return self.separators[doc_type]
        return self.separators["default"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()