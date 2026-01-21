import os
import shutil
import time
from datetime import datetime
from uuid import uuid4
from src.services.media_service import MediaService
from src.services.ai_service import AIService
from src.repositories.user_repository import UserRepository
from src.repositories.context_repository import ContextRepository
from src.database.repositories.conversation_repository import ConversationRepository
from src.database.repositories.transcription_repository import TranscriptionRepository
from src.database.repositories.message_repository import MessageRepository
from src.core.context import MediaContext
from src.utils.media_detector import is_photo, is_voice_or_audio, is_video
from src.utils.url_parser import extract_video_url
from src.utils.message_splitter import send_long_message
from src.utils.formatters import truncate_with_ellipsis
from src.config import MAX_MESSAGE_LENGTH

class MessageHandler:
    def __init__(self, client, user_repo: UserRepository, context_repo: ContextRepository,
                 media_service: MediaService, ai_service: AIService):
        self.client = client
        self.user_repo = user_repo
        self.context_repo = context_repo
        self.media_service = media_service
        self.ai_service = ai_service
        
        # Database repositories
        self.conversation_repo = ConversationRepository()
        self.transcription_repo = TranscriptionRepository()
        self.message_repo = MessageRepository()
        
        # Ensure media/audio directory exists
        self.audio_dir = os.path.join(os.getcwd(), "media", "audio")
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # Ensure transcripts directory exists
        self.transcripts_dir = os.path.join(os.getcwd(), "media", "transcripts")
        os.makedirs(self.transcripts_dir, exist_ok=True)
    
    def _move_audio_to_storage(self, audio_path: str, user_id: int) -> str:
        """Move audio file to media/audio folder with user_id and timestamp"""
        try:
            if not os.path.exists(audio_path):
                return None
            
            # Generate new filename with user_id and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = os.path.splitext(audio_path)[1]
            new_filename = f"{user_id}_{timestamp}{file_ext}"
            new_path = os.path.join(self.audio_dir, new_filename)
            
            # Move file to media/audio
            shutil.move(audio_path, new_path)
            print(f"📦 Moved audio file to: {new_path}")
            return new_path
        except Exception as e:
            print(f"❌ Error moving audio file: {e}")
            # If move fails, try to delete the original file
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return None
    
    def _cleanup_audio_file(self, audio_path: str):
        """Delete audio file"""
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                print(f"🗑️ Deleted audio file: {audio_path}")
        except Exception as e:
            print(f"⚠️ Error deleting audio file: {e}")
    
    def _save_transcript_to_file(self, transcription: str, user_id: int, context_id: str) -> str:
        """Save transcript to file and return file path"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{user_id}_{timestamp}_{context_id}.txt"
            file_path = os.path.join(self.transcripts_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(transcription)
            
            print(f"💾 Saved transcript to file: {file_path}")
            return file_path
        except Exception as e:
            print(f"❌ Error saving transcript to file: {e}")
            return None
    
    async def _fast_download_media(self, message, file_path: str = None) -> str:
        """
        Fast download using iter_download with optimized settings
        Combines Solution 1 (large request_size) + Solution 5 (streaming)
        
        Expected improvement: +120-180% speed vs default download_media
        """
        try:
            # Generate file path if not provided
            if not file_path:
                timestamp = int(time.time())
                
                # Detect file extension
                file_ext = '.mp4'  # default
                if message.file:
                    if message.file.name:
                        file_ext = os.path.splitext(message.file.name)[1] or '.mp4'
                    elif message.file.mime_type:
                        # Common video mime types
                        mime_map = {
                            'video/mp4': '.mp4',
                            'video/quicktime': '.mov',
                            'video/x-matroska': '.mkv',
                            'video/webm': '.webm',
                            'video/avi': '.avi',
                            'audio/mpeg': '.mp3',
                            'audio/mp4': '.m4a',
                            'audio/ogg': '.oga',
                            'audio/wav': '.wav',
                        }
                        file_ext = mime_map.get(message.file.mime_type, '.mp4')
                
                file_path = f"temp_media_{message.id}_{timestamp}{file_ext}"
            
            print(f"🚀 Fast downloading to: {file_path}")
            start_time = time.time()
            bytes_downloaded = 0
            
            # Use iter_download for streaming with optimized chunk sizes
            with open(file_path, 'wb') as f:
                async for chunk in self.client.iter_download(
                    message.media,
                    chunk_size=1024 * 1024,      # 1MB write buffer (Solution 5)
                    request_size=512 * 1024,     # 512KB API request size (Solution 1 - max)
                    dc_id=None,                  # Auto-select best DC
                ):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
            
            elapsed = time.time() - start_time
            speed_mbps = (bytes_downloaded / 1024 / 1024) / elapsed if elapsed > 0 else 0
            
            print(f"✅ Downloaded {bytes_downloaded / 1024 / 1024:.2f} MB in {elapsed:.2f}s ({speed_mbps:.2f} MB/s)")
            
            return file_path
            
        except Exception as e:
            print(f"❌ Fast download failed: {e}")
            # Cleanup partial file
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return None
    
    async def _process_media(self, event, user_id: int, transcribed_text: str, 
                            user_prompt: str = None, source_type: str = "audio",
                            duration_seconds: int = 0, process_with_ai: bool = True):
        """
        Process transcribed media and create new context
        
        Args:
            user_prompt: Text message sent in THE SAME message as the link/media
            process_with_ai: If True, process user_prompt with AI immediately
                            If False, only transcribe (don't send to AI)
        
        Logic:
            - Link only → Just transcribe (process_with_ai=False)
            - Link + text in SAME message → Transcribe + AI process (process_with_ai=True)
            - This prevents treating separate messages as combined input
        """
        
        # Generate metadata using AI
        status_msg = await event.reply("✨ Generating metadata...")
        metadata = await self.ai_service.generate_metadata(transcribed_text)
        await status_msg.delete()
        
        # Telegram handler tạo conversation_id
        conversation_id = uuid4()
        
        # Check if transcript is very long (> 4096 * 3)
        transcript_length = len(transcribed_text)
        very_long_threshold = 4096 * 3  # 12,288 characters
        
        transcript_file_path = None
        if transcript_length > very_long_threshold:
            # Save to file
            transcript_file_path = self._save_transcript_to_file(
                transcribed_text, 
                user_id, 
                str(conversation_id)
            )
            print(f"📊 Transcript is very long ({transcript_length} chars > {very_long_threshold}), saved to file")
        
        # Create transcription in database
        transcription_id = self.transcription_repo.create_transcription(transcribed_text)
        
        # Prepare metadata
        metadata_json = {
            "summary": metadata.summary,
            "duration_seconds": duration_seconds,
        }
        if transcript_file_path:
            metadata_json["transcript_file_path"] = transcript_file_path
        
        # Create conversation in database
        self.conversation_repo.create_conversation(
            user_id=str(user_id),
            transcription_id=transcription_id,
            title=metadata.title,
            platform='telegram',
            metadata=metadata_json,
            source_type=source_type,
            conversation_id=conversation_id
        )
        
        # Create MediaContext for compatibility
        context = MediaContext(
            user_id=user_id,
            context_id=str(conversation_id),
            transcription=transcribed_text,
            title=metadata.title,
            summary=metadata.summary,
            source_type=source_type,
            duration_seconds=duration_seconds,
            transcript_file_path=transcript_file_path
        )
        
        # Show confirmation
        confirmation_msg = (
            f"✅ Transcribed!\n\n"
            f"📝 {truncate_with_ellipsis(metadata.title, 35)}\n"
            f'"{truncate_with_ellipsis(metadata.summary, 80)}"\n\n'
        )
        
        # Add note if transcript was saved to file
        if transcript_file_path:
            confirmation_msg += (
                f"📄 Transcript is very long ({transcript_length:,} chars) and has been saved to a file.\n"
                f"💬 Use commands like 'full transcript', 'xem full transcript', or 'show me the transcript' to receive the file.\n\n"
            )
        
        await event.reply(confirmation_msg)
        
        # If user has both audio and text AND process_with_ai is True, process the question immediately
        if user_prompt and process_with_ai:
            ai_response = await self.ai_service.get_response(
                user_prompt, 
                transcription=transcribed_text, 
                history=[]
            )
            if ai_response:
                # Save messages to database
                self.message_repo.add_message(conversation_id, 'user', user_prompt)
                self.message_repo.add_message(conversation_id, 'assistant', ai_response)
                # Update conversation timestamp
                self.conversation_repo.update_conversation(conversation_id)
                await send_long_message(event, ai_response)
    
    async def _handle_text_message(self, event, user_id: int, user_text: str):
        """Handle text message with active context"""
        # IMPORTANT: Check if text contains a URL
        # If it does, it should be treated as a NEW video/audio to transcribe
        # NOT as a question about the current active context
        video_url = extract_video_url(user_text)
        
        if video_url:
            # This is a URL, not a text question
            # Don't process with current context, let main handler process it
            print(f"⚠️ Text contains URL, skipping context-based processing")
            return
        
        active_context = self.context_repo.get_active_context(user_id)
        
        if active_context:
            conversation_id = active_context.id
            ai_response = await self.ai_service.get_response(
                user_text, 
                active_context.transcription, 
                active_context.history
            )
            
            # Check if AI wants to return full transcription
            if ai_response and ai_response == "__FUNCTION_CALL__get_full_transcription":
                print(f"🔧 Function call detected: get_full_transcription")
                
                # Check if transcript was saved to file (very long transcript)
                if active_context.transcript_file_path and os.path.exists(active_context.transcript_file_path):
                    print(f"📄 Sending transcript file: {active_context.transcript_file_path}")
                    await event.reply("📄 Sending full transcript as file...")
                    await self.client.send_file(
                        event.chat_id,
                        active_context.transcript_file_path,
                        caption=f"📄 Full Transcription\n\n{active_context.title}"
                    )
                    # Save messages to database
                    from uuid import UUID
                    self.message_repo.add_message(UUID(conversation_id), 'user', user_text)
                    self.message_repo.add_message(UUID(conversation_id), 'assistant', "[Sent full transcription file]")
                    self.conversation_repo.update_conversation(UUID(conversation_id))
                else:
                    # Regular transcript, send as chunked messages
                    await send_long_message(
                        event, 
                        f"📄 **Full Transcription**\n\n{active_context.transcription}",
                        prefix="📄 **Full Transcription** (continued)\n\n"
                    )
                    # Save messages to database
                    from uuid import UUID
                    self.message_repo.add_message(UUID(conversation_id), 'user', user_text)
                    self.message_repo.add_message(UUID(conversation_id), 'assistant', "[Returned full transcription]")
                    self.conversation_repo.update_conversation(UUID(conversation_id))
            elif ai_response:
                # Save messages to database
                from uuid import UUID
                self.message_repo.add_message(UUID(conversation_id), 'user', user_text)
                self.message_repo.add_message(UUID(conversation_id), 'assistant', ai_response)
                self.conversation_repo.update_conversation(UUID(conversation_id))
                await send_long_message(event, ai_response)
        else:
            # No active context, general chat
            ai_response = await self.ai_service.get_response(user_text)
            if ai_response:
                await send_long_message(event, ai_response)
    
    async def handle(self, event):
        """Handle incoming message"""
        try:
            # Skip own messages
            me = await self.client.get_me()
            if event.message.from_id and event.message.from_id.user_id == me.id:
                return
            
            # Skip commands (they're handled separately)
            if event.message.text and event.message.text.strip().startswith('/'):
                return
            
            # Check if user started
            sender = await event.get_sender()
            user_id = sender.id
            
            print(f"\n{'='*60}")
            print(f"📨 New message from user {user_id} name {sender.username}")
            
            if not self.user_repo.exists(user_id):
                await event.reply("⚠️ Vui lòng nhấn /start để bắt đầu!")
                return
            
            user_text = event.message.text.strip() if event.message.text else ""
            video_url = extract_video_url(user_text) if user_text else None
            
            # Check if there's text besides the URL in THE SAME message
            # This ensures URL and text were sent together, not as separate messages
            text_without_url = user_text.replace(video_url, "").strip() if video_url else user_text
            has_additional_text = bool(text_without_url)
            
            print(f"📝 User text: {user_text[:100] if user_text else 'None'}...")
            print(f"🔗 Video URL: {video_url if video_url else 'None'}")
            print(f"💬 Additional text in same message: {has_additional_text}")
            if has_additional_text and video_url:
                print(f"   → Text content: '{text_without_url[:50]}...'")
            print(f"📎 Has media: {bool(event.message.media)}")
            
            # Handle media
            if event.message.media:
                if is_photo(event.message.media):
                    if video_url:
                        # Process video link from text
                        status_msg = await event.reply("⏳ Downloading and transcribing video...")
                        audio_path = await self.media_service.download_video_audio(video_url)
                        if audio_path:
                            await status_msg.edit("⏳ Transcribing audio...")
                            transcribed = await self.media_service.transcribe_audio(audio_path)
                            
                            # Get duration before removing file
                            duration = 0
                            try:
                                import mutagen
                                audio_info = mutagen.File(audio_path)
                                if audio_info:
                                    duration = int(audio_info.info.length)
                            except:
                                pass
                            
                            # Always cleanup video audio files (usually large)
                            self._cleanup_audio_file(audio_path)
                            
                            if transcribed:
                                await status_msg.delete()
                                # Only process with AI if there's additional text in THE SAME message
                                # This prevents treating separate messages as a combined request
                                await self._process_media(
                                    event, user_id, transcribed, 
                                    text_without_url or None,
                                    source_type="video",
                                    duration_seconds=duration,
                                    process_with_ai=has_additional_text
                                )
                            else:
                                await status_msg.edit("❌ Failed to transcribe audio")
                        else:
                            await status_msg.edit("❌ Failed to download video")
                    elif user_text:
                        # Process text with active context
                        await self._handle_text_message(event, user_id, user_text)
                    return
                
                # Priority: video link in text
                if video_url:
                    status_msg = await event.reply("⏳ Downloading and transcribing video...")
                    audio_path = await self.media_service.download_video_audio(video_url)
                    if audio_path:
                        await status_msg.edit("⏳ Transcribing audio...")
                        transcribed = await self.media_service.transcribe_audio(audio_path)
                        
                        # Get duration
                        duration = 0
                        try:
                            import mutagen
                            audio_info = mutagen.File(audio_path)
                            if audio_info:
                                duration = int(audio_info.info.length)
                        except:
                            pass
                        
                        # Always cleanup video audio files (usually large)
                        self._cleanup_audio_file(audio_path)
                        
                        if transcribed:
                            await status_msg.delete()
                            # Only process with AI if there's additional text in THE SAME message
                            await self._process_media(
                                event, user_id, transcribed, 
                                text_without_url or None,
                                source_type="video",
                                duration_seconds=duration,
                                process_with_ai=has_additional_text
                            )
                        else:
                            await status_msg.edit("❌ Failed to transcribe audio")
                    else:
                        await status_msg.edit("❌ This video is not available")
                    return
                
                # Process voice message or audio file
                if is_voice_or_audio(event.message.media):
                    print(f"🎤 Phát hiện voice/audio message")
                    status_msg = await event.reply("⏳ Downloading audio...")
                    path = await self._fast_download_media(event.message)
                    print(f"📁 Downloaded to: {path}")
                    
                    if path:
                        await status_msg.edit("⏳ Transcribing audio...")
                        transcribed = await self.media_service.transcribe_audio(path)
                        
                        # Get duration
                        duration = 0
                        source_type = "audio"
                        try:
                            import mutagen
                            audio_info = mutagen.File(path)
                            if audio_info:
                                duration = int(audio_info.info.length)
                            
                            # Detect if voice message or audio file
                            if hasattr(event.message.media, 'voice'):
                                source_type = "voice_message"
                        except:
                            pass
                        
                        if transcribed:
                            print(f"✅ Transcribed successfully, processing...")
                            
                            # Move audio file to storage
                            stored_path = self._move_audio_to_storage(path, user_id)
                            
                            await status_msg.delete()
                            # Only process with AI if there's user text in THE SAME message (caption)
                            # Voice/audio without caption → just transcribe
                            # Voice/audio with caption → transcribe + process caption with AI
                            await self._process_media(
                                event, user_id, transcribed, 
                                user_text or None,
                                source_type=source_type,
                                duration_seconds=duration,
                                process_with_ai=bool(user_text)
                            )
                        else:
                            print(f"❌ Transcription failed")
                            # Delete the file if transcription failed
                            self._cleanup_audio_file(path)
                            await status_msg.edit("❌ Failed to transcribe audio")
                    else:
                        print(f"❌ Download failed")
                        await status_msg.edit("❌ Failed to download audio")
                    return
                
                # Process video file
                if is_video(event.message.media):
                    print(f"🎬 Phát hiện video file")
                    status_msg = await event.reply("⏳ Downloading video...")
                    video_path = await self._fast_download_media(event.message)
                    print(f"📁 Downloaded video to: {video_path}")
                    
                    if video_path:
                        await status_msg.edit("⏳ Extracting audio from video...")
                        audio_path = await self.media_service.extract_audio_from_video(video_path)
                        
                        if audio_path:
                            await status_msg.edit("⏳ Transcribing audio...")
                            transcribed = await self.media_service.transcribe_audio(audio_path)
                            
                            # Get duration
                            duration = 0
                            try:
                                import mutagen
                                audio_info = mutagen.File(audio_path)
                                if audio_info:
                                    duration = int(audio_info.info.length)
                            except:
                                pass
                            
                            # Clean up video and audio files
                            self._cleanup_audio_file(video_path)
                            self._cleanup_audio_file(audio_path)
                            
                            if transcribed:
                                print(f"✅ Transcribed video successfully, processing...")
                                await status_msg.delete()
                                # Only process with AI if there's user text (caption)
                                # Video without caption → just transcribe
                                # Video with caption → transcribe + process caption with AI
                                await self._process_media(
                                    event, user_id, transcribed, 
                                    user_text or None,
                                    source_type="video_file",
                                    duration_seconds=duration,
                                    process_with_ai=bool(user_text)
                                )
                            else:
                                print(f"❌ Video transcription failed")
                                await status_msg.edit("❌ Failed to transcribe video audio")
                        else:
                            print(f"❌ Audio extraction failed")
                            # Clean up video file
                            self._cleanup_audio_file(video_path)
                            await status_msg.edit("❌ Failed to extract audio from video")
                    else:
                        print(f"❌ Video download failed")
                        await status_msg.edit("❌ Failed to download video")
                    return
                
                # If not photo, not audio/voice, and not video → skip
                print(f"⚠️ Unsupported media type")
                await event.reply("⚠️ Unsupported media type")
                return
            
            # Handle text only
            if user_text:
                if video_url:
                    status_msg = await event.reply("⏳ Downloading and transcribing video...")
                    audio_path = await self.media_service.download_video_audio(video_url)
                    if audio_path:
                        await status_msg.edit("⏳ Transcribing audio...")
                        transcribed = await self.media_service.transcribe_audio(audio_path)
                        
                        # Get duration
                        duration = 0
                        try:
                            import mutagen
                            audio_info = mutagen.File(audio_path)
                            if audio_info:
                                duration = int(audio_info.info.length)
                        except:
                            pass
                        
                        # Always cleanup video audio files (usually large)
                        self._cleanup_audio_file(audio_path)
                        
                        if transcribed:
                            await status_msg.delete()
                            # Only process with AI if there's additional text in THE SAME message
                            await self._process_media(
                                event, user_id, transcribed, 
                                text_without_url or None,
                                source_type="url",
                                duration_seconds=duration,
                                process_with_ai=has_additional_text
                            )
                        else:
                            await status_msg.edit("❌ Failed to transcribe audio")
                    else:
                        await status_msg.edit("❌ Failed to download video")
                else:
                    # Text message with active context
                    await self._handle_text_message(event, user_id, user_text)
            
            print(f"{'='*60}\n")
        
        except Exception as e:
            print(f"❌ CRITICAL ERROR in handler: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            try:
                await event.reply(f"❌ Internal error: {type(e).__name__}")
            except:
                pass
