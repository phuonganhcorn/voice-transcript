from typing import Optional, List
from uuid import UUID
from src.database.repositories.conversation_repository import ConversationRepository
from src.database.repositories.transcription_repository import TranscriptionRepository
from src.database.repositories.message_repository import MessageRepository
from src.core.context import MediaContext, UserContexts

class ContextRepository:
    """Context repository using database - maintains compatibility with old interface"""
    
    def __init__(self):
        self.conversation_repo = ConversationRepository()
        self.transcription_repo = TranscriptionRepository()
        self.message_repo = MessageRepository()
    
    def get(self, user_id: int) -> Optional[UserContexts]:
        """Load all contexts for user (for compatibility)"""
        conversations = self.conversation_repo.get_user_conversations(str(user_id))
        if not conversations:
            return None
        
        # Find active conversation
        active_id = None
        for conv in conversations:
            if conv.is_active:
                active_id = conv.id
                break
        
        # Convert to MediaContext format
        contexts = []
        for conv in conversations:
            # Get transcription content
            transcription = self.transcription_repo.get_transcription_by_id(conv.transcription_id)
            transcription_text = transcription.content if transcription else ""
            
            # Get history
            history = self.message_repo.get_conversation_history(conv.id)
            
            # Convert to MediaContext
            context = MediaContext(
                user_id=int(conv.user_id),
                context_id=str(conv.id),
                transcription=transcription_text,
                title=conv.title or "",
                summary=conv.metadata.get('summary', '') if conv.metadata else '',
                duration_seconds=conv.metadata.get('duration_seconds', 0) if conv.metadata else 0,
                source_type=conv.source_type,
                transcript_file_path=conv.metadata.get('transcript_file_path') if conv.metadata else None,
                history=history
            )
            contexts.append(context)
        
        return UserContexts(
            user_id=user_id,
            contexts=contexts,
            active_context_id=str(active_id) if active_id else None
        )
    
    def save(self, user_contexts: UserContexts):
        """Save all contexts for user (for compatibility)"""
        # This is handled by individual add/update operations
        pass
    
    def get_active_context(self, user_id: int) -> Optional[MediaContext]:
        """Get active context for user"""
        conversation = self.conversation_repo.get_active_conversation(str(user_id))
        if not conversation:
            return None
        
        # Get transcription
        transcription = self.transcription_repo.get_transcription_by_id(conversation.transcription_id)
        transcription_text = transcription.content if transcription else ""
        
        # Get history
        history = self.message_repo.get_conversation_history(conversation.id)
        
        return MediaContext(
            user_id=int(conversation.user_id),
            context_id=str(conversation.id),
            transcription=transcription_text,
            title=conversation.title or "",
            summary=conversation.metadata.get('summary', '') if conversation.metadata else '',
            duration_seconds=conversation.metadata.get('duration_seconds', 0) if conversation.metadata else 0,
            source_type=conversation.source_type,
            transcript_file_path=conversation.metadata.get('transcript_file_path') if conversation.metadata else None,
            history=history
        )
    
    def add_context(self, user_id: int, context: MediaContext):
        """Add new context for user"""
        from uuid import UUID as UUIDType
        
        # Create transcription first
        transcription_id = self.transcription_repo.create_transcription(context.transcription)
        
        # Prepare metadata
        metadata = {
            "summary": context.summary,
            "duration_seconds": context.duration_seconds,
        }
        if context.transcript_file_path:
            metadata["transcript_file_path"] = context.transcript_file_path
        
        # Create conversation
        conversation_id = self.conversation_repo.create_conversation(
            user_id=str(user_id),
            transcription_id=transcription_id,
            title=context.title,
            platform='telegram',  # Will be set by handler
            metadata=metadata,
            source_type=context.source_type,
            conversation_id=UUIDType(context.id) if context.id else None
        )
        
        print(f"✅ Đã thêm context mới: {context.title}")
    
    def update_context(self, user_id: int, context: MediaContext):
        """Update existing context"""
        # Update conversation updated_at
        self.conversation_repo.update_conversation(UUID(context.id))
    
    def switch_context(self, user_id: int, context_id: str) -> bool:
        """Switch active context"""
        return self.conversation_repo.set_active_conversation(str(user_id), UUID(context_id))
    
    def delete_context(self, user_id: int, context_id: str) -> bool:
        """Delete a context"""
        return self.conversation_repo.delete_conversation(str(user_id), UUID(context_id))
    
    def delete(self, user_id: int):
        """Delete all contexts for user"""
        conversations = self.conversation_repo.get_user_conversations(str(user_id))
        for conv in conversations:
            self.conversation_repo.delete_conversation(str(user_id), conv.id)
        print(f"🗑️ Đã xóa tất cả contexts của user {user_id}")
    
    def get_context_by_id(self, user_id: int, context_id: str) -> Optional[MediaContext]:
        """Get context by ID"""
        conversation = self.conversation_repo.get_conversation_by_id(UUID(context_id))
        if not conversation or conversation.user_id != str(user_id):
            return None
        
        # Get transcription
        transcription = self.transcription_repo.get_transcription_by_id(conversation.transcription_id)
        transcription_text = transcription.content if transcription else ""
        
        # Get history
        history = self.message_repo.get_conversation_history(conversation.id)
        
        return MediaContext(
            user_id=int(conversation.user_id),
            context_id=str(conversation.id),
            transcription=transcription_text,
            title=conversation.title or "",
            summary=conversation.metadata.get('summary', '') if conversation.metadata else '',
            duration_seconds=conversation.metadata.get('duration_seconds', 0) if conversation.metadata else 0,
            source_type=conversation.source_type,
            transcript_file_path=conversation.metadata.get('transcript_file_path') if conversation.metadata else None,
            history=history
        )
    
    def get_user_contexts(self, user_id: int):
        """Get user contexts (alias for get)"""
        return self.get(user_id)
