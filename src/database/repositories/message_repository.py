from uuid import UUID
from typing import Optional, List, Dict
from datetime import datetime
from src.database.connection import db
from src.database.models import Message

class MessageRepository:
    """Repository for managing conversation messages using Supabase SDK"""
    
    def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> UUID:
        """Add a message to conversation"""
        client = db.get_client()
        
        from uuid import uuid4
        message_id = uuid4()
        
        result = client.table('messages').insert({
            'id': str(message_id),
            'conversation_id': str(conversation_id),
            'role': role,
            'content': content,
            'file_url': file_url,
            'file_name': file_name,
            'file_type': file_type,
            'file_size': file_size
        }).execute()
        
        return message_id
    
    def get_conversation_history(
        self,
        conversation_id: UUID,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get conversation history"""
        client = db.get_client()
        
        query = client.table('messages').select(
            'role, content, file_url, file_name, file_type, file_size, created_at'
        ).eq('conversation_id', str(conversation_id)).order('created_at', desc=False)
        
        if limit:
            query = query.limit(limit)
        
        result = query.execute()
        
        if result.data:
            return [
                {
                    "role": row['role'],
                    "content": row['content'],
                    "file_url": row.get('file_url'),
                    "file_name": row.get('file_name'),
                    "file_type": row.get('file_type'),
                    "file_size": row.get('file_size')
                }
                for row in result.data
            ]
        return []
