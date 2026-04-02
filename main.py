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
from routers import chat, knowledge, sources, analytics

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

# CORS middleware remote
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# local
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Allow all during testing
#     allow_credentials=False,  # Must be False when allow_origins=["*"]
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# CORS middleware - EXPLICIT CONFIGURATION
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:5173",
#         "http://localhost:3000",
#         "http://127.0.0.1:5173",
#         "https://frontend-rag-sooty.vercel.app",
#         "https://frontend-rag-sooty.vercel.app",
#     ],
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["Content-Type", "Authorization", "Accept"],
#     expose_headers=["Content-Type"],
# )

# Include routers
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(sources.router)
app.include_router(analytics.router)


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


@app.get("/debug/auth")
async def debug_auth(token: str):
    """Debug auth endpoint"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://etbrxyoceccpzlmjjicu.supabase.co/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": "sb_publishable_bbqc4yZfQpxgfjj46-6PBw_LWr6xBSQ",
                }
            )
            return {
                "status": response.status_code,
                "response": response.text,
                "token_preview": token[:50] + "..."
            }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
