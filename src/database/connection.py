import os
from typing import Optional
from supabase import create_client, Client
from src.config import Config

class Database:
    """Database connection manager using Supabase SDK"""
    
    def __init__(self):
        self.client: Optional[Client] = None
    
    def initialize(self):
        """Initialize Supabase client"""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                raise ValueError(
                    "Supabase credentials missing: Need SUPABASE_URL and SUPABASE_ANON_KEY in .env file"
                )
            
            self.client = create_client(supabase_url, supabase_key)
            print("✅ Supabase client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase client: {e}")
            raise
    
    def get_client(self) -> Client:
        """Get Supabase client"""
        if not self.client:
            raise RuntimeError("Supabase client not initialized. Call initialize() first.")
        return self.client
    
    def close(self):
        """Close Supabase client (no-op for SDK, but kept for compatibility)"""
        print("✅ Supabase client closed")

# Global database instance
db = Database()
