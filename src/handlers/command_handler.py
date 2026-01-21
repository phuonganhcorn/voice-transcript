from datetime import datetime
from src.core.user import User
from src.repositories.user_repository import UserRepository
from src.repositories.context_repository import ContextRepository
from src.utils.formatters import format_duration, format_date_compact, truncate_with_ellipsis, format_source_emoji

class CommandHandler:
    def __init__(self, user_repo: UserRepository, context_repo: ContextRepository):
        self.user_repo = user_repo
        self.context_repo = context_repo
    
    async def handle_start(self, event):
        """Handle /start command - Check và lưu vào database"""
        sender = await event.get_sender()
        user_id = sender.id
        username = getattr(sender, 'username', None) or sender.first_name or "User"
        
        # Check user exists in database
        if self.user_repo.exists(user_id):
            await event.reply(
                f"👋 Hello {username}!\n\n"
                "You are already registered. Send me audio or video and I will transcribe it for you!\n\n"
                "📋 Commands:\n"
                "/list - View your conversations\n"
                "/current - See your current conversation\n"
                "/clear - Delete all conversations\n"
                "/help - Usage instructions"
            )
        else:
            # Create user in database
            user = User(
                user_id=user_id,
                username=username,
                started_at=datetime.now().isoformat()
            )
            self.user_repo.save(user)  # Lưu vào database (user_profiles table)
            await event.reply(
                f"🎉 Welcome, {username}!\n\n"
                "I can help you with:\n"
                "• Transcribing audio/video\n"
                "• Answering questions about the content\n"
                "• Managing multiple conversations\n\n"
                "Send an audio or video file to get started!\n\n"
                "📋 Commands:\n"
                "/list - View your conversations\n"
                "/help - Instructions"
            )
    
    async def handle_clear(self, event):
        """Handle /clear command"""
        sender = await event.get_sender()
        user_id = sender.id
        
        self.context_repo.delete(user_id)
        await event.reply("✅ Đã xóa tất cả conversations!")
    
    async def handle_help(self, event):
        """Handle /help command"""
        help_text = """
📖 **How to Use**

**Basics:**
• Send audio/video → automatic transcription
• Send text → chat about the current video
• New video → old video is archived automatically

**Commands:**
/list - View all conversations
/switch <num> - Switch to another conversation
/delete <num> - Delete a conversation
/current - Show the current conversation
/clear - Delete all conversations
/help - Show this help message

**Examples:**
/list → View your conversations
/switch 2 → Switch to #2
/delete 3 → Delete #3
        """
        await event.reply(help_text.strip())
    
    async def handle_list(self, event):
        """Handle /list command - show all contexts"""
        sender = await event.get_sender()
        user_id = sender.id
        
        user_contexts = self.context_repo.get(user_id)
        
        if not user_contexts or not user_contexts.contexts:
            await event.reply(
                "📚 Chưa có conversation nào.\n\n"
                "Gửi audio/video để bắt đầu!"
            )
            return
        
        # Build message
        lines = [f"📚 Conversations ({len(user_contexts.contexts)})\n"]
        
        for i, ctx in enumerate(user_contexts.contexts, 1):
            # Active indicator
            emoji = "🟢" if ctx.id == user_contexts.active_context_id else "⚪"
            
            # Truncate title
            title = truncate_with_ellipsis(ctx.title, 35)
            
            # Format metadata
            date = format_date_compact(ctx.timestamp)
            duration = format_duration(ctx.duration_seconds)
            msg_count = ctx.get_message_count()
            source_emoji = format_source_emoji(ctx.source_type)
            
            # Add context info
            lines.append(f"{emoji} {i}. {title}")
            lines.append(f"   {date} • {source_emoji} {duration} • {msg_count} msgs")
            
            # Add summary if exists
            if ctx.summary:
                summary = truncate_with_ellipsis(ctx.summary, 80)
                lines.append(f'   "{summary}"')
            
            lines.append("")  # Empty line between contexts
        
        # Add navigation help
        lines.append("─────────────────")
        lines.append("/switch <num> • /delete <num>")
        
        await event.reply("\n".join(lines))
    
    async def handle_switch(self, event, args: str):
        """Handle /switch <number> command"""
        sender = await event.get_sender()
        user_id = sender.id
        
        if not args or not args.strip().isdigit():
            await event.reply("❌ Sử dụng: /switch <số>\n\nVí dụ: /switch 2")
            return
        
        index = int(args.strip())
        user_contexts = self.context_repo.get(user_id)
        
        if not user_contexts:
            await event.reply("❌ Chưa có conversation nào!")
            return
        
        context = user_contexts.get_context_by_index(index)
        
        if not context:
            await event.reply(f"❌ Không tìm thấy conversation #{index}")
            return
        
        # Switch context
        self.context_repo.switch_context(user_id, context.id)
        
        # Show confirmation with preview
        lines = [
            f"✅ → {truncate_with_ellipsis(context.title, 35)}\n",
            f"📅 {format_date_compact(context.timestamp)} • {format_source_emoji(context.source_type)} {format_duration(context.duration_seconds)}"
        ]
        
        # Show last conversation if exists
        if context.history:
            last_user_msg = None
            last_ai_msg = None
            
            for msg in reversed(context.history):
                if msg["role"] == "assistant" and not last_ai_msg:
                    last_ai_msg = msg["content"]
                elif msg["role"] == "user" and not last_user_msg:
                    last_user_msg = msg["content"]
                
                if last_user_msg and last_ai_msg:
                    break
            
            if last_user_msg or last_ai_msg:
                lines.append("\nLast chat:")
                lines.append("─────────────────")
                if last_user_msg:
                    lines.append(f"💬 {truncate_with_ellipsis(last_user_msg, 100)}")
                if last_ai_msg:
                    lines.append(f"🤖 {truncate_with_ellipsis(last_ai_msg, 100)}")
                lines.append("─────────────────")
        
        lines.append("\n💬 Ask me anything!")
        
        await event.reply("\n".join(lines))
    
    async def handle_delete(self, event, args: str):
        """Handle /delete <number> command"""
        sender = await event.get_sender()
        user_id = sender.id
        
        if not args or not args.strip().isdigit():
            await event.reply("❌ Sử dụng: /delete <số>\n\nVí dụ: /delete 2")
            return
        
        index = int(args.strip())
        user_contexts = self.context_repo.get(user_id)
        
        if not user_contexts:
            await event.reply("❌ Chưa có conversation nào!")
            return
        
        context = user_contexts.get_context_by_index(index)
        
        if not context:
            await event.reply(f"❌ Không tìm thấy conversation #{index}")
            return
        
        title = context.title
        
        # Delete context
        if self.context_repo.delete_context(user_id, context.id):
            await event.reply(f"✅ Đã xóa: {truncate_with_ellipsis(title, 35)}")
        else:
            await event.reply("❌ Lỗi khi xóa conversation")
    
    async def handle_current(self, event):
        """Handle /current command - show current active context"""
        sender = await event.get_sender()
        user_id = sender.id
        
        user_contexts = self.context_repo.get(user_id)
        
        if not user_contexts or not user_contexts.active_context_id:
            await event.reply("📚 Chưa có conversation nào đang active.\n\nGửi audio/video để bắt đầu!")
            return
        
        context = user_contexts.get_active_context()
        
        if not context:
            await event.reply("❌ Không tìm thấy conversation!")
            return
        
        # Show detailed info
        lines = [
            f"🟢 **{context.title}**\n",
            f"📅 {format_date_compact(context.timestamp)}",
            f"{format_source_emoji(context.source_type)} Duration: {format_duration(context.duration_seconds)}",
            f"💬 Messages: {context.get_message_count()}",
        ]
        
        if context.summary:
            lines.append(f'\n📝 "{context.summary}"')
        
        lines.append(f"\n🆔 ID: {context.id}")
        
        await event.reply("\n".join(lines))
    
    async def handle_summary(self, event):
        """Handle /summary command - legacy support"""
        await self.handle_current(event)
    
    async def handle_ask_questions(self, event):
        """Handle /ask_questions command - legacy support"""
        await self.handle_help(event)
