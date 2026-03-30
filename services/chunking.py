"""
Text chunking service using multiple strategies for better RAG.
"""
import re
from typing import List, Dict, Optional
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    PythonCodeTextSplitter,
)
from config import settings


def detect_document_type(text: str, filename: str = None, url: str = None) -> str:
    """Detect document type from filename, URL, or content"""

    # 1. Check filename/URL extension first
    if filename or url:
        source = filename or url
        source_lower = source.lower()

        # Code files
        if source_lower.endswith(('.py', '.js', '.java', '.cpp', '.c', '.go', '.rs')):
            return 'code'

        # Markdown
        if source_lower.endswith(('.md', '.markdown')):
            return 'markdown'

        # Tables/CSV
        if source_lower.endswith(('.csv', '.xlsx', '.xls')):
            return 'table'

        # JSON
        if source_lower.endswith('.json'):
            return 'json'

        # PDF
        if source_lower.endswith('.pdf'):
            return 'document'

        # Word
        if source_lower.endswith(('.docx', '.doc')):
            return 'document'

        # PowerPoint
        if source_lower.endswith(('.pptx', '.ppt')):
            return 'presentation'

        # Text files
        if source_lower.endswith(('.txt', '.text')):
            return 'text'

    # 2. Check if it's a URL (web content)
    if url and ('http://' in url or 'https://' in url):
        # Check URL path for clues
        if '/blog/' in url or '/article/' in url:
            return 'article'
        if '/docs/' in url or '/documentation' in url:
            return 'documentation'
        if '/api/' in url or '/reference' in url:
            return 'api'
        return 'webpage'

    # 3. Check content patterns
    text_lower = text.lower()

    # FAQ detection
    if 'faq' in text_lower or ('question:' in text_lower and 'answer:' in text_lower):
        return 'faq'

    # Code detection
    if text.startswith('```') or 'def ' in text_lower or 'class ' in text_lower:
        return 'code'

    # Markdown detection
    if text.startswith('#') or '## ' in text_lower:
        return 'markdown'

    # JSON detection
    if text.strip().startswith('{') and '}' in text:
        return 'json'

    # Table detection
    if '|' in text and '---' in text:
        return 'table'

    # Default
    return 'text'


def get_chunk_size(text: str, doc_type: str) -> int:
    """Get optimal chunk size based on document type"""
    sizes = {
        'faq': 300,        # Short Q&A
        'text': 500,       # General text
        'markdown': 600,   # Structured docs
        'document': 700,   # Long docs
        'code': 200,       # Code snippets
        'table': 800,      # Tables
    }
    return sizes.get(doc_type, settings.chunk_size)


def split_by_headers(text: str) -> List[str]:
    """Split markdown/text by headers (H1, H2, H3)"""
    sections = []
    current_section = []
    lines = text.split('\n')

    for line in lines:
        # Check if line is a header
        if re.match(r'^#{1,3}\s', line) or re.match(r'^[A-Z][A-Z\s]+$', line.strip()):
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
        current_section.append(line)

    if current_section:
        sections.append('\n'.join(current_section))

    return sections if len(sections) > 1 else [text]


def split_by_semantic_similarity(chunks: List[str]) -> List[str]:
    """Merge chunks that are semantically related (simplified version)"""
    # This is a placeholder for more advanced semantic chunking
    # You could use sentence transformers here
    return chunks


def split_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    filename: str = None,
    url: str = None,  # ← Add this parameter
) -> List[str]:
    """
    Split text into smaller chunks using optimal strategy based on content.
    """
    # Detect document type (pass url for detection)
    doc_type = detect_document_type(text, filename, url)  # ← Pass url

    # Get optimal chunk size
    optimal_chunk_size = chunk_size or get_chunk_size(text, doc_type)
    optimal_overlap = chunk_overlap or settings.chunk_overlap

    # Choose splitting strategy based on document type
    if doc_type == 'code':
        # Use code-specific splitter for Python files
        try:
            splitter = PythonCodeTextSplitter(chunk_size=optimal_chunk_size)
            chunks = splitter.split_text(text)
        except:
            # Fallback to recursive splitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=optimal_chunk_size,
                chunk_overlap=optimal_overlap,
                separators=["\nclass ", "\ndef ", "\n\n", "\n", " "],
                length_function=len,
            )
            chunks = splitter.split_text(text)

    elif doc_type == 'markdown':
        # First split by headers, then by size
        sections = split_by_headers(text)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=optimal_chunk_size,
            chunk_overlap=optimal_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        chunks = []
        for section in sections:
            chunks.extend(splitter.split_text(section))

    elif doc_type in ['article', 'documentation', 'api', 'webpage']:
        # URL content - preserve structure
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=optimal_chunk_size,
            chunk_overlap=optimal_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        chunks = splitter.split_text(text)

    elif doc_type == 'faq':
        # FAQ content - keep Q&A together
        chunks = split_faq_content(text)  # You'll need this function

    else:
        # Default recursive splitter for regular text
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=optimal_chunk_size,
            chunk_overlap=optimal_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        chunks = splitter.split_text(text)

    # Filter out empty chunks
    chunks = [c.strip() for c in chunks if c.strip()]

    return chunks


def split_faq_content(text: str) -> List[str]:
    """Split FAQ content into Q&A pairs"""
    chunks = []

    # Pattern: Q: ... A: ... or Question: ... Answer: ...
    pattern = r'(?:Q:|Question:)(.*?)(?:A:|Answer:)(.*?)(?=(?:Q:|Question:|$))'

    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    for q, a in matches:
        if q.strip() and a.strip():
            chunks.append(f"Question: {q.strip()}\n\nAnswer: {a.strip()}")

    return chunks if chunks else [text]


def split_documents(documents: List[Dict]) -> List[Dict]:
    """
    Split multiple documents into chunks with metadata.
    """
    all_chunks = []

    for doc in documents:
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})
        filename = metadata.get("file_path", "")
        url = metadata.get("url", "")  # ← Get URL from metadata

        # Detect document type (pass both filename and url)
        doc_type = detect_document_type(content, filename, url)
        metadata["doc_type"] = doc_type

        # Split text (pass url for better detection)
        chunks = split_text(content, filename=filename, url=url)

        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "content": chunk,
                "metadata": {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                    "doc_type": doc_type,
                },
            })

    return all_chunks


def split_faq(faq_pairs: List[Dict]) -> List[Dict]:
    """
    Split FAQ pairs into chunks optimized for Q&A retrieval.
    Each Q&A pair is preserved as a single chunk (small, focused).
    """
    chunks = []

    for pair in faq_pairs:
        question = pair.get("question", "")
        answer = pair.get("answer", "")

        # FAQ chunks should be small and self-contained
        content = f"Question: {question}\n\nAnswer: {answer}"

        chunks.append({
            "content": content,
            "metadata": {
                "type": "faq",
                "question": question,
                "doc_type": "faq",
            },
        })

    return chunks
