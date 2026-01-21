from datetime import datetime
from typing import Optional

class User:
    def __init__(self, user_id: int, username: Optional[str] = None, started_at: Optional[str] = None):
        self.user_id = user_id
        self.username = username
        self.started_at = started_at or datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "username": self.username,
            "started_at": self.started_at
        }
    
    @classmethod
    def from_dict(cls, user_id: int, data: dict):
        return cls(
            user_id=user_id,
            username=data.get("username"),
            started_at=data.get("started_at")
        )

