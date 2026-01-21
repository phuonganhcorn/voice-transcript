from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

@dataclass
class Transcription:
    """Transcription model"""
    transcription_id: UUID
    content: str
    created_at: datetime

@dataclass
class Conversation:
    """Conversation model"""
    id: UUID
    user_id: str
    transcription_id: UUID
    title: str
    platform: str
    metadata: dict
    source_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

@dataclass
class Message:
    """Message model"""
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    file_url: Optional[str]
    file_name: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    created_at: datetime

@dataclass
class UserProfile:
    """User profile model"""
    id: UUID
    user_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime
    updated_at: datetime

