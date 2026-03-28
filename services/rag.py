"""
RAG (Retrieval-Augmented Generation) service supporting multiple AI providers.
"""
from typing import List, Optional
from services.embeddings import search_similar_documents
from services.ai import ai_service
from config import settings


# System prompt for the AI
SYSTEM_PROMPT = """You are an AI Knowledge Assistant for a Conversational AI Knowledge System. 
Your role is to provide accurate, helpful answers based on the retrieved knowledge base content.

Rules:
- Answer based ONLY on the provided context. If the context doesn't contain relevant information, say so.
- Be concise but thorough. Use markdown formatting for better readability:
  * Use **bold** for emphasis on key terms
  * Use bullet points (- ) for lists
  * Use numbered lists (1. ) for steps or sequences
  * Use ### for section headers if organizing content
- DO NOT include source citations like [Source: ...] or [Document X] in your answers.
- If you're unsure, acknowledge it rather than guessing.
- Respond in the same language as the user's question.
"""


async def generate_rag_response(
    question: str,
    conversation_history: Optional[List[dict]] = None,
    source_id: Optional[str] = None,
) -> dict:
    """
    Generate a response using RAG (Retrieval-Augmented Generation).

    Args:
        question: User's question
        conversation_history: Optional list of previous messages [{role, content}]
        source_id: Optional filter to search specific knowledge source

    Returns:
        Dict with 'answer' and 'sources' keys
    """
    # Step 1: Retrieve relevant documents
    retrieved_docs = search_similar_documents(
        query=question,
        source_id=source_id,
    )

    # Step 2: Build context from retrieved documents
    context_parts = []
    sources = []

    for i, doc in enumerate(retrieved_docs, 1):
        context_parts.append(
            f"[Document {i}]\n{doc['content']}"
        )
        sources.append({
            "title": doc["metadata"].get("title", "Unknown"),
            "source_id": doc["metadata"].get("source_id"),
        })

    context = "\n\n---\n\n".join(
        context_parts) if context_parts else "No relevant documents found."

    # Step 3: Build conversation context
    conversation_context = ""
    if conversation_history:
        recent_history = conversation_history[-6:]  # Last 3 exchanges
        for msg in recent_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg['content']}\n"

    # Step 4: Build prompt
    full_question = question
    if conversation_context:
        full_question = f"Previous conversation:\n{conversation_context}\n\nCurrent question: {question}"

    prompt = f"""Context information:
{context}

Question: {full_question}

Please provide a helpful answer based on the context above."""

    # Step 5: Generate response using AI service (OpenRouter or Gemini)
    try:
        answer = await ai_service.generate_response(  # ← Added await
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048
        )
    except Exception as e:
        print(f"AI generation error: {e}")
        answer = f"Sorry, I encountered an error: {str(e)}"

    return {
        "answer": answer,
        "sources": sources,
        "chunks_retrieved": len(retrieved_docs),
    }


async def generate_simple_response(question: str) -> str:
    """
    Generate a response without RAG (fallback for when no knowledge base exists).
    Uses the configured AI provider directly.

    Args:
        question: User's question

    Returns:
        Generated response string
    """
    prompt = f"""Question: {question}

Please provide a helpful answer. Be concise and friendly."""

    simple_prompt = """You are a helpful AI assistant for a Knowledge Management System.
Currently, the knowledge base is empty or not configured. Help the user understand the system
and guide them to add knowledge sources through the admin panel."""

    try:
        answer = await ai_service.generate_response(  # ← Added await
            prompt=prompt,
            system_prompt=simple_prompt,
            temperature=0.7,
            max_tokens=500
        )
    except Exception as e:
        print(f"Simple response error: {e}")
        answer = f"Sorry, I encountered an error: {str(e)}"

    return answer