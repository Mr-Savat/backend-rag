"""
Data sources router - handles external URL management and crawling.
"""
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from database import get_supabase
from models.schemas import DataSourceCreate, DataSourceResponse
from services.crawler import crawl_url
from services.chunking import split_text
from services.embeddings import add_documents_to_vector_store, delete_vectors_by_source
from dependencies.auth import get_current_user_id

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources")
async def list_data_sources(
    user_id: str = Depends(get_current_user_id)
):
    """List all data sources (external URLs) for current user."""
    supabase = get_supabase()

    result = supabase.table("data_sources").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()

    sources = [
        DataSourceResponse(
            id=s["id"],
            url=s["url"],
            title=s["title"],
            status=s["status"],
            last_sync=s.get("last_sync"),
            document_count=s.get("document_count", 0),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
        )
        for s in result.data
    ]

    return {"sources": sources, "total": len(sources)}


@router.post("/sources")
async def add_data_source(
    background_tasks: BackgroundTasks,
    data: DataSourceCreate,
    user_id: str = Depends(get_current_user_id),
):
    """
    Add a URL data source and crawl it.

    Steps:
    1. Create data_source record (status: syncing)
    2. Background: Crawl URL → Extract text → Chunk → Embed → Store
    3. Update status to connected
    """
    supabase = get_supabase()
    source_id = str(uuid.uuid4())

    # Insert the record with user_id
    supabase.table("data_sources").insert({
        "id": source_id,
        "url": data.url,
        "title": data.title or data.url,
        "status": "syncing",
        "document_count": 0,
        "user_id": user_id,  # ✅ Added user_id
    }).execute()

    # Fetch the created record
    source_result = supabase.table("data_sources").select('*').eq('id', source_id).execute()
    source_data = source_result.data[0] if source_result.data else None

    # Schedule background crawling
    background_tasks.add_task(process_url_source, source_id, data.url, user_id)

    return source_data


@router.post("/sources/{source_id}/sync")
async def sync_data_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    """Force re-sync a data source (must belong to current user)."""
    supabase = get_supabase()

    # Get the source - verify ownership
    source_result = supabase.table("data_sources").select("*").eq("id", source_id).eq("user_id", user_id).execute()
    
    if not source_result.data:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    source = source_result.data[0]

    # Update status to syncing
    supabase.table("data_sources").update({
        "status": "syncing",
    }).eq("id", source_id).execute()

    # Schedule background crawling
    background_tasks.add_task(process_url_source, source_id, source["url"], user_id)

    return {"message": "Sync started", "source_id": source_id}


@router.delete("/sources/{source_id}")
async def delete_data_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a data source (must belong to current user)."""
    supabase = get_supabase()

    # Verify ownership
    check_result = supabase.table("data_sources").select("id").eq("id", source_id).eq("user_id", user_id).execute()
    if not check_result.data:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Delete vectors associated with this source
    delete_vectors_by_source(source_id, collection_name="knowledge")

    # Delete from database
    supabase.table("data_sources").delete().eq("id", source_id).eq("user_id", user_id).execute()

    return {"message": "Data source deleted"}


# --- Background Processing ---

async def process_url_source(source_id: str, url: str, user_id: str):
    """Crawl a URL and process its content for RAG."""
    from database import get_supabase

    supabase = get_supabase()

    try:
        # Crawl the URL
        crawl_result = await crawl_url(url)

        if crawl_result["error"]:
            supabase.table("data_sources").update({
                "status": "error",
            }).eq("id", source_id).eq("user_id", user_id).execute()
            return

        if not crawl_result["content"] or crawl_result["word_count"] < 10:
            supabase.table("data_sources").update({
                "status": "error",
            }).eq("id", source_id).eq("user_id", user_id).execute()
            return

        # Chunk the content
        chunks = split_text(crawl_result["content"])

        # Store in vector database
        documents = [{
            "content": chunk,
            "metadata": {
                "type": "url",
                "url": url,
                "title": crawl_result["title"],
                "source_id": source_id,
                "user_id": user_id,  # ✅ Added user_id to metadata
            },
        } for chunk in chunks]

        chunks_added = add_documents_to_vector_store(documents, source_id)

        # Update source status
        from datetime import datetime, timezone
        supabase.table("data_sources").update({
            "status": "connected",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "document_count": chunks_added,
            "title": crawl_result["title"],
        }).eq("id", source_id).eq("user_id", user_id).execute()

        print(f"Processed URL source {source_id}: {chunks_added} chunks from {crawl_result['title']}")

    except Exception as e:
        print(f"Error processing URL source {source_id}: {e}")
        supabase.table("data_sources").update({
            "status": "error",
        }).eq("id", source_id).eq("user_id", user_id).execute()