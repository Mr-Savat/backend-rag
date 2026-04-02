from fastapi import APIRouter, Depends, HTTPException
from database import get_supabase
from dependencies.auth import get_current_user_id, require_admin
from datetime import datetime, timedelta
import json

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/dashboard")
async def get_dashboard_analytics(user_id: str = Depends(require_admin)):
    """Fetch aggregated analytics for the admin dashboard."""
    supabase = get_supabase()
    
    # Calculate cutoff for the last 7 days
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    seven_days_ago_iso = seven_days_ago.isoformat()

    try:
        # 1. Total Sources
        ks_res = supabase.table("knowledge_sources").select("id", count="exact").execute()
        ds_res = supabase.table("data_sources").select("id", count="exact").execute()
        total_sources = (ks_res.count or len(ks_res.data)) + (ds_res.count or len(ds_res.data))

        # 2. Total Conversations
        conv_res = supabase.table("conversations").select("id, user_id, created_at").execute()
        all_conversations = conv_res.data

        # 3. Total Users and Active Users
        msg_res = supabase.table("messages").select("user_id, created_at").execute()
        all_messages = msg_res.data

        # Calculate Total Users from profiles table
        prof_res = supabase.table("profiles").select("id", count="exact").execute()
        total_users = prof_res.count or len(prof_res.data)

        # Calculate Active Users (active in the last 7 days)
        active_users_set = set()
        for c in all_conversations:
            if c.get("created_at") and c.get("created_at") >= seven_days_ago_iso:
                active_users_set.add(c.get("user_id"))
        for m in all_messages:
            if m.get("created_at") and m.get("created_at") >= seven_days_ago_iso:
                active_users_set.add(m.get("user_id"))
        active_users = len(active_users_set)

        # 4. Chart Data (Last 7 Days)
        # Initialize dictionary for the last 7 days
        chart_data_dict = {}
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            # Use 'short' day name matching the frontend (e.g., 'Mon', 'Tue')
            day_name = d.strftime('%a')
            chart_data_dict[d.strftime('%Y-%m-%d')] = {
                "name": day_name,
                "conversations": 0,
                "users": set()
            }

        # Aggregate Conversations
        for c in all_conversations:
            if not c.get("created_at"): continue
            # Handle standard ISO formats, splitting at 'T' or space
            date_str = c.get("created_at")[:10]
            if date_str in chart_data_dict:
                chart_data_dict[date_str]["conversations"] += 1
                chart_data_dict[date_str]["users"].add(c.get("user_id"))

        # Aggregate Users from messages just in case they sent messages without creating a new convo
        for m in all_messages:
            if not m.get("created_at"): continue
            date_str = m.get("created_at")[:10]
            if date_str in chart_data_dict:
                chart_data_dict[date_str]["users"].add(m.get("user_id"))

        # Format chart data for frontend
        chart_data = []
        # Need to sort keys chronologically
        for date_key in sorted(chart_data_dict.keys()):
            entry = chart_data_dict[date_key]
            chart_data.append({
                "name": entry["name"],
                "conversations": entry["conversations"],
                "users": len(entry["users"])
            })

        # 5. Popular Queries
        # Get recent user messages
        recent_msg_res = supabase.table("messages").select("content").eq("role", "user").order("created_at", desc=True).limit(50).execute()
        
        # Simple frequency count of raw contents
        query_freq = {}
        for msg in recent_msg_res.data:
            text = msg["content"].strip()
            # Ignore extremely short greetings if we want
            if len(text) > 4:
                query_freq[text] = query_freq.get(text, 0) + 1

        # Sort by frequency
        sorted_queries = sorted(query_freq.items(), key=lambda x: x[1], reverse=True)
        popular_questions = []
        for idx, (text, freq) in enumerate(sorted_queries[:5]):
            popular_questions.append({
                "id": idx + 1,
                "text": text,
                "frequency": freq,
                "trend": "up" if idx < 2 else "stable" # Mock trend for now
            })

        return {
            "stats": {
                "totalSources": total_sources,
                "totalConversations": len(all_conversations),
                "totalUsers": total_users,
                "activeUsers": active_users,
            },
            "chartData": chart_data,
            "popularQueries": popular_questions
        }

    except Exception as e:
        print(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load analytics data")
