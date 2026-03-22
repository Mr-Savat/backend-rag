"""
Chat router - handles RAG chat conversations.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from database import get_supabase
from models.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
)
from services.rag import generate_rag_response, generate_simple_response

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(data: ConversationCreate):
    """Create a new conversation."""
    supabase = get_supabase()

    result = supabase.table("conversations").insert({
        "title": data.title,
    }).select().single().execute()

    if result.data is None:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    return ConversationResponse(
        id=result.data["id"],
        title=result.data["title"],
        created_at=result.data["created_at"],
        updated_at=result.data["updated_at"],
        message_count=0,
    )


@router.get("/conversations")
async def list_conversations(user_id: str = None):
    """List all conversations."""
    supabase = get_supabase()

    query = supabase.table("conversations").select("*, messages(count)").order("updated_at", desc=True)

    if user_id:
        query = query.eq("user_id", user_id)

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
async def get_conversation(conversation_id: str):
    """Get a conversation with all messages."""
    supabase = get_supabase()

    # Get conversation
    conv_result = supabase.table("conversations").select("*").eq("id", conversation_id).single().execute()
    if conv_result.data is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    msg_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()

    return {
        "conversation": conv_result.data,
        "messages": msg_result.data,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    supabase = get_supabase()

    # Messages are deleted automatically via ON DELETE CASCADE
    result = supabase.table("conversations").delete().eq("id", conversation_id).execute()

    if result.data is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted"}


@router.post("/chat", response_model=ChatMessageResponse)
async def send_message(data: ChatMessageRequest):
    """
    Send a message and get AI response using RAG.

    Flow:
    1. Save user message to database
    2. Retrieve relevant knowledge using RAG
    3. Generate AI response
    4. Save AI response to database
    5. Return AI response
    """
    supabase = get_supabase()

    # Create conversation if not provided
    conversation_id = data.conversation_id
    if not conversation_id:
        conv_result = supabase.table("conversations").insert({
            "title": data.message[:50],
        }).select().single().execute()
        conversation_id = conv_result.data["id"]
    else:
        # Update conversation title if it's the first message
        conv = supabase.table("conversations").select("messages(count)").eq("id", conversation_id).single().execute()
        msg_count = conv.data.get("messages", [{}])[0].get("count", 0) if conv.data.get("messages") else 0
        if msg_count == 0:
            supabase.table("conversations").update({
                "title": data.message[:50],
            }).eq("id", conversation_id).execute()

    # Save user message
    user_msg = supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": data.message,
    }).select().single().execute()

    if user_msg.data is None:
        raise HTTPException(status_code=500, detail="Failed to save message")

    # Get conversation history for context
    history_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()
    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_result.data[:-1]  # Exclude current message
    ]

    # Generate RAG response
    try:
        rag_result = generate_rag_response(
            question=data.message,
            conversation_history=conversation_history,
        )
        ai_content = rag_result["answer"]
    except Exception as e:
        # Fallback to simple response if RAG fails (e.g., no vector store configured)
        print(f"RAG failed, using fallback: {e}")
        try:
            ai_content = generate_simple_response(data.message)
        except Exception as e2:
            ai_content = f"I'm currently unable to process your request. Error: {str(e2)}"

    # Save AI response
    ai_msg = supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": ai_content,
    }).select().single().execute()

    if ai_msg.data is None:
        raise HTTPException(status_code=500, detail="Failed to save AI response")

    return ChatMessageResponse(
        message_id=ai_msg.data["id"],
        conversation_id=conversation_id,
        role="assistant",
        content=ai_content,
        created_at=ai_msg.data["created_at"],
    )
