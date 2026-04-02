"""
Chat router - handles RAG chat conversations.
"""
import uuid 
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json
from datetime import datetime
from database import get_supabase
from models.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
)
from services.rag import generate_rag_response, generate_simple_response, get_system_prompt, get_rag_context
from services.embeddings import search_similar_documents
from services.ai import ai_service
from dependencies.auth import get_current_user_id

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Create a new conversation for the current user."""
    supabase = get_supabase()
    conv_id = str(uuid.uuid4())

    supabase.table("conversations").insert({
        "id": conv_id,
        "title": data.title,
        "user_id": user_id,
    }).execute()

    result = supabase.table("conversations").select('*').eq('id', conv_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create conversation")
    
    conv_data = result.data[0]

    return ConversationResponse(
        id=conv_data["id"],
        title=conv_data["title"],
        user_id=conv_data.get("user_id"),
        created_at=conv_data["created_at"],
        updated_at=conv_data["updated_at"],
        message_count=0,
    )


@router.get("/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_user_id)
):
    """List all conversations for current user"""
    supabase = get_supabase()

    query = supabase.table("conversations").select("*, messages(count)").eq("user_id", user_id).order("updated_at", desc=True)

    result = query.execute()

    conversations = []
    for conv in result.data:
        msg_count = conv.get("messages", [{}])[0].get("count", 0) if conv.get("messages") else 0
        conversations.append(ConversationResponse(
            id=conv["id"],
            user_id=conv.get("user_id"),
            title=conv["title"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            message_count=msg_count,
        ))

    return {"conversations": conversations, "total": len(conversations)}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get a conversation with all messages (must belong to current user)."""
    supabase = get_supabase()

    conv_result = supabase.table("conversations").select("*").eq("id", conversation_id).eq("user_id", user_id).execute()
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv_data = conv_result.data[0]

    msg_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()

    return {
        "conversation": conv_data,
        "messages": msg_result.data,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Delete a conversation and its messages (must belong to current user)."""
    supabase = get_supabase()

    check_result = supabase.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user_id).execute()
    if not check_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    supabase.table("conversations").delete().eq("id", conversation_id).execute()

    return {"message": "Conversation deleted"}


@router.post("/chat", response_model=ChatMessageResponse)
async def send_message(
    data: ChatMessageRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Send a message and get AI response using RAG."""
    supabase = get_supabase()

    conversation_id = data.conversation_id
    if not conversation_id:
        conv_id = str(uuid.uuid4())
        supabase.table("conversations").insert({
            "id": conv_id,
            "title": data.message[:50],
            "user_id": user_id,
        }).execute()
        conversation_id = conv_id
    else:
        conv_check = supabase.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user_id).execute()
        if not conv_check.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conv_result = supabase.table("conversations").select("*, messages(count)").eq("id", conversation_id).execute()
        if conv_result.data:
            conv_data = conv_result.data[0]
            msg_count = conv_data.get("messages", [{}])[0].get("count", 0) if conv_data.get("messages") else 0
            if msg_count == 0:
                supabase.table("conversations").update({
                    "title": data.message[:50],
                }).eq("id", conversation_id).execute()

    # Save user message
    msg_id = str(uuid.uuid4())
    supabase.table("messages").insert({
        "id": msg_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": "user",
        "content": data.message,
    }).execute()

    history_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_result.data[:-1]
    ]

    try:
        rag_result = await generate_rag_response(
            question=data.message,
            conversation_history=conversation_history,
        )
        ai_content = rag_result["answer"]
    except Exception as e:
        print(f"RAG failed, using fallback: {e}")
        try:
            ai_content = await generate_simple_response(data.message)
        except Exception as e2:
            ai_content = f"I'm currently unable to process your request. Error: {str(e2)}"

    # Save AI response
    ai_msg_id = str(uuid.uuid4())
    supabase.table("messages").insert({
        "id": ai_msg_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": "assistant",
        "content": ai_content,
    }).execute()

    ai_msg_result = supabase.table("messages").select('*').eq('id', ai_msg_id).execute()
    if not ai_msg_result.data:
        raise HTTPException(status_code=500, detail="Failed to save AI response")
    
    ai_msg_data = ai_msg_result.data[0]

    return ChatMessageResponse(
        message_id=ai_msg_data["id"],
        conversation_id=conversation_id,
        role="assistant",
        content=ai_content,
        created_at=ai_msg_data["created_at"],
    )


# ============ STREAMING ENDPOINT ============

@router.post("/chat/stream")
async def send_message_stream(
    data: ChatMessageRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Send a message and get streaming AI response (word by word)."""
    supabase = get_supabase()
    
    # Create conversation if not provided
    conversation_id = data.conversation_id
    if not conversation_id:
        conv_id = str(uuid.uuid4())
        supabase.table("conversations").insert({
            "id": conv_id,
            "title": data.message[:50],
            "user_id": user_id,
        }).execute()
        conversation_id = conv_id
    else:
        # Verify conversation belongs to user
        conv_check = supabase.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user_id).execute()
        if not conv_check.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Save user message
    msg_id = str(uuid.uuid4())
    supabase.table("messages").insert({
        "id": msg_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": "user",
        "content": data.message,
    }).execute()
    
    # Get conversation history
    history_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_result.data[:-1]
    ]
    
    # Retrieve relevant documents for RAG using shared isolated context pipeline
    context, sources = await get_rag_context(data.message)
    
    # Build conversation context
    conversation_context = ""
    if conversation_history:
        for msg in conversation_history[-6:]:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg['content']}\n"
    
    full_question = data.message
    if conversation_context:
        full_question = f"Previous conversation:\n{conversation_context}\n\nCurrent question: {data.message}"
    
    prompt = f"""Context information:
{context}

Question: {full_question}

Please provide a helpful answer based on the context above."""
    
    async def generate():
        full_response = ""
        async for chunk in ai_service.generate_stream_response(
            prompt=prompt,
            system_prompt=get_system_prompt(),
            temperature=0.3,
            max_tokens=2048
        ):
            full_response += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        # Save final response to database
        ai_msg_id = str(uuid.uuid4())
        supabase.table("messages").insert({
            "id": ai_msg_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "assistant",
            "content": full_response,
        }).execute()
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")