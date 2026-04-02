"""
RAG (Retrieval-Augmented Generation) service supporting multiple AI providers.
"""
from typing import List, Optional
from services.embeddings import search_similar_documents
from services.ai import ai_service
from config import settings


# System prompt for the AI
SYSTEM_PROMPT = """You are an AI Knowledge Assistant for a Conversational AI Knowledge System. 
Your role is to provide accurate, helpful answers based strictly on the retrieved knowledge base content.

CRITICAL RULES FOR CONTEXT ISOLATION:
- You will be provided with multiple text chunks from different documents.
- DO NOT mix or merge attributes, facts, or descriptions between different documents. Treat each document as belonging to a distinct subject or person.

FORMATTING RULES:
- ALWAYS structure your response cleanly. Avoid long blocked paragraphs.
- Use **bold** text to emphasize key terms, names, or locations.
- Use bullet points (`- `) or numbered lists (`1. `) whenever explaining multiple points, features, or details.
- Use `###` headers to break up different sections if the answer is long.
- Keep sentences concise and easy to read.

GENERAL RULES:
- Answer based ONLY on the provided context. If the context doesn't contain relevant information, say so.
- DO NOT include internal system citations like [Document X | Source: ...] in your final answers.
- If you're unsure, acknowledge it rather than guessing.
- Respond in the same language as the user's question.
"""


async def reformulate_query(question: str, conversation_history: Optional[List[dict]] = None) -> str:
    """Rewrite query based on chat history using extremely fast LLM inference."""
    if not conversation_history or len(conversation_history) == 0:
        return question
        
    recent_history = conversation_history[-6:]
    history_str = "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in recent_history])
    
    prompt = f"""Given the following conversation history and the user's latest question, rewrite the question to be a completely standalone query that includes all necessary context from the history.
DO NOT answer the question. JUST return the rewritten query. Keep it under 20 words.
History:
{history_str}
Latest Question: {question}
Rewritten Query:"""

    try:
        rewritten = await ai_service.generate_response(
            prompt=prompt,
            system_prompt="You are a helpful query re-writer. Only output the rewritten query without any quotes or explanations.",
            temperature=0.0,
            max_tokens=30
        )
        return rewritten.replace("Rewritten Query:", "").strip().strip('"\'')
    except Exception as e:
        print(f"Query reformulation error: {e}")
        return question

# Global Ranker lazy initialization
_ranker = None
def get_ranker():
    global _ranker
    if _ranker is None:
        try:
            from flashrank import Ranker
            # The lightest, fastest ONNX model
            _ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="/tmp") 
        except ImportError:
            print("Warning: flashrank not installed. Reranking will be skipped.")
            return None
    return _ranker

async def generate_rag_response(
    question: str,
    conversation_history: Optional[List[dict]] = None,
    source_id: Optional[str] = None,
) -> dict:
    """
    Generate a response using High-Performance RAG.
    """
    # Step 0: Contextualize the query
    standalone_query = await reformulate_query(question, conversation_history)
    print(f"Original: {question} | Standalone: {standalone_query}")

    # Step 1: Retrieve a LARGER pool of candidate documents (e.g., top 15)
    retrieved_docs = search_similar_documents(
        query=standalone_query,
        k=15, 
        source_id=source_id,
    )

    # Step 2: Re-rank the candidates to find the absolute best Top 4-5
    final_docs = []
    ranker = get_ranker()
    
    if ranker and retrieved_docs:
        try:
            from flashrank import RerankRequest
            passages = []
            for i, doc in enumerate(retrieved_docs):
                passages.append({
                    "id": i,
                    "text": doc["content"],
                    "meta": doc["metadata"]
                })
                
            rerank_request = RerankRequest(query=standalone_query, passages=passages)
            results = ranker.rerank(rerank_request)
            
            # Select ultimate Top 5
            top_results = results[:5]
            final_docs = [{"content": r["text"], "metadata": r["meta"]} for r in top_results]
        except Exception as e:
            print(f"Reranking error: {e}. Falling back to default retrieval.")
            final_docs = retrieved_docs[:5]
    else:
        # Fallback if no ranker
        final_docs = retrieved_docs[:5]

    # Step 3: Build context from retrieved documents
    context_parts = []
    sources = []

    for i, doc in enumerate(final_docs, 1):
        # Extract title or filename for context injection to prevent Entity Bleed
        title = doc["metadata"].get("title", doc["metadata"].get("file_path", "Unknown Document"))
        
        context_parts.append(
            f"[Document {i} | Source: {title}]\n{doc['content']}"
        )
        sources.append({
            "title": doc["metadata"].get("title", "Unknown"),
            "source_id": doc["metadata"].get("source_id"),
        })

    context = "\n\n---\n\n".join(
        context_parts) if context_parts else "No relevant documents found."

    # Step 4: Build conversation context for LLM response
    conversation_context = ""
    if conversation_history:
        recent_history = conversation_history[-6:]  # Last 3 exchanges
        for msg in recent_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg['content']}\n"

    # Step 5: Build final prompt
    full_question = question
    if conversation_context:
        full_question = f"Previous conversation:\n{conversation_context}\n\nCurrent question: {question}"

    prompt = f"""Context information:
{context}

Question: {full_question}

Please provide a helpful answer based on the context above."""

    # Step 6: Generate response using AI
    try:
        answer = await ai_service.generate_response(  
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
        "chunks_retrieved": len(final_docs),
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
