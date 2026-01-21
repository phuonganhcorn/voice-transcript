from uuid import UUID
from typing import Optional
from datetime import datetime
from src.database.connection import db
from src.database.models import UserProfile

class UserProfileRepository:
    """Repository for managing user profiles using Supabase SDK"""
    
    def create_or_update_user_profile(
        self,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> UUID:
        """Create or update user profile"""
        client = db.get_client()
        
        from uuid import uuid4
        
        # Try to get existing profile
        existing = client.table('user_profiles').select('id').eq(
            'user_id', user_id
        ).execute()
        
        profile_data = {
            'user_id': user_id,
            'first_name': first_name,
            'last_name': last_name,
            'avatar_url': avatar_url
        }
        
        if existing.data and len(existing.data) > 0:
            # Update existing
            existing_id = UUID(existing.data[0]['id'])
            client.table('user_profiles').update(profile_data).eq(
                'id', str(existing_id)
            ).execute()
            print(f"✅ Updated user profile for {user_id}")
            return existing_id
        else:
            # Create new
            new_id = uuid4()
            profile_data['id'] = str(new_id)
            result = client.table('user_profiles').insert(profile_data).execute()
            print(f"✅ Created user profile for {user_id}")
            return new_id
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile by user_id"""
        client = db.get_client()
        
        result = client.table('user_profiles').select('*').eq(
            'user_id', user_id
        ).execute()
        
        if result.data and len(result.data) > 0:
            row = result.data[0]
            
            created_at = row.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            updated_at = row.get('updated_at')
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            
            return UserProfile(
                id=UUID(row['id']),
                user_id=row['user_id'],
                first_name=row.get('first_name'),
                last_name=row.get('last_name'),
                avatar_url=row.get('avatar_url'),
                created_at=created_at,
                updated_at=updated_at
            )
        return None
    
    def user_exists(self, user_id: str) -> bool:
        """Check if user profile exists"""
        profile = self.get_user_profile(user_id)
        return profile is not None
