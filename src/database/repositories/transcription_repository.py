from uuid import UUID
from typing import Optional
from datetime import datetime
from src.database.connection import db
from src.database.models import Transcription

class TranscriptionRepository:
    """Repository for managing transcriptions using Supabase SDK"""
    
    def create_transcription(self, content: str) -> UUID:
        """Create a new transcription and return its ID"""
        client = db.get_client()
        
        # Generate UUID
        from uuid import uuid4
        transcription_id = uuid4()
        
        # Insert into database
        result = client.table('transcriptions').insert({
            'transcription_id': str(transcription_id),
            'content': content
        }).execute()
        
        print(f"✅ Created transcription {transcription_id}")
        return transcription_id
    
    def get_transcription_by_id(self, transcription_id: UUID) -> Optional[Transcription]:
        """Get transcription by ID"""
        client = db.get_client()
        
        result = client.table('transcriptions').select('*').eq(
            'transcription_id', str(transcription_id)
        ).execute()
        
        if result.data and len(result.data) > 0:
            row = result.data[0]
            return Transcription(
                transcription_id=UUID(row['transcription_id']),
                content=row['content'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            )
        return None
