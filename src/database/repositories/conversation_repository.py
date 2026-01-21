from uuid import UUID, uuid4
from typing import Optional, List
from datetime import datetime
from src.database.connection import db
from src.database.models import Conversation

class ConversationRepository:
    """Repository for managing conversations using Supabase SDK"""
    
    def create_conversation(
        self,
        user_id: str,
        transcription_id: UUID,
        title: str,
        platform: str,
        metadata: dict,
        source_type: str,
        conversation_id: Optional[UUID] = None
    ) -> UUID:
        """
        Create a new conversation
        
        Args:
            user_id: User ID
            transcription_id: Transcription ID to link
            title: Conversation title
            platform: 'telegram' or 'mobile'
            metadata: JSON metadata
            source_type: 'audio', 'video', etc.
            conversation_id: Optional conversation ID (Telegram/Mobile tự tạo)
        
        Returns:
            UUID of created conversation
        """
        client = db.get_client()
        
        # Generate UUID if not provided (for Telegram)
        if conversation_id is None:
            conversation_id = uuid4()
        
        # Deactivate all other conversations for this user
        self.deactivate_all_conversations(user_id)
        
        # Insert new conversation
        result = client.table('conversations').insert({
            'id': str(conversation_id),
            'user_id': user_id,
            'transcription_id': str(transcription_id),
            'title': title,
            'platform': platform,
            'metadata': metadata,
            'source_type': source_type,
            'is_active': True
        }).execute()
        
        if result.data and len(result.data) > 0:
            created_id = UUID(result.data[0]['id'])
            print(f"✅ Created conversation {created_id} for user {user_id} with transcript {transcription_id}")
            return created_id
        
        return conversation_id
    
    def get_active_conversation(self, user_id: str) -> Optional[Conversation]:
        """Get active conversation for user"""
        client = db.get_client()
        
        # Get active conversation (Supabase SDK doesn't support JOIN easily, 
        # so we get conversation first, then fetch transcription if needed)
        result = client.table('conversations').select('*').eq(
            'user_id', user_id
        ).eq('is_active', True).order('updated_at', desc=True).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            row = result.data[0]
            return self._row_to_conversation(row)
        return None
    
    def get_conversation_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        """Get conversation by ID"""
        client = db.get_client()
        
        result = client.table('conversations').select('*').eq(
            'id', str(conversation_id)
        ).execute()
        
        if result.data and len(result.data) > 0:
            return self._row_to_conversation(result.data[0])
        return None
    
    def get_user_conversations(self, user_id: str) -> List[Conversation]:
        """Get all conversations for a user"""
        client = db.get_client()
        
        result = client.table('conversations').select('*').eq(
            'user_id', user_id
        ).order('created_at', desc=True).execute()
        
        if result.data:
            return [self._row_to_conversation(row) for row in result.data]
        return []
    
    def set_active_conversation(self, user_id: str, conversation_id: UUID) -> bool:
        """Set a conversation as active (deactivates others)"""
        client = db.get_client()
        
        # First check if conversation exists and belongs to user
        check_result = client.table('conversations').select('id').eq(
            'id', str(conversation_id)
        ).eq('user_id', user_id).execute()
        
        if not check_result.data or len(check_result.data) == 0:
            return False
        
        # Deactivate all conversations for this user
        client.table('conversations').update({
            'is_active': False
        }).eq('user_id', user_id).execute()
        
        # Activate the specified conversation
        client.table('conversations').update({
            'is_active': True
        }).eq('id', str(conversation_id)).eq('user_id', user_id).execute()
        
        print(f"✅ Set conversation {conversation_id} as active for user {user_id}")
        return True
    
    def deactivate_all_conversations(self, user_id: str) -> None:
        """Deactivate all conversations for a user"""
        client = db.get_client()
        
        client.table('conversations').update({
            'is_active': False
        }).eq('user_id', user_id).eq('is_active', True).execute()
    
    def delete_conversation(self, user_id: str, conversation_id: UUID) -> bool:
        """Delete a conversation"""
        client = db.get_client()
        
        result = client.table('conversations').delete().eq(
            'id', str(conversation_id)
        ).eq('user_id', user_id).execute()
        
        if result.data and len(result.data) > 0:
            print(f"✅ Deleted conversation {conversation_id} for user {user_id}")
            return True
        return False
    
    def update_conversation(self, conversation_id: UUID) -> None:
        """Update conversation updated_at timestamp"""
        client = db.get_client()
        
        # Supabase auto-updates updated_at via trigger, but we can force update
        client.table('conversations').update({
            'updated_at': datetime.now().isoformat()
        }).eq('id', str(conversation_id)).execute()
    
    def _row_to_conversation(self, row: dict) -> Conversation:
        """Convert database row to Conversation model"""
        import json
        
        metadata = row.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        
        created_at = row.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        updated_at = row.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        
        return Conversation(
            id=UUID(row['id']),
            user_id=row['user_id'],
            transcription_id=UUID(row['transcription_id']),
            title=row.get('title', ''),
            platform=row.get('platform', 'telegram'),
            metadata=metadata,
            source_type=row.get('source_type', 'audio'),
            is_active=row.get('is_active', False),
            created_at=created_at,
            updated_at=updated_at
        )
