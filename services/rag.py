"""
RAG (Retrieval-Augmented Generation) service using LangChain + Google Gemini.
"""
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import settings
from services.embeddings import search_similar_documents


# System prompt for the AI
SYSTEM_PROMPT = """You are an AI Knowledge Assistant for a Conversational AI Knowledge System. 
Your role is to provide accurate, helpful answers based on the retrieved knowledge base content.

Rules:
- Answer based ONLY on the provided context. If the context doesn't contain relevant information, say so.
- Be concise but thorough. Use formatting (bullet points, numbered lists) when appropriate.
- If you're unsure, acknowledge it rather than guessing.
- Cite the source when possible (e.g., "According to the Academic Handbook...").
- Respond in the same language as the user's question.
"""

RAG_PROMPT_TEMPLATE = """{system_prompt}

=== Retrieved Knowledge ===
{context}

=== User Question ===
{question}

Please provide a helpful answer based on the retrieved knowledge above. If the knowledge doesn't contain relevant information to answer the question, let the user know politely."""


def get_chat_model() -> ChatGoogleGenerativeAI:
    """
    Get Google Gemini chat model instance.
    """
    if settings.google_api_key == "your_google_api_key_here":
        raise ValueError(
            "GOOGLE_API_KEY is not set. Please set it in backend/.env"
        )

    return ChatGoogleGenerativeAI(
        model=settings.chat_model,
        google_api_key=settings.google_api_key,
        temperature=0.3,  # Lower temperature for more factual responses
        max_output_tokens=2048,
    )


def generate_rag_response(
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
            f"[Document {i}] (Source: {doc['metadata'].get('title', 'Unknown')})\n{doc['content']}"
        )
        sources.append({
            "title": doc["metadata"].get("title", "Unknown"),
            "source_id": doc["metadata"].get("source_id"),
        })

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # Step 3: Build conversation context
    conversation_context = ""
    if conversation_history:
        recent_history = conversation_history[-6:]  # Last 3 exchanges
        for msg in recent_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg['content']}\n"

    # Step 4: Generate response using LLM
    chat_model = get_chat_model()

    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

    chain = prompt | chat_model | StrOutputParser()

    full_question = question
    if conversation_context:
        full_question = f"Previous conversation:\n{conversation_context}\n\nCurrent question: {question}"

    answer = chain.invoke({
        "system_prompt": SYSTEM_PROMPT,
        "context": context,
        "question": full_question,
    })

    return {
        "answer": answer,
        "sources": sources,
        "chunks_retrieved": len(retrieved_docs),
    }


def generate_simple_response(question: str) -> str:
    """
    Generate a response without RAG (fallback for when no knowledge base exists).
    Uses Gemini directly.

    Args:
        question: User's question

    Returns:
        Generated response string
    """
    chat_model = get_chat_model()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful AI assistant for a Knowledge Management System.
Currently, the knowledge base is empty or not configured. Help the user understand the system
and guide them to add knowledge sources through the admin panel."""),
        ("human", "{question}"),
    ])

    chain = prompt | chat_model | StrOutputParser()

    return chain.invoke({"question": question})
