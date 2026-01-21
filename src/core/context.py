from datetime import datetime
from typing import List, Dict, Optional
import uuid

class MediaContext:
    """Single context for one audio/video transcription"""
    def __init__(self, user_id: int, transcription: str = "", title: str = "", 
                 summary: str = "", context_id: Optional[str] = None, 
                 history: Optional[List[Dict]] = None, duration_seconds: int = 0,
                 source_type: str = "audio", transcript_file_path: Optional[str] = None):
        self.user_id = user_id
        self.id = context_id or self._generate_id()
        self.title = title
        self.summary = summary
        self.transcription = transcription
        self.timestamp = datetime.now().isoformat()
        self.duration_seconds = duration_seconds
        self.source_type = source_type  # audio, video, voice_message
        self.transcript_file_path = transcript_file_path  # Path to saved transcript file for very long texts
        self.history = history or []
    
    def _generate_id(self) -> str:
        """Generate unique context ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"ctx_{timestamp}_{short_uuid}"
    
    def add_to_history(self, user_msg: str, ai_msg: str):
        """Add conversation turn to history"""
        self.history.extend([
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": ai_msg}
        ])
    
    def get_message_count(self) -> int:
        """Get number of user messages"""
        return len([m for m in self.history if m["role"] == "user"])
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "transcription": self.transcription,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "source_type": self.source_type,
            "transcript_file_path": self.transcript_file_path,
            "history": self.history
        }
    
    @classmethod
    def from_dict(cls, user_id: int, data: dict):
        """Create from dictionary"""
        return cls(
            user_id=user_id,
            context_id=data.get("id"),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            transcription=data.get("transcription", ""),
            duration_seconds=data.get("duration_seconds", 0),
            source_type=data.get("source_type", "audio"),
            transcript_file_path=data.get("transcript_file_path"),
            history=data.get("history", [])
        )


class UserContexts:
    """Manager for all contexts of a user"""
    def __init__(self, user_id: int, contexts: Optional[List[MediaContext]] = None,
                 active_context_id: Optional[str] = None):
        self.user_id = user_id
        self.contexts = contexts or []
        self.active_context_id = active_context_id
    
    def add_context(self, context: MediaContext):
        """Add new context and set as active"""
        self.contexts.append(context)
        self.active_context_id = context.id
    
    def get_active_context(self) -> Optional[MediaContext]:
        """Get currently active context"""
        if not self.active_context_id:
            return None
        for ctx in self.contexts:
            if ctx.id == self.active_context_id:
                return ctx
        return None
    
    def get_context_by_id(self, context_id: str) -> Optional[MediaContext]:
        """Get context by ID"""
        for ctx in self.contexts:
            if ctx.id == context_id:
                return ctx
        return None
    
    def get_context_by_index(self, index: int) -> Optional[MediaContext]:
        """Get context by display index (1-based)"""
        if 1 <= index <= len(self.contexts):
            return self.contexts[index - 1]
        return None
    
    def switch_context(self, context_id: str) -> bool:
        """Switch active context"""
        if any(ctx.id == context_id for ctx in self.contexts):
            self.active_context_id = context_id
            return True
        return False
    
    def delete_context(self, context_id: str) -> bool:
        """Delete a context"""
        initial_len = len(self.contexts)
        self.contexts = [ctx for ctx in self.contexts if ctx.id != context_id]
        
        # If deleted context was active, switch to most recent
        if self.active_context_id == context_id:
            self.active_context_id = self.contexts[0].id if self.contexts else None
        
        return len(self.contexts) < initial_len
    
    def archive_current_context(self):
        """Mark current context as archived (just deactivate)"""
        self.active_context_id = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "contexts": [ctx.to_dict() for ctx in self.contexts],
            "active_context_id": self.active_context_id
        }
    
    @classmethod
    def from_dict(cls, user_id: int, data: dict):
        """Create from dictionary"""
        contexts = [MediaContext.from_dict(user_id, ctx_data) 
                   for ctx_data in data.get("contexts", [])]
        return cls(
            user_id=user_id,
            contexts=contexts,
            active_context_id=data.get("active_context_id")
        )

