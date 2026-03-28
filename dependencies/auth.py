# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# import httpx
# import os
# from typing import Optional

# from dotenv import load_dotenv

# # Load .env
# load_dotenv()

# security = HTTPBearer()

# security = HTTPBearer()

# async def verify_supabase_token(token: str) -> dict:
#     """Verify JWT token with Supabase"""
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.get(
#                 f"{settings.supabase_url}/auth/v1/user",
#                 headers={
#                     "Authorization": f"Bearer {token}",
#                     "apikey": settings.supabase_anon_key,
#                 }
#             )
            
#             if response.status_code != 200:
#                 raise HTTPException(
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                     detail="Invalid authentication token",
#                 )
            
#             return response.json()
            
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=f"Authentication failed: {str(e)}",
#         )

# async def get_current_user(
#     credentials: HTTPAuthorizationCredentials = Depends(security)
# ) -> dict:
#     """Get current user from JWT token"""
#     token = credentials.credentials
#     user = await verify_supabase_token(token)
#     return user

# async def get_current_user_id(
#     user: dict = Depends(get_current_user)
# ) -> str:
#     """Get current user ID"""
#     return user.get("id")

# async def get_current_user_role(
#     user: dict = Depends(get_current_user)
# ) -> str:
#     """Get current user's role from profiles table"""
#     supabase = get_supabase()
    
#     try:
#         result = supabase.table("profiles").select("role").eq("id", user.get("id")).execute()
        
#         if result.data:
#             return result.data[0].get("role", "user")
#         return "user"
#     except Exception as e:
#         print(f"Error getting user role: {e}")
#         return "user"

# async def require_admin(
#     user_id: str = Depends(get_current_user_id),
#     role: str = Depends(get_current_user_role)
# ) -> str:
#     """Require admin role for access"""
#     if role != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Admin access required"
#         )
#     return user_id




# true




from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from config import settings
from database import get_supabase

security = HTTPBearer()

async def verify_supabase_token(token: str) -> dict:
    """Verify JWT token with Supabase"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_anon_key,
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                )
            
            return response.json()
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Get current user from JWT token"""
    token = credentials.credentials
    user = await verify_supabase_token(token)
    return user

async def get_current_user_id(
    user: dict = Depends(get_current_user)
) -> str:
    """Get current user ID"""
    return user.get("id")

async def get_current_user_role(
    user: dict = Depends(get_current_user)
) -> str:
    """Get current user's role from profiles table"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("profiles").select("role").eq("id", user.get("id")).execute()
        
        if result.data:
            return result.data[0].get("role", "user")
        return "user"
    except Exception as e:
        print(f"Error getting user role: {e}")
        return "user"

async def require_admin(
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role)
) -> str:
    """Require admin role for access"""
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user_id