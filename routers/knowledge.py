"""
Knowledge router - handles knowledge source upload, processing, and management.
"""
import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from database import get_supabase
from models.schemas import (
    KnowledgeSourceCreate,
    KnowledgeSourceResponse,
    KnowledgeSourceListResponse,
    ProcessStatusResponse,
)
from services.chunking import split_text, split_documents
from services.embeddings import add_documents_to_vector_store, delete_vectors_by_source

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge", response_model=KnowledgeSourceListResponse)
async def list_knowledge_sources(search: str = None, type: str = None, status: str = None):
    """List all knowledge sources with optional filtering."""
    supabase = get_supabase()

    query = supabase.table("knowledge_sources").select("*").order("created_at", desc=True)

    if search:
        query = query.ilike("title", f"%{search}%")
    if type:
        query = query.eq("type", type)
    if status:
        query = query.eq("status", status)

    result = query.execute()

    sources = [
        KnowledgeSourceResponse(
            id=s["id"],
            title=s["title"],
            type=s["type"],
            status=s["status"],
            file_path=s.get("file_path"),
            file_size=s.get("file_size"),
            document_count=s.get("document_count", 0),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
        )
        for s in result.data
    ]

    return KnowledgeSourceListResponse(sources=sources, total=len(sources))


@router.get("/knowledge/{source_id}", response_model=KnowledgeSourceResponse)
async def get_knowledge_source(source_id: str):
    """Get a single knowledge source."""
    supabase = get_supabase()

    result = supabase.table("knowledge_sources").select("*").eq("id", source_id).single().execute()

    if result.data is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    s = result.data
    return KnowledgeSourceResponse(
        id=s["id"],
        title=s["title"],
        type=s["type"],
        status=s["status"],
        file_path=s.get("file_path"),
        file_size=s.get("file_size"),
        document_count=s.get("document_count", 0),
        created_at=s["created_at"],
        updated_at=s["updated_at"],
    )


@router.post("/knowledge/upload")
async def upload_knowledge_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    type: str = Form(default="document"),
):
    """
    Upload a file to Supabase Storage and process it for RAG.

    Steps:
    1. Upload file to Supabase Storage
    2. Create knowledge_source record (status: processing)
    3. Background: Extract text → Chunk → Embed → Store vectors
    4. Update status to active
    """
    supabase = get_supabase()
    source_id = str(uuid.uuid4())

    # Upload file to Supabase Storage
    file_content = await file.read()
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    storage_path = f"{source_id}{file_extension}"

    try:
        storage_result = supabase.storage.from_("knowledge-files").upload(storage_path, file_content, {"content-type": file.content_type})
    except Exception as e:
        if "already exists" not in str(e):
            raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")

    # Get public URL
    file_url = supabase.storage.from_("knowledge-files").get_public_url(storage_path)

    # Create knowledge source record
    source_result = supabase.table("knowledge_sources").insert({
        "id": source_id,
        "title": title or file.filename,
        "type": type,
        "status": "processing",
        "file_path": storage_path,
        "file_size": f"{len(file_content) / 1024:.1f} KB",
        "document_count": 0,
    }).select().single().execute()

    # Schedule background processing
    background_tasks.add_task(process_uploaded_file, source_id, file_content, file_extension)

    return source_result.data


@router.post("/knowledge/add-text")
async def add_text_knowledge(
    background_tasks: BackgroundTasks,
    data: KnowledgeSourceCreate,
):
    """
    Add text content directly as a knowledge source.

    Steps:
    1. Create knowledge_source record (status: processing)
    2. Background: Chunk text → Embed → Store vectors
    3. Update status to active
    """
    supabase = get_supabase()
    source_id = str(uuid.uuid4())

    if not data.content:
        raise HTTPException(status_code=400, detail="Content is required for text/faq type")

    # Create knowledge source record
    source_result = supabase.table("knowledge_sources").insert({
        "id": source_id,
        "title": data.title,
        "type": data.type.value,
        "status": "processing",
        "document_count": 0,
        "metadata": {"content_length": len(data.content)},
    }).select().single().execute()

    # Schedule background processing
    background_tasks.add_task(
        process_text_content,
        source_id,
        data.content,
        data.type.value,
    )

    return source_result.data


@router.delete("/knowledge/{source_id}")
async def delete_knowledge_source(source_id: str):
    """Delete a knowledge source and its vectors."""
    supabase = get_supabase()

    # Get source info for storage deletion
    source = supabase.table("knowledge_sources").select("file_path").eq("id", source_id).single().execute()
    if source.data is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    # Delete from vector store
    delete_vectors_by_source(source_id)

    # Delete file from storage
    if source.data.get("file_path"):
        try:
            supabase.storage.from_("knowledge-files").remove([source.data["file_path"]])
        except Exception:
            pass  # File might not exist

    # Delete from database
    supabase.table("knowledge_sources").delete().eq("id", source_id).execute()

    return {"message": "Knowledge source deleted"}


# --- Background Processing Functions ---

def process_uploaded_file(source_id: str, file_content: bytes, file_extension: str):
    """Process an uploaded file: extract text → chunk → embed → store."""
    import io

    supabase = get_supabase()

    try:
        # Extract text from file
        text = extract_text_from_file(file_content, file_extension)

        if not text or len(text.strip()) < 10:
            supabase.table("knowledge_sources").update({
                "status": "error",
                "metadata": {"error": "Could not extract meaningful text from file"},
            }).eq("id", source_id).execute()
            return

        # Chunk the text
        chunks = split_text(text)

        # Store in vector database
        documents = [{"content": chunk, "metadata": {}} for chunk in chunks]
        chunks_added = add_documents_to_vector_store(documents, source_id)

        # Update source status
        supabase.table("knowledge_sources").update({
            "status": "active",
            "document_count": chunks_added,
        }).eq("id", source_id).execute()

        print(f"Processed source {source_id}: {chunks_added} chunks created")

    except Exception as e:
        print(f"Error processing source {source_id}: {e}")
        supabase.table("knowledge_sources").update({
            "status": "error",
            "metadata": {"error": str(e)},
        }).eq("id", source_id).execute()


def process_text_content(source_id: str, content: str, source_type: str):
    """Process text/FAQ content: chunk → embed → store."""
    supabase = get_supabase()

    try:
        if source_type == "faq":
            # Parse FAQ format: "Q: ... A: ..." or "Question: ... Answer: ..."
            import re
            qa_pairs = re.split(r'\n(?=(?:Q:|Question:|A:|Answer:))', content)
            documents = []
            for qa in qa_pairs:
                if qa.strip():
                    documents.append({
                        "content": qa.strip(),
                        "metadata": {"type": "faq"},
                    })
        else:
            # Regular text chunking
            chunks = split_text(content)
            documents = [{"content": chunk, "metadata": {}} for chunk in chunks]

        # Store in vector database
        chunks_added = add_documents_to_vector_store(documents, source_id)

        # Update source status
        supabase.table("knowledge_sources").update({
            "status": "active",
            "document_count": chunks_added,
        }).eq("id", source_id).execute()

        print(f"Processed text source {source_id}: {chunks_added} chunks created")

    except Exception as e:
        print(f"Error processing text source {source_id}: {e}")
        supabase.table("knowledge_sources").update({
            "status": "error",
            "metadata": {"error": str(e)},
        }).eq("id", source_id).execute()


def extract_text_from_file(file_content: bytes, extension: str) -> str:
    """Extract text content from various file types."""
    extension = extension.lower().lstrip(".")

    if extension == "txt":
        # Try to detect encoding
        import chardet
        detected = chardet.detect(file_content)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        return file_content.decode(encoding, errors="replace")

    elif extension == "pdf":
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    elif extension == "docx":
        import io
        from docx import Document
        doc = Document(io.BytesIO(file_content))
        return "\n".join([para.text for para in doc.paragraphs if para.text])

    elif extension == "pptx":
        import io
        from pptx import Presentation
        prs = Presentation(io.BytesIO(file_content))
        text = ""
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
        return text

    elif extension in ["md", "markdown"]:
        return file_content.decode("utf-8", errors="replace")

    elif extension == "csv":
        return file_content.decode("utf-8", errors="replace")

    elif extension == "json":
        import json
        data = json.loads(file_content.decode("utf-8"))
        # Try to extract text from JSON
        if isinstance(data, list):
            return "\n".join([json.dumps(item, indent=2) for item in data])
        return json.dumps(data, indent=2)

    else:
        # Fallback: try UTF-8
        return file_content.decode("utf-8", errors="replace")
