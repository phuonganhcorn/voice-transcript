from typing import Optional, Union
from src.core.user import User
from src.database.repositories.user_profile_repository import UserProfileRepository

class UserRepository:
    """User repository using database"""
    
    def __init__(self):
        self.profile_repo = UserProfileRepository()
    
    def exists(self, user_id: Union[int, str]) -> bool:
        """Check if user exists - accepts both int (Telegram) and str (Mobile UUID)"""
        return self.profile_repo.user_exists(str(user_id))
    
    def get(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        profile = self.profile_repo.get_user_profile(str(user_id))
        if profile:
            return User(
                user_id=int(profile.user_id),
                username=f"{profile.first_name or ''} {profile.last_name or ''}".strip() or None,
                started_at=profile.created_at.isoformat()
            )
        return None
    
    def save(self, user: User):
        """Save user (create or update profile)"""
        # Extract first_name and last_name from username if available
        first_name = None
        last_name = None
        if user.username:
            parts = user.username.split(maxsplit=1)
            first_name = parts[0] if parts else None
            last_name = parts[1] if len(parts) > 1 else None
        
        self.profile_repo.create_or_update_user_profile(
            user_id=str(user.user_id),
            first_name=first_name,
            last_name=last_name
        )
    
    def add_user(self, user_id: Union[int, str]):
        """Add a new user - accepts both int (Telegram) and str (Mobile UUID)"""
        # For mobile (string UUID), just create profile directly without User object
        if isinstance(user_id, str):
            self.profile_repo.create_or_update_user_profile(
                user_id=user_id,
                first_name=None,
                last_name=None
            )
        else:
            # For telegram (int), use User object
            user = User(user_id=user_id)
            self.save(user)
