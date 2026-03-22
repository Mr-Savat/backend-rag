"""
Data sources router - handles external URL management and crawling.
"""
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from database import get_supabase
from models.schemas import DataSourceCreate, DataSourceResponse
from services.crawler import crawl_url
from services.chunking import split_text
from services.embeddings import add_documents_to_vector_store

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources")
async def list_data_sources():
    """List all data sources (external URLs)."""
    supabase = get_supabase()

    result = supabase.table("data_sources").select("*").order("created_at", desc=True).execute()

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

    # Create data source record
    source_result = supabase.table("data_sources").insert({
        "id": source_id,
        "url": data.url,
        "title": data.title or data.url,
        "status": "syncing",
        "document_count": 0,
    }).select().single().execute()

    # Schedule background crawling
    background_tasks.add_task(process_url_source, source_id, data.url)

    return source_result.data


@router.post("/sources/{source_id}/sync")
async def sync_data_source(
    source_id: str,
    background_tasks: BackgroundTasks,
):
    """Force re-sync a data source."""
    supabase = get_supabase()

    source = supabase.table("data_sources").select("*").eq("id", source_id).single().execute()
    if source.data is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Update status to syncing
    supabase.table("data_sources").update({
        "status": "syncing",
    }).eq("id", source_id).execute()

    # Schedule background crawling
    background_tasks.add_task(process_url_source, source_id, source.data["url"])

    return {"message": "Sync started", "source_id": source_id}


@router.delete("/sources/{source_id}")
async def delete_data_source(source_id: str):
    """Delete a data source."""
    supabase = get_supabase()

    # Delete vectors associated with this source
    from services.embeddings import delete_vectors_by_source
    delete_vectors_by_source(source_id, collection_name="knowledge")

    # Delete from database
    result = supabase.table("data_sources").delete().eq("id", source_id).execute()

    if result.data is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    return {"message": "Data source deleted"}


# --- Background Processing ---

async def process_url_source(source_id: str, url: str):
    """Crawl a URL and process its content for RAG."""
    import asyncio
    from database import get_supabase

    supabase = get_supabase()

    try:
        # Crawl the URL
        crawl_result = await crawl_url(url)

        if crawl_result["error"]:
            supabase.table("data_sources").update({
                "status": "error",
                "metadata": {"error": crawl_result["error"]},
            }).eq("id", source_id).execute()
            return

        if not crawl_result["content"] or crawl_result["word_count"] < 10:
            supabase.table("data_sources").update({
                "status": "error",
                "metadata": {"error": "Insufficient content extracted"},
            }).eq("id", source_id).execute()
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
        }).eq("id", source_id).execute()

        print(f"Processed URL source {source_id}: {chunks_added} chunks from {crawl_result['title']}")

    except Exception as e:
        print(f"Error processing URL source {source_id}: {e}")
        supabase.table("data_sources").update({
            "status": "error",
            "metadata": {"error": str(e)},
        }).eq("id", source_id).execute()
