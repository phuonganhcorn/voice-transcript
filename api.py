from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import os
import shutil
from datetime import datetime

# Import các services từ project
from src.services.media_service import MediaService
from src.services.ai_service import AIService
from src.repositories.user_repository import UserRepository
from src.repositories.context_repository import ContextRepository
from src.database.repositories.conversation_repository import ConversationRepository
from src.database.repositories.transcription_repository import TranscriptionRepository
from src.database.repositories.message_repository import MessageRepository
from src.database.connection import db
from src.core.context import MediaContext
from src.utils.s3_upload import init_s3_client, upload_file_to_s3

# Initialize database
print("🔌 Initializing database connection...")
db.initialize()

# Initialize FastAPI app
app = FastAPI(
    title="Video/Audio Transcription & AI Chat API",
    description="API for transcribing audio/video and chatting with AI about the content",
    version="1.0.0"
)

# Initialize services
media_service = MediaService()
ai_service = AIService()
user_repo = UserRepository()
context_repo = ContextRepository()

# Initialize database repositories
conversation_repo = ConversationRepository()
transcription_repo = TranscriptionRepository()
message_repo = MessageRepository()

# Initialize S3 client
init_s3_client()

# Pydantic models for API
class TranscribeResponse(BaseModel):
    success: bool
    transcription_id: Optional[str] = None  # For mobile: transcription_id
    conversation_id: Optional[str] = None  # For mobile: conversation_id
    context_id: Optional[str] = None  # Legacy field (conversation_id)
    title: Optional[str] = None
    summary: Optional[str] = None
    transcription: Optional[str] = None
    duration_seconds: int = 0
    message: Optional[str] = None
    s3_link: Optional[str] = None  # S3 link to transcript file

class ChatRequest(BaseModel):
    user_id: str
    messages: List[str]  # Array of messages: [user_msg1, assistant_msg1, user_msg2, assistant_msg2, ..., current_user_msg]

class ChatResponse(BaseModel):
    success: bool
    response: Optional[str] = None

class VideoUrlRequest(BaseModel):
    user_id: int
    video_url: str

class VideoUrlMobileRequest(BaseModel):
    user_id: str
    video_url: str

class AudioUrlMobileRequest(BaseModel):
    user_id: str
    audio_url: str  # Can be storage URL or direct audio URL

# Health check
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Video/Audio Transcription & AI Chat API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "media_service": "ok",
            "ai_service": "ok",
            "repositories": "ok"
        }
    }

# User management
@app.post("/users/{user_id}/initialize")
async def initialize_user(user_id: int):
    """Initialize a new user"""
    try:
        if user_repo.exists(user_id):
            return {
                "success": True,
                "message": f"User {user_id} already exists",
                "user_id": user_id
            }
        
        user_repo.add_user(user_id)
        return {
            "success": True,
            "message": f"User {user_id} initialized successfully",
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Transcription endpoints
@app.post("/transcribe/audio", response_model=TranscribeResponse)
async def transcribe_audio_file(
    user_id: int = Form(...),
    file: UploadFile = File(...)
):
    """
    Transcribe an audio file
    
    Supported formats: .m4a, .mp3, .wav, .ogg, .oga, .opus
    """
    try:
        # Check user exists
        if not user_repo.exists(user_id):
            user_repo.add_user(user_id)
        
        # Save uploaded file
        audio_dir = os.path.join(os.getcwd(), "media", "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(file.filename)[1]
        temp_filename = f"temp_{user_id}_{timestamp}{file_ext}"
        temp_path = os.path.join(audio_dir, temp_filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Transcribe
        transcribed = await media_service.transcribe_audio(temp_path)
        
        if not transcribed:
            # Cleanup on failure
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return TranscribeResponse(
                success=False,
                message="Failed to transcribe audio"
            )
        
        # Generate metadata
        metadata = await ai_service.generate_metadata(transcribed)
        
        # Get duration
        duration = 0
        try:
            import mutagen
            audio_info = mutagen.File(temp_path)
            if audio_info:
                duration = int(audio_info.info.length)
        except:
            pass
        
        # Save transcription to file and upload to S3
        transcript_dir = os.path.join(os.getcwd(), "media", "transcripts")
        os.makedirs(transcript_dir, exist_ok=True)
        
        transcript_filename = f"{user_id}_{timestamp}_transcript.txt"
        transcript_local_path = os.path.join(transcript_dir, transcript_filename)
        
        # Write transcript to file with UTF-8 encoding (ensure Unicode support)
        with open(transcript_local_path, "w", encoding="utf-8", errors="replace", newline="") as f:
            f.write(transcribed)
        
        # Upload to S3
        s3_transcript_key = f"transcripts/{transcript_filename}"
        s3_transcript_url = upload_file_to_s3(transcript_local_path, s3_transcript_key)
        
        # Create context
        context = MediaContext(
            user_id=user_id,
            transcription=transcribed,
            title=metadata.title,
            summary=metadata.summary,
            source_type="audio",
            duration_seconds=duration
        )
        
        context_repo.add_context(user_id, context)
        
        # Rename file with proper naming
        final_filename = f"{user_id}_{timestamp}{file_ext}"
        final_path = os.path.join(audio_dir, final_filename)
        
        if os.path.exists(temp_path):
            shutil.move(temp_path, final_path)
        
        return TranscribeResponse(
            success=True,
            context_id=context.id,
            title=metadata.title,
            summary=metadata.summary,
            transcription=transcribed,
            duration_seconds=duration,
            s3_link=s3_transcript_url,
            message="Audio transcribed successfully"
        )
        
    except Exception as e:
        # Cleanup on error
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe/audio-url-mobile", response_model=TranscribeResponse)
async def transcribe_audio_url_mobile(request: AudioUrlMobileRequest):
    """
    Transcribe audio from URL for Mobile App
    - Supports storage URLs (Supabase, S3, etc.) and direct audio URLs
    - Conversation_id được tạo SAU KHI transcribe thành công
    - Always uploads transcript to S3
    - Returns transcription_id và conversation_id
    """
    try:
        from uuid import uuid4
        
        # Check user exists (user_id is string for mobile, can be UUID)
        if not user_repo.exists(request.user_id):
            user_repo.add_user(request.user_id)
        
        # Check if URL is from storage or platform
        if media_service._is_storage_url(request.audio_url):
            # Download directly from storage
            print(f"📥 Detected storage URL, downloading directly...")
            audio_path = await media_service.download_from_storage_url(request.audio_url)
        else:
            # Try to download as direct audio file
            print(f"📥 Downloading audio from URL...")
            audio_path = await media_service.download_from_storage_url(request.audio_url)
        
        if not audio_path:
            return TranscribeResponse(
                success=False,
                message="Failed to download audio from URL"
            )
        
        # Transcribe
        transcribed = await media_service.transcribe_audio(audio_path)
        
        # Get duration before cleanup
        duration = 0
        try:
            import mutagen
            audio_info = mutagen.File(audio_path)
            if audio_info:
                duration = int(audio_info.info.length)
        except:
            pass
        
        # Cleanup downloaded file
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if not transcribed:
            return TranscribeResponse(
                success=False,
                message="Failed to transcribe audio"
            )
        
        # Generate metadata
        metadata = await ai_service.generate_metadata(transcribed)
        
        # Save transcription to file and upload to S3
        transcript_dir = os.path.join(os.getcwd(), "media", "transcripts")
        os.makedirs(transcript_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_filename = f"{request.user_id}_{timestamp}_transcript.txt"
        transcript_local_path = os.path.join(transcript_dir, transcript_filename)
        
        # Write transcript to file with UTF-8 encoding (ensure Unicode support)
        with open(transcript_local_path, "w", encoding="utf-8", errors="replace", newline="") as f:
            f.write(transcribed)
        
        # Upload to S3
        s3_transcript_key = f"transcripts/{transcript_filename}"
        s3_transcript_url = upload_file_to_s3(transcript_local_path, s3_transcript_key)
        
        # Create transcription in database
        transcription_id = transcription_repo.create_transcription(transcribed)
        
        # Prepare metadata
        metadata_json = {
            "summary": metadata.summary,
            "duration_seconds": duration,
            "transcript_file_path": s3_transcript_url if s3_transcript_url else transcript_local_path
        }
        
        # Create conversation_id AFTER successful transcription
        conversation_id = uuid4()
        
        # Create conversation in database
        conversation_repo.create_conversation(
            user_id=request.user_id,
            transcription_id=transcription_id,
            title=metadata.title,
            platform='mobile',
            metadata=metadata_json,
            source_type="audio",
            conversation_id=conversation_id
        )
        
        # Return transcription_id và conversation_id
        return TranscribeResponse(
            success=True,
            transcription_id=str(transcription_id),
            conversation_id=str(conversation_id),
            s3_link=s3_transcript_url,
            message="Transcription completed successfully"
        )
        
    except Exception as e:
        if 'transcript_local_path' in locals() and os.path.exists(transcript_local_path):
            os.remove(transcript_local_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe/video-url", response_model=TranscribeResponse)
async def transcribe_video_url(request: VideoUrlRequest):
    """
    Transcribe audio from a video URL (YouTube, etc.)
    """
    try:
        # Check user exists
        if not user_repo.exists(request.user_id):
            user_repo.add_user(request.user_id)
        
        # Download video audio
        audio_path = await media_service.download_video_audio(request.video_url)
        
        if not audio_path:
            return TranscribeResponse(
                success=False,
                message="Failed to download video"
            )
        
        # Transcribe
        transcribed = await media_service.transcribe_audio(audio_path)
        
        # Get duration before cleanup
        duration = 0
        try:
            import mutagen
            audio_info = mutagen.File(audio_path)
            if audio_info:
                duration = int(audio_info.info.length)
        except:
            pass
        
        # Always cleanup video audio (large files)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if not transcribed:
            return TranscribeResponse(
                success=False,
                message="Failed to transcribe video audio"
            )
        
        # Generate metadata
        metadata = await ai_service.generate_metadata(transcribed)
        
        # Save transcription to file and upload to S3
        transcript_dir = os.path.join(os.getcwd(), "media", "transcripts")
        os.makedirs(transcript_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_filename = f"{request.user_id}_{timestamp}_transcript.txt"
        transcript_local_path = os.path.join(transcript_dir, transcript_filename)
        
        # Write transcript to file with UTF-8 encoding (ensure Unicode support)
        with open(transcript_local_path, "w", encoding="utf-8", errors="replace", newline="") as f:
            f.write(transcribed)
        
        # Upload to S3
        s3_transcript_key = f"transcripts/{transcript_filename}"
        s3_transcript_url = upload_file_to_s3(transcript_local_path, s3_transcript_key)
        
        # Create context
        context = MediaContext(
            user_id=request.user_id,
            transcription=transcribed,
            title=metadata.title,
            summary=metadata.summary,
            source_type="video",
            duration_seconds=duration
        )
        
        context_repo.add_context(request.user_id, context)
        
        return TranscribeResponse(
            success=True,
            context_id=context.id,
            title=metadata.title,
            summary=metadata.summary,
            transcription=transcribed,
            duration_seconds=duration,
            s3_link=s3_transcript_url,
            message="Video transcribed successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe/video-url-mobile", response_model=TranscribeResponse)
async def transcribe_video_url_mobile(request: VideoUrlMobileRequest):
    """
    Transcribe audio from a video URL for Mobile App
    - Supports storage URLs (Supabase, S3, etc.) and platform URLs (YouTube, etc.)
    - Conversation_id được tạo SAU KHI transcribe thành công
    - Always uploads transcript to S3
    - Returns transcription_id và conversation_id
    """
    try:
        from uuid import uuid4
        
        # Check user exists (user_id is string for mobile, can be UUID)
        if not user_repo.exists(request.user_id):
            user_repo.add_user(request.user_id)
        
        # Check if URL is from storage or platform
        if media_service._is_storage_url(request.video_url):
            # Download directly from storage
            print(f"📥 Detected storage URL, downloading directly...")
            audio_path = await media_service.download_from_storage_url(request.video_url)
        else:
            # Use yt-dlp/pytubefix for platform URLs (YouTube, etc.)
            print(f"📥 Detected platform URL, using yt-dlp...")
            audio_path = await media_service.download_video_audio(request.video_url)
        
        if not audio_path:
            return TranscribeResponse(
                success=False,
                message="Failed to download video"
            )
        
        # Transcribe
        transcribed = await media_service.transcribe_audio(audio_path)
        
        # Get duration before cleanup
        duration = 0
        try:
            import mutagen
            audio_info = mutagen.File(audio_path)
            if audio_info:
                duration = int(audio_info.info.length)
        except:
            pass
        
        # Always cleanup video audio (large files)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if not transcribed:
            return TranscribeResponse(
                success=False,
                message="Failed to transcribe video audio"
            )
        
        # Generate metadata
        metadata = await ai_service.generate_metadata(transcribed)
        
        # Save transcription to file and upload to S3
        transcript_dir = os.path.join(os.getcwd(), "media", "transcripts")
        os.makedirs(transcript_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_filename = f"{request.user_id}_{timestamp}_transcript.txt"
        transcript_local_path = os.path.join(transcript_dir, transcript_filename)
        
        # Write transcript to file with UTF-8 encoding (ensure Unicode support)
        with open(transcript_local_path, "w", encoding="utf-8", errors="replace", newline="") as f:
            f.write(transcribed)
        
        # Upload to S3
        s3_transcript_key = f"transcripts/{transcript_filename}"
        s3_transcript_url = upload_file_to_s3(transcript_local_path, s3_transcript_key)
        
        # Create transcription in database
        transcription_id = transcription_repo.create_transcription(transcribed)
        
        # Prepare metadata
        metadata_json = {
            "summary": metadata.summary,
            "duration_seconds": duration,
            "transcript_file_path": s3_transcript_url if s3_transcript_url else transcript_local_path
        }
        
        # Create conversation_id AFTER successful transcription
        conversation_id = uuid4()
        
        # Create conversation in database
        conversation_repo.create_conversation(
            user_id=request.user_id,
            transcription_id=transcription_id,
            title=metadata.title,
            platform='mobile',
            metadata=metadata_json,
            source_type="video",
            conversation_id=conversation_id
        )
        
        # Return transcription_id và conversation_id (theo FLOW_DESIGN.md)
        return TranscribeResponse(
            success=True,
            transcription_id=str(transcription_id),
            conversation_id=str(conversation_id),
            s3_link=s3_transcript_url,
            message="Video transcribed successfully"
        )
        
    except Exception as e:
        if 'transcript_local_path' in locals() and os.path.exists(transcript_local_path):
            os.remove(transcript_local_path)
        raise HTTPException(status_code=500, detail=str(e))

# Chat endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with AI about a context or general conversation
    - Mobile FE sends full conversation history as messages array
    - messages format: [user_msg1, assistant_msg1, user_msg2, assistant_msg2, ..., current_user_msg]
    - Messages alternate: user, assistant, user, assistant, ...
    """
    try:
        from uuid import UUID
        
        # Check user exists (user_id is string for mobile, can be UUID)
        if not user_repo.exists(request.user_id):
            return ChatResponse(
                success=False,
                response=f"User {request.user_id} not found. Please initialize first."
            )
        
        # Validate messages array
        if not request.messages or len(request.messages) == 0:
            return ChatResponse(
                success=False,
                response="Messages array cannot be empty"
            )
        
        # Get active conversation
        conversation = conversation_repo.get_active_conversation(request.user_id)
        
        # For mobile: messages[0] is the transcription
        # For mobile: messages format is [transcription, user_msg1, assistant_msg1, user_msg2, assistant_msg2, ..., current_user_msg]
        # For telegram: messages format is [user_msg1, assistant_msg1, user_msg2, assistant_msg2, ..., current_user_msg]
        
        transcription_text = ""
        history_start_index = 0
        
        # Check if first message is transcription (mobile format)
        if conversation and len(request.messages) > 0:
            # For mobile, first message is transcription
            transcription_text = str(request.messages[0]) if request.messages[0] is not None else ""
            history_start_index = 1  # Start history from index 1
        elif conversation:
            # For telegram, get transcription from database
            try:
                transcription = transcription_repo.get_transcription_by_id(conversation.transcription_id)
                transcription_text = (transcription.content if transcription and transcription.content else "") or ""
            except Exception as e:
                print(f"⚠️ Error getting transcription: {e}")
                transcription_text = ""
        
        # Convert messages array to history format
        # Skip transcription (index 0) for mobile, start from index 1
        # Messages alternate: user (index 1), assistant (index 2), user (index 3), ... for mobile
        history = []
        messages_for_history = request.messages[history_start_index:-1]  # All except transcription and last message
        for i, msg in enumerate(messages_for_history):
            # Ensure msg is a string, not None
            msg_content = str(msg) if msg is not None else ""
            role = 'user' if i % 2 == 0 else 'assistant'
            history.append({
                "role": role,
                "content": msg_content
            })
        
        # Current user message is the last one in the array
        current_user_message = str(request.messages[-1]) if request.messages[-1] is not None else ""
        
        # Get AI response
        if conversation:
            ai_response = await ai_service.get_response(
                current_user_message,
                transcription_text,
                history
            )
            
            if ai_response:
                try:
                    # Save messages to database
                    message_repo.add_message(conversation.id, 'user', current_user_message)
                    message_repo.add_message(conversation.id, 'assistant', ai_response)
                    # Update conversation timestamp
                    conversation_repo.update_conversation(conversation.id)
                except Exception as e:
                    print(f"⚠️ Error saving messages: {e}")
                    # Continue even if saving fails
        else:
            # No context, general chat
            ai_response = await ai_service.get_response(
                current_user_message,
                None,
                history
            )
        
        if not ai_response:
            return ChatResponse(
                success=False,
                response="Failed to get AI response"
            )
        
        return ChatResponse(
            success=True,
            response=ai_response
        )
        
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"❌ Error in /chat endpoint: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

