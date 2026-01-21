import os
import base64
import subprocess
import asyncio
import yt_dlp
import requests
from yt_dlp import DownloadError
from typing import Optional, Tuple
from src.clients.openrouter_api import OpenRouterAPI
from src.config import MAX_FILE_SIZE_MB

# Try importing pytubefix as fallback
try:
    from pytubefix import YouTube as PyTubeYouTube
    PYTUBEFIX_AVAILABLE = True
except ImportError:
    PYTUBEFIX_AVAILABLE = False
    print("⚠️ pytubefix not available - will only use yt-dlp")

class MediaService:
    def __init__(self):
        self.api = OpenRouterAPI()
    
    async def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Extract audio from video file using ffmpeg"""
        try:
            if not self._check_ffmpeg():
                print(f"❌ ffmpeg không được tìm thấy! Không thể extract audio từ video.")
                print(f"💡 Cài đặt ffmpeg: brew install ffmpeg (macOS) hoặc sudo apt-get install ffmpeg (Linux)")
                return None
            
            print(f"🎬 Extracting audio from video: {video_path}")
            
            # Generate output audio path
            base_name = os.path.splitext(video_path)[0]
            audio_path = f"{base_name}_audio.m4a"
            
            # Extract audio using ffmpeg
            result = subprocess.run(
                ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'copy', '-y', audio_path],
                capture_output=True,
                timeout=300
            )
            
            # If copy codec fails, try re-encoding
            if result.returncode != 0:
                print(f"⚠️ Audio copy failed, trying re-encode...")
                result = subprocess.run(
                    ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'aac', '-b:a', '128k', '-y', audio_path],
                    capture_output=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                print(f"❌ Failed to extract audio from video")
                error_msg = result.stderr.decode('utf-8', errors='ignore')[:500]
                print(f"ffmpeg error: {error_msg}")
                return None
            
            if os.path.exists(audio_path):
                file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
                print(f"✅ Extracted audio: {audio_path} ({file_size_mb:.2f} MB)")
                return audio_path
            else:
                print(f"❌ Audio file not created")
                return None
                
        except Exception as e:
            print(f"❌ Exception in extract_audio_from_video: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def download_video_audio(self, url: str) -> Optional[str]:
        """
        Download audio from video URL using optimized settings
        Uses aria2c for multi-connection downloads (2-5x faster)
        Falls back to concurrent fragment downloads if aria2c not available
        """
        try:
            print(f"🎬 Đang tải video từ: {url}")
            
            # Validate URL
            if not url or not isinstance(url, str):
                print(f"❌ Invalid URL: {url}")
                return None
            
            # Check if aria2c is available
            has_aria2c = self._check_aria2c()
            
            # Check for proxy (cookies are not effective when IP is blocked)
            from src.config import Config
            proxy_url = Config.YOUTUBE_PROXY  # Proxy URL for residential IP
            
            if proxy_url:
                print(f"🌐 Using proxy: {proxy_url}")
            
            # Common options for both aria2c and fallback
            common_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': 'audio_temp.m4a',
                
                # Add user-agent and headers to avoid HTTP 400 errors and bot detection
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                },
                
                # Bypass YouTube bot detection - prioritize mobile clients
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios'],  # Try mobile clients first (less likely to be blocked)
                        'player_skip': ['webpage', 'configs'],  # Skip some checks
                        'player_js_version': 'actual',  # Use actual player JS version (helps with some blocking)
                    }
                },
                
                # Additional options to bypass restrictions
                'no_check_certificate': True,  # Skip certificate validation
                'prefer_insecure': False,  # Prefer HTTPS
                'no_warnings': False,  # Show warnings for debugging
                'quiet': False,  # Enable verbose for debugging
            }
            
            # Add proxy if available (cookies don't help when IP is blocked)
            if proxy_url:
                common_opts['proxy'] = proxy_url
            
            if has_aria2c:
                print(f"🚀 Using aria2c for fast multi-connection download")
                ydl_opts = {
                    **common_opts,
                    # Use aria2c - professional download manager
                    'external_downloader': 'aria2c',
                     'external_downloader_args': [
                        '--max-connection-per-server=16',  # 16 connections per server
                        '--split=16',                      # Split file into 16 parts
                        '--min-split-size=1M',             # Split if file > 1MB
                        '--max-concurrent-downloads=16',
                        '--continue=true',                 # Resume support
                        '--max-download-limit=0',          # No speed limit
                    ],
                }
            else:
                print(f"⚡ Using concurrent fragment downloads (aria2c not found)")
                ydl_opts = {
                    **common_opts,
                    # Fallback: concurrent fragment downloads
                    'concurrent_fragment_downloads': 8,
                    'http_chunk_size': 10485760,  # 10MB chunks
                }
            
            # Add error handling callback
            def download_hook(d):
                if d['status'] == 'error':
                    print(f"❌ Download error: {d.get('error', 'Unknown error')}")
                elif d['status'] == 'downloading':
                    if 'total_bytes' in d:
                        percent = d.get('downloaded_bytes', 0) / d['total_bytes'] * 100
                        print(f"📥 Downloading: {percent:.1f}%")
            
            ydl_opts['progress_hooks'] = [download_hook]
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Extract info first to validate URL
                    try:
                        print(f"🔍 Extracting video info from URL...")
                        info = ydl.extract_info(url, download=False)
                        if not info:
                            print(f"❌ Could not extract video info from URL")
                            return None
                        print(f"📹 Video title: {info.get('title', 'Unknown')}")
                        print(f"⏱️  Duration: {info.get('duration', 0)} seconds")
                        print(f"🌐 Extractor: {info.get('extractor', 'Unknown')}")
                        
                        # Download with original instance
                        print(f"⬇️ Starting download...")
                        ydl.download([url])
                        
                    except DownloadError as extract_error:
                        error_msg = str(extract_error)
                        print(f"❌ Failed to extract video info: {error_msg}")
                        
                        # Check for YouTube blocking (Failed to extract any player response or Failed to parse JSON)
                        if 'Failed to extract any player response' in error_msg or 'Failed to parse JSON' in error_msg:
                            print(f"🤖 YouTube blocking detected - trying multiple fallback methods...")
                            
                            # Try different player clients in order (prioritize mobile/TV clients)
                            retry_clients = [
                                ('android', 'Android client'),
                                ('ios', 'iOS client'),
                                ('tv', 'TV client'),
                                ('mweb', 'Mobile web client'),
                                ('web', 'Web client'),
                            ]
                            
                            retry_success = False
                            for client_name, client_desc in retry_clients:
                                try:
                                    print(f"🔄 Trying {client_desc}...")
                                    import time
                                    time.sleep(2)  # Longer delay between retries to avoid rate limiting
                                    
                                    ydl_opts_retry = ydl_opts.copy()
                                    # Override extractor_args for this retry
                                    ydl_opts_retry['extractor_args'] = {
                                        'youtube': {
                                            'player_client': [client_name],
                                            'player_js_version': 'actual',  # Use actual player JS version
                                        }
                                    }
                                    # Keep proxy if available
                                    if 'proxy' in ydl_opts:
                                        ydl_opts_retry['proxy'] = ydl_opts['proxy']
                                    
                                    with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl_retry:
                                        info = ydl_retry.extract_info(url, download=False)
                                        if info:
                                            print(f"✅ Success with {client_desc}!")
                                            print(f"📹 Video title: {info.get('title', 'Unknown')}")
                                            print(f"⏱️  Duration: {info.get('duration', 0)} seconds")
                                            # Download immediately with retry instance
                                            print(f"⬇️ Starting download with {client_desc}...")
                                            ydl_retry.download([url])
                                            retry_success = True
                                            break  # Success, exit retry loop
                                        else:
                                            raise DownloadError(f"{client_desc} failed")
                                except Exception as retry_error:
                                    retry_error_msg = str(retry_error)
                                    print(f"⚠️ {client_desc} failed: {retry_error_msg[:150]}")
                                    if client_name == retry_clients[-1][0]:  # Last retry
                                        print(f"❌ All retry methods failed")
                                        print(f"💡 YouTube is heavily blocking requests. Solutions:")
                                        print(f"   1. Update yt-dlp: pip install -U yt-dlp (or use nightly build)")
                                        print(f"   2. Use cookies:")
                                        print(f"      - Set YOUTUBE_COOKIES_FILE=/path/to/cookies.txt (export from browser)")
                                        print(f"      - OR set YOUTUBE_COOKIES_FROM_BROWSER=chrome|firefox|edge (auto-extract)")
                                        print(f"      Export cookies using 'Get cookies.txt LOCALLY' extension")
                                        print(f"      See: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp")
                                        print(f"   3. Use proxy/VPN with residential IP (set HTTP_PROXY env var)")
                                        print(f"   4. Try again later (YouTube may rate limit)")
                                        print(f"   5. Consider using YouTube Data API for metadata (if video is public)")
                                        return None
                                    continue  # Try next client
                            
                            if not retry_success:
                                return None
                            # If retry succeeded, continue to file check below
                            
                        # Check for bot detection
                        elif 'Sign in to confirm you\'re not a bot' in error_msg or 'bot' in error_msg.lower():
                            print(f"🤖 YouTube detected bot - trying alternative method...")
                            # Try with different player client
                            try:
                                ydl_opts_retry = ydl_opts.copy()
                                ydl_opts_retry['extractor_args'] = {
                                    'youtube': {
                                        'player_client': ['ios', 'android'],  # Try iOS client
                                        'player_js_version': 'actual',  # Use actual player JS version
                                    }
                                }
                                # Keep proxy if available
                                if 'proxy' in ydl_opts:
                                    ydl_opts_retry['proxy'] = ydl_opts['proxy']
                                with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl_retry:
                                    print(f"🔄 Retrying with iOS client...")
                                    info = ydl_retry.extract_info(url, download=False)
                                    if info:
                                        print(f"✅ Success with iOS client!")
                                        print(f"📹 Video title: {info.get('title', 'Unknown')}")
                                        print(f"⏱️  Duration: {info.get('duration', 0)} seconds")
                                        # Download immediately with retry instance
                                        print(f"⬇️ Starting download with iOS client...")
                                        ydl_retry.download([url])
                                    else:
                                        raise DownloadError("Retry failed")
                            except Exception as retry_error:
                                print(f"❌ Retry also failed: {retry_error}")
                                print(f"🔄 Trying fallback method: pytubefix...")
                                
                                # Try pytubefix as fallback
                                if PYTUBEFIX_AVAILABLE:
                                    try:
                                        return await self._download_with_pytubefix(url)
                                    except Exception as pytube_error:
                                        print(f"❌ pytubefix also failed: {pytube_error}")
                                
                                print(f"💡 YouTube requires authentication. Solutions:")
                                print(f"   1. Use proxy/VPN with residential IP (set YOUTUBE_PROXY env var)")
                                print(f"   2. Try again later (YouTube may rate limit)")
                                return None
                        elif 'HTTP Error 400' in error_msg or 'Bad Request' in error_msg:
                            print(f"💡 URL might be invalid or not supported by yt-dlp")
                            print(f"💡 Supported sites: YouTube, Vimeo, Twitter, TikTok, etc.")
                            return None
                        elif 'HTTP Error 403' in error_msg or 'Forbidden' in error_msg:
                            print(f"💡 Access forbidden - video might be private or region-locked")
                            return None
                        elif 'HTTP Error 404' in error_msg or 'Not Found' in error_msg:
                            print(f"💡 Video not found - URL might be incorrect or video was deleted")
                            return None
                        else:
                            return None
                    except Exception as extract_error:
                        error_type = type(extract_error).__name__
                        error_msg = str(extract_error)
                        print(f"❌ Failed to extract video info: {error_type}: {error_msg}")
                        # Try to get more details
                        if hasattr(extract_error, 'msg'):
                            print(f"   Error message: {extract_error.msg}")
                        import traceback
                        traceback.print_exc()
                        return None
            except DownloadError as e:
                error_msg = str(e)
                print(f"❌ yt_dlp DownloadError: {error_msg}")
                # Provide helpful error messages
                if 'HTTP Error 400' in error_msg or 'Bad Request' in error_msg:
                    print(f"💡 This URL might not be supported or is invalid")
                    print(f"💡 Please check if the URL is correct and try again")
                elif 'HTTP Error 403' in error_msg:
                    print(f"💡 Access forbidden - video might be private or region-locked")
                elif 'HTTP Error 404' in error_msg:
                    print(f"💡 Video not found - URL might be incorrect or video was deleted")
                import traceback
                traceback.print_exc()
                return None
            except Exception as e:
                # Catch other yt_dlp exceptions
                error_type = type(e).__name__
                error_msg = str(e)
                print(f"❌ yt_dlp {error_type}: {error_msg}")
                import traceback
                traceback.print_exc()
                return None
            
            # Check if file was created
            if os.path.exists("audio_temp.m4a"):
                file_size = os.path.getsize("audio_temp.m4a")
                file_size_mb = file_size / (1024 * 1024)
                print(f"✅ Đã tải video thành công! File size: {file_size_mb:.2f} MB")
                return "audio_temp.m4a"
            else:
                print(f"❌ File audio_temp.m4a không tồn tại sau khi tải")
                # Check for other possible output files
                possible_files = ['audio_temp.m4a', 'audio_temp.mp3', 'audio_temp.webm', 'audio_temp.opus']
                for filename in possible_files:
                    if os.path.exists(filename):
                        print(f"⚠️ Found alternative file: {filename}")
                        return filename
                return None
        except Exception as e:
            print(f"❌ Exception trong download_video_audio: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _is_storage_url(self, url: str) -> bool:
        """Check if URL is from Supabase storage or similar storage service"""
        if not url:
            return False
        # Check for Supabase storage pattern
        if 'supabase.co/storage/v1/object/public' in url:
            return True
        # Check for other common storage patterns
        if any(pattern in url for pattern in ['storage.googleapis.com', 's3.amazonaws.com', 'blob.core.windows.net']):
            return True
        return False
    
    async def download_from_storage_url(self, url: str, output_filename: str = "audio_temp.m4a") -> Optional[str]:
        """
        Download file directly from storage URL (Supabase, S3, etc.)
        Returns path to downloaded file
        """
        try:
            print(f"📥 Downloading from storage URL: {url[:100]}...")
            
            # Download file
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Get file extension from URL or Content-Type
            file_ext = os.path.splitext(url.split('?')[0])[1]  # Remove query params
            if not file_ext:
                # Try to get from Content-Type
                content_type = response.headers.get('Content-Type', '')
                if 'video' in content_type or 'audio' in content_type:
                    if 'mp4' in content_type:
                        file_ext = '.mp4'
                    elif 'm4a' in content_type:
                        file_ext = '.m4a'
                    elif 'mp3' in content_type:
                        file_ext = '.mp3'
                    else:
                        file_ext = '.m4a'  # Default
                else:
                    file_ext = '.m4a'  # Default
            
            # Determine output filename
            if not output_filename.endswith(file_ext):
                output_filename = f"audio_temp{file_ext}"
            
            # Download to file
            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if os.path.exists(output_filename):
                file_size = os.path.getsize(output_filename)
                file_size_mb = file_size / (1024 * 1024)
                print(f"✅ Downloaded from storage! File size: {file_size_mb:.2f} MB")
                return output_filename
            else:
                print(f"❌ Downloaded file not found")
                return None
                
        except Exception as e:
            print(f"❌ Failed to download from storage URL: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _check_aria2c(self) -> bool:
        """Check if aria2c is available"""
        try:
            result = subprocess.run(['aria2c', '--version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    async def _download_with_pytubefix(self, url: str) -> Optional[str]:
        """
        Fallback method using pytubefix when yt-dlp fails
        pytubefix sometimes works when yt-dlp is blocked
        """
        if not PYTUBEFIX_AVAILABLE:
            raise ImportError("pytubefix is not installed")
        
        try:
            print(f"🔄 Using pytubefix as fallback...")
            
            # Create YouTube object
            yt = PyTubeYouTube(url)
            
            # Get audio stream (best quality)
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            
            if not audio_stream:
                raise Exception("No audio stream available")
            
            print(f"📹 Video title: {yt.title}")
            print(f"⏱️  Duration: {yt.length} seconds")
            print(f"⬇️ Downloading audio with pytubefix...")
            
            # Download to temp file
            output_path = audio_stream.download(output_path=".", filename="audio_temp")
            
            # Convert to m4a if needed (pytubefix may download in different format)
            if output_path and os.path.exists(output_path):
                # Check if file needs conversion
                file_ext = os.path.splitext(output_path)[1].lower()
                if file_ext != '.m4a':
                    # Rename to audio_temp.m4a (ffmpeg will handle conversion if needed)
                    m4a_path = "audio_temp.m4a"
                    if os.path.exists(m4a_path):
                        os.remove(m4a_path)
                    os.rename(output_path, m4a_path)
                    output_path = m4a_path
                else:
                    # Rename to standard name
                    m4a_path = "audio_temp.m4a"
                    if os.path.exists(m4a_path):
                        os.remove(m4a_path)
                    os.rename(output_path, m4a_path)
                    output_path = m4a_path
                
                file_size = os.path.getsize(output_path)
                file_size_mb = file_size / (1024 * 1024)
                print(f"✅ Downloaded with pytubefix! File size: {file_size_mb:.2f} MB")
                return output_path
            else:
                raise Exception("Downloaded file not found")
                
        except Exception as e:
            print(f"❌ pytubefix download failed: {type(e).__name__}: {e}")
            raise
    
    async def _transcribe_with_ffmpeg_chunking(self, audio_path: str, max_chunk_size_mb: float = 10, recursion_depth: int = 0) -> Optional[str]:
        """Split audio file using ffmpeg"""
        try:
            # Max recursion depth to prevent infinite loops
            MAX_RECURSION = 3
            if recursion_depth >= MAX_RECURSION:
                print(f"❌ Max recursion depth reached ({MAX_RECURSION}). Cannot split further.")
                return None
            
            if not self._check_ffmpeg():
                print(f"❌ ffmpeg không được tìm thấy! Không thể chia audio.")
                print(f"💡 Cài đặt ffmpeg: brew install ffmpeg (macOS) hoặc sudo apt-get install ffmpeg (Linux)")
                return None
            
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"✂️ [Depth {recursion_depth}] Splitting {file_size_mb:.2f} MB file using ffmpeg...")
            
            # Get audio duration using ffprobe
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                     '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    print(f"❌ Không thể lấy duration của audio file")
                    print(f"ffprobe error: {result.stderr}")
                    return None
                
                duration = float(result.stdout.strip())
            except Exception as e:
                print(f"❌ Exception khi lấy duration: {type(e).__name__}: {e}")
                return None
            
            # Calculate chunk duration with safety margin (target 85% of max to ensure under limit)
            safety_margin = 0.85
            target_chunk_size_mb = max_chunk_size_mb * safety_margin
            chunk_duration = (target_chunk_size_mb / file_size_mb) * duration
            
            # Ensure minimum chunk duration
            MIN_CHUNK_DURATION = 30  # seconds
            if chunk_duration < MIN_CHUNK_DURATION:
                print(f"❌ Calculated chunk duration too small ({chunk_duration:.1f}s < {MIN_CHUNK_DURATION}s)")
                print(f"💡 Audio bitrate too high. Try: ffmpeg -i input -b:a 64k output.mp3")
                return None
            
            print(f"📊 File size: {file_size_mb:.2f} MB")
            print(f"⏱️  Duration: {duration:.2f} seconds")
            print(f"🎯 Target chunk size: {target_chunk_size_mb:.2f} MB (safety margin: {safety_margin})")
            print(f"✂️  Splitting into chunks of ~{chunk_duration:.2f} seconds each...")
            
            # Use a unique temporary directory to avoid filename collisions
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="audio_chunks_")
            
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            ext = os.path.splitext(audio_path)[1] or '.m4a'
            
            # Use ffmpeg segment muxer for FAST parallel splitting (single pass)
            # This is 6-8x faster than sequential chunk creation
            print(f"🚀 Using ffmpeg segment muxer for fast splitting...")
            import time
            split_start = time.time()
            
            chunk_pattern = os.path.join(temp_dir, f"chunk_%03d{ext}")
            
            # Single ffmpeg command to split entire file
            result = subprocess.run(
                [
                    'ffmpeg', '-i', audio_path,
                    '-f', 'segment',                      # Use segment muxer
                    '-segment_time', str(chunk_duration), # Split every N seconds
                    '-c', 'copy',                         # Copy codec (fast, no re-encode)
                    '-reset_timestamps', '1',             # Reset timestamp for each chunk
                    '-y',                                 # Overwrite
                    chunk_pattern
                ],
                capture_output=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"⚠️ Segment with copy failed, trying with re-encode...")
                result = subprocess.run(
                    [
                        'ffmpeg', '-i', audio_path,
                        '-f', 'segment',
                        '-segment_time', str(chunk_duration),
                        '-acodec', 'libmp3lame',          # Re-encode if copy fails
                        '-ar', '16000',
                        '-ac', '1',
                        '-b:a', '64k',
                        '-reset_timestamps', '1',
                        '-y',
                        chunk_pattern
                    ],
                    capture_output=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                print(f"❌ Failed to split audio file")
                print(f"ffmpeg error: {result.stderr.decode('utf-8', errors='ignore')[:500]}")
                return None
            
            split_elapsed = time.time() - split_start
            
            # Collect created chunk files
            chunk_paths = sorted([
                os.path.join(temp_dir, f) 
                for f in os.listdir(temp_dir) 
                if f.startswith('chunk_') and f.endswith(ext)
            ])
            
            if not chunk_paths:
                print(f"❌ No chunks were created")
                return None
            
            # Log chunk sizes
            for i, chunk_path in enumerate(chunk_paths, 1):
                chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                print(f"📦 Chunk {i}: {chunk_size_mb:.2f} MB")
            
            print(f"✅ Created {len(chunk_paths)} chunks in {split_elapsed:.1f}s (segment muxer)")
            
            # Transcribe chunks in parallel with rate limiting
            print(f"🚀 Starting parallel transcription (max 5 concurrent)...")
            
            # Semaphore to limit concurrent API calls
            MAX_CONCURRENT_TRANSCRIPTIONS = 5
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)
            
            async def transcribe_chunk_with_limit(chunk_index, chunk_path):
                """Transcribe a single chunk with concurrency control"""
                async with semaphore:
                    try:
                        print(f"🎵 Transcribing chunk {chunk_index}/{len(chunk_paths)}...")
                        
                        chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                        
                        # Skip empty chunks
                        if chunk_size_mb < 0.01:
                            print(f"⚠️ Chunk {chunk_index} is too small ({chunk_size_mb:.2f} MB), skipping...")
                            return None
                        
                        # Use stricter threshold (9.5 MB instead of 10 MB) to catch edge cases
                        if chunk_size_mb > 9.5:
                            print(f"⚠️ Chunk {chunk_index} is still too large ({chunk_size_mb:.2f} MB > 9.5 MB), recursively chunking...")
                            text = await self._transcribe_with_ffmpeg_chunking(chunk_path, max_chunk_size_mb, recursion_depth + 1)
                        else:
                            text = await self._transcribe_single_audio(chunk_path)
                        
                        if text:
                            print(f"✅ Chunk {chunk_index} transcribed successfully")
                            return text
                        else:
                            print(f"⚠️ Chunk {chunk_index} transcription failed")
                            return None
                            
                    except Exception as e:
                        print(f"❌ Error transcribing chunk {chunk_index}: {e}")
                        return None
                    finally:
                        # Clean up chunk file
                        if os.path.exists(chunk_path):
                            try:
                                os.remove(chunk_path)
                                print(f"🗑️ Deleted chunk {chunk_index}")
                            except Exception as cleanup_error:
                                print(f"⚠️ Could not delete chunk {chunk_index}: {cleanup_error}")
            
            # Create tasks for all chunks
            tasks = [
                transcribe_chunk_with_limit(i, chunk_path) 
                for i, chunk_path in enumerate(chunk_paths, 1)
            ]
            
            # Execute all tasks in parallel (with semaphore limiting concurrency)
            import time
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.time() - start_time
            
            # Filter out None and exceptions
            transcriptions = []
            for i, result in enumerate(results, 1):
                if isinstance(result, Exception):
                    print(f"⚠️ Chunk {i} raised exception: {result}")
                elif result:
                    transcriptions.append(result)
            
            print(f"⚡ Parallel transcription completed in {elapsed:.1f}s ({len(transcriptions)}/{len(chunk_paths)} successful)")
            
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(temp_dir)
                print(f"🗑️ Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                print(f"⚠️ Could not clean up temp directory: {e}")
            
            # Merge all transcriptions
            if transcriptions:
                merged_text = "\n\n".join(transcriptions)
                print(f"✅ Merged transcription from {len(transcriptions)}/{len(chunk_paths)} chunks: {len(merged_text)} chars")
                return merged_text
            else:
                print(f"❌ All chunks failed to transcribe")
                return None
                
        except Exception as e:
            print(f"❌ Exception in ffmpeg chunking: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            # Clean up temp directory if it exists
            try:
                if 'temp_dir' in locals() and os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir)
                    print(f"🗑️ Cleaned up temp directory after error")
            except Exception as cleanup_error:
                print(f"⚠️ Could not clean up temp directory: {cleanup_error}")
            return None
    
    async def _transcribe_single_audio(self, audio_path: str) -> Optional[str]:
        """Transcribe a single audio file"""
        try:
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            
            with open(audio_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            result = self.api.transcribe_audio(audio_base64)
            
            if result:
                return result
            elif result is None:
                print(f"💡 File size {file_size_mb:.2f} MB is too large, will try chunking...")
                return None
            else:
                return None
        except Exception as e:
            print(f"❌ Exception in transcribe: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """Main transcribe function with automatic chunking"""
        try:
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"📊 Audio file size: {file_size_mb:.2f} MB")
            
            # If file is small enough, transcribe directly
            if file_size_mb <= MAX_FILE_SIZE_MB:
                print(f"✅ File size OK (≤{MAX_FILE_SIZE_MB}MB), transcribing directly...")
                return await self._transcribe_single_audio(audio_path)
            
            # File is too large, must split into chunks
            print(f"✂️ File too large ({file_size_mb:.2f} MB > {MAX_FILE_SIZE_MB} MB), splitting into chunks...")
            return await self._transcribe_with_ffmpeg_chunking(audio_path, MAX_FILE_SIZE_MB)
                
        except Exception as e:
            print(f"❌ Exception in transcribe_audio: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

