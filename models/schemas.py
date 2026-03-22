"""
Pydantic models for API request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# --- Enums ---

class SourceType(str, Enum):
    DOCUMENT = "document"
    URL = "url"
    TEXT = "text"
    FAQ = "faq"


class SourceStatus(str, Enum):
    ACTIVE = "active"
    PROCESSING = "processing"
    ERROR = "error"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DataSourceStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    ERROR = "error"


# --- Chat Models ---

class ChatMessageRequest(BaseModel):
    """Send a message and get AI response."""
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=5000)


class ChatMessageResponse(BaseModel):
    """AI response with message data."""
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


class ConversationCreate(BaseModel):
    """Create a new conversation."""
    title: str = Field(default="New Conversation")


class ConversationResponse(BaseModel):
    """Conversation data."""
    id: str
    user_id: Optional[str] = None
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


# --- Knowledge Models ---

class KnowledgeSourceCreate(BaseModel):
    """Create a new knowledge source."""
    title: str = Field(..., min_length=1, max_length=500)
    type: SourceType
    content: Optional[str] = None  # For text/faq type
    url: Optional[str] = None      # For url type


class KnowledgeSourceResponse(BaseModel):
    """Knowledge source data."""
    id: str
    title: str
    type: str
    status: str
    file_path: Optional[str] = None
    file_size: Optional[str] = None
    document_count: int
    created_at: str
    updated_at: str


class KnowledgeSourceListResponse(BaseModel):
    """List of knowledge sources."""
    sources: List[KnowledgeSourceResponse]
    total: int


# --- Data Source (URL) Models ---

class DataSourceCreate(BaseModel):
    """Add a URL data source."""
    url: str = Field(..., min_length=1)
    title: Optional[str] = None


class DataSourceResponse(BaseModel):
    """Data source data."""
    id: str
    url: str
    title: str
    status: str
    last_sync: Optional[str] = None
    document_count: int
    created_at: str
    updated_at: str


# --- Processing Models ---

class ProcessStatusResponse(BaseModel):
    """Status of document processing."""
    source_id: str
    status: str
    chunks_created: int
    message: str


# --- Health Check ---

class HealthResponse(BaseModel):
    """API health check."""
    status: str
    version: str
    services: dict
