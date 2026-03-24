"""
Chat router - handles RAG chat conversations.
"""
import uuid 
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
    conv_id = str(uuid.uuid4())

    # Insert the record
    supabase.table("conversations").insert({
        "id": conv_id,
        "title": data.title,
    }).execute()

    # Fetch the created record
    result = supabase.table("conversations").select('*').eq('id', conv_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create conversation")
    
    conv_data = result.data[0]

    return ConversationResponse(
        id=conv_data["id"],
        title=conv_data["title"],
        created_at=conv_data["created_at"],
        updated_at=conv_data["updated_at"],
        message_count=0,
    )


@router.get("/conversations")
async def list_conversations(user_id: str = None):
    """List all conversations."""
    supabase = get_supabase()

    query = supabase.table("conversations").select("*, messages(count)").order("updated_at", desc=True)  # ✅ Correct

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
    conv_result = supabase.table("conversations").select("*").eq("id", conversation_id).execute()
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv_data = conv_result.data[0]

    # Get messages - ✅ Fixed order syntax
    msg_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()

    return {
        "conversation": conv_data,
        "messages": msg_result.data,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    supabase = get_supabase()

    # Messages are deleted automatically via ON DELETE CASCADE
    result = supabase.table("conversations").delete().eq("id", conversation_id).execute()

    if not result.data:
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
    # ✅ Removed import uuid from here (now at top)

    # Create conversation if not provided
    conversation_id = data.conversation_id
    if not conversation_id:
        conv_id = str(uuid.uuid4())
        supabase.table("conversations").insert({
            "id": conv_id,
            "title": data.message[:50],
        }).execute()
        conversation_id = conv_id
    else:
        # Update conversation title if it's the first message
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
        "role": "user",
        "content": data.message,
    }).execute()

    # Fetch the saved user message
    user_msg_result = supabase.table("messages").select('*').eq('id', msg_id).execute()
    if not user_msg_result.data:
        raise HTTPException(status_code=500, detail="Failed to save message")

    # Get conversation history for context - ✅ Fixed order syntax
    history_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
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
    ai_msg_id = str(uuid.uuid4())
    supabase.table("messages").insert({
        "id": ai_msg_id,
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": ai_content,
    }).execute()

    # Fetch the saved AI response
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