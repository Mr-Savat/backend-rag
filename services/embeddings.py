"""
Embedding generation and vector storage service using HuggingFace + pgvector.
"""
import os
import json
import uuid
from typing import List

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from config import settings


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Get HuggingFace embeddings instance (free, no API key required).
    Uses intfloat/e5-small-v2 - small, efficient model.
    """
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


def get_vector_store(collection_name: str = "knowledge") -> PGVector:
    """
    Get PGVector store connected to Supabase PostgreSQL.

    Args:
        collection_name: Name of the vector collection

    Returns:
        PGVector instance
    """
    db_url = settings.database_url
    if not db_url or db_url == "":
        raise ValueError(
            "DATABASE_URL is not set. "
            "Set it in backend/.env with your Supabase PostgreSQL connection string."
        )

    embeddings = get_embeddings()

    vector_store = PGVector(
        embeddings=embeddings,
        connection=db_url,
        collection_name=collection_name,
        use_jsonb=True,
    )

    return vector_store


def add_documents_to_vector_store(
    documents: List[dict],
    source_id: str,
    collection_name: str = "knowledge",
) -> int:
    """
    Add document chunks to the vector store.

    Args:
        documents: List of dicts with 'content' and 'metadata' keys
        source_id: Knowledge source ID to associate with chunks
        collection_name: Vector collection name

    Returns:
        Number of documents added
    """
    vector_store = get_vector_store(collection_name)

    from langchain_core.documents import Document

    langchain_docs = []
    for doc in documents:
        metadata = doc.get("metadata", {})
        metadata["source_id"] = source_id

        langchain_docs.append(
            Document(
                page_content=doc["content"],
                metadata=metadata,
            )
        )

    ids = vector_store.add_documents(langchain_docs)
    return len(ids)


def search_similar_documents(
    query: str,
    k: int = None,
    collection_name: str = "knowledge",
    source_id: str = None,
) -> List[dict]:
    """
    Search for documents similar to the query.
    """
    vector_store = get_vector_store(collection_name)

    filter_dict = {}
    if source_id:
        filter_dict["source_id"] = source_id

    results = vector_store.similarity_search(
        query,
        k=k or settings.max_retrieved_chunks,
        filter=filter_dict if filter_dict else None,
    )

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in results
    ]


def delete_vectors_by_source(source_id: str, collection_name: str = "knowledge") -> bool:
    """
    Delete all vectors associated with a knowledge source.
    """
    try:
        vector_store = get_vector_store(collection_name)
        vector_store.delete(filter={"source_id": source_id})
        return True
    except Exception as e:
        print(f"Error deleting vectors for source {source_id}: {e}")
        return False