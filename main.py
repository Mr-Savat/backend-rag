"""
AI Knowledge System - FastAPI Backend
======================================
Main entry point with all routers and middleware.
"""
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

# Import routers
from routers import chat, knowledge, sources

# Import schemas
from models.schemas import HealthResponse

# Create FastAPI app
app = FastAPI(
    title="AI Knowledge System API",
    description="Backend API for the Conversational AI Knowledge System with RAG (Retrieval-Augmented Generation).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(sources.router)


# --- Health Check ---

@app.get("/", response_model=HealthResponse, tags=["health"])
async def health_check():
    """API health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services={
            "api": "running",
            "gemini": "configured" if settings.google_api_key != "your_google_api_key_here" else "not configured",
            "supabase": "configured" if settings.supabase_url else "not configured",
            "database": "configured" if settings.database_url else "not configured",
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health():
    """Detailed health check."""
    return await health_check()


# --- API Documentation ---

@app.get("/api", tags=["info"])
async def api_info():
    """Get API information and available endpoints."""
    return {
        "name": "AI Knowledge System API",
        "version": "1.0.0",
        "description": "Backend for Conversational AI Knowledge System",
        "endpoints": {
            "chat": {
                "POST /api/chat": "Send message and get RAG response",
                "POST /api/conversations": "Create new conversation",
                "GET /api/conversations": "List conversations",
                "GET /api/conversations/{id}": "Get conversation with messages",
                "DELETE /api/conversations/{id}": "Delete conversation",
            },
            "knowledge": {
                "GET /api/knowledge": "List knowledge sources",
                "POST /api/knowledge/upload": "Upload a file",
                "POST /api/knowledge/add-text": "Add text/FAQ content",
                "DELETE /api/knowledge/{id}": "Delete knowledge source",
            },
            "sources": {
                "GET /api/sources": "List data sources (URLs)",
                "POST /api/sources": "Add URL data source",
                "POST /api/sources/{id}/sync": "Re-sync a data source",
                "DELETE /api/sources/{id}": "Delete data source",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
