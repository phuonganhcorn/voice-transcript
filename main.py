from telethon import events
from src.clients.telegram_client import TelegramBotClient
from src.repositories.user_repository import UserRepository
from src.repositories.context_repository import ContextRepository
from src.services.media_service import MediaService
from src.services.ai_service import AIService
from src.handlers.command_handler import CommandHandler
from src.handlers.message_handler import MessageHandler
from src.database.connection import db

# Initialize database
print("🔌 Initializing database connection...")
db.initialize()

# Initialize clients
telegram_client = TelegramBotClient()
client = telegram_client.get_client()

# Initialize repositories
user_repo = UserRepository()
context_repo = ContextRepository()

# Initialize services
media_service = MediaService()
ai_service = AIService()

# Initialize handlers
command_handler = CommandHandler(user_repo, context_repo)
message_handler = MessageHandler(client, user_repo, context_repo, media_service, ai_service)

# Register command handlers
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await command_handler.handle_start(event)

@client.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    await command_handler.handle_help(event)

@client.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    await command_handler.handle_clear(event)

@client.on(events.NewMessage(pattern='/list'))
async def list_handler(event):
    await command_handler.handle_list(event)

@client.on(events.NewMessage(pattern=r'/switch\s*(.*)'))
async def switch_handler(event):
    args = event.pattern_match.group(1)
    await command_handler.handle_switch(event, args)

@client.on(events.NewMessage(pattern=r'/delete\s*(.*)'))
async def delete_handler(event):
    args = event.pattern_match.group(1)
    await command_handler.handle_delete(event, args)

@client.on(events.NewMessage(pattern='/current'))
async def current_handler(event):
    await command_handler.handle_current(event)

# Register message handler
@client.on(events.NewMessage)
async def handler(event):
    await message_handler.handle(event)

async def main():
    print("🤖 Bot đã sẵn sàng!")
    print("📝 Bot sẽ chỉ xử lý tin nhắn từ users đã /start")
    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
