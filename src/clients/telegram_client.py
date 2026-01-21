from telethon import TelegramClient
from src.config import API_ID, API_HASH, SESSION_NAME

class TelegramBotClient:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    def get_client(self):
        """Get Telegram client instance"""
        return self.client

