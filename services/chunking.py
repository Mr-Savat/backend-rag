"""
Text chunking service using LangChain text splitters.
Splits documents into smaller chunks for embedding and retrieval.
"""
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import settings


def split_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> list[str]:
    """
    Split text into smaller chunks using RecursiveCharacterTextSplitter.

    Args:
        text: The full text to split
        chunk_size: Maximum size of each chunk (default from settings)
        chunk_overlap: Overlap between chunks (default from settings)

    Returns:
        List of text chunks
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = text_splitter.split_text(text)
    return chunks


def split_documents(documents: list[dict]) -> list[dict]:
    """
    Split multiple documents into chunks with metadata.

    Args:
        documents: List of dicts with 'content' and 'metadata' keys

    Returns:
        List of dicts with 'content', 'metadata', and 'chunk_index' keys
    """
    all_chunks = []

    for doc in documents:
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})

        chunks = split_text(content)

        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "content": chunk,
                "metadata": {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            })

    return all_chunks


def split_faq(faq_pairs: list[dict]) -> list[dict]:
    """
    Split FAQ pairs into chunks optimized for Q&A retrieval.

    Args:
        faq_pairs: List of dicts with 'question' and 'answer' keys

    Returns:
        List of dicts with 'content' and 'metadata' keys
    """
    chunks = []

    for pair in faq_pairs:
        question = pair.get("question", "")
        answer = pair.get("answer", "")

        content = f"Question: {question}\n\nAnswer: {answer}"

        chunks.append({
            "content": content,
            "metadata": {
                "type": "faq",
                "question": question,
            },
        })

    return chunks
