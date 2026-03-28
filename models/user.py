"""
User models for database and API.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    """User profile in database."""
    id: str
    email: str
    name: Optional[str] = None
    role: str = "user"
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    """Update user profile."""
    name: Optional[str] = None
    avatar_url: Optional[str] = None