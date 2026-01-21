import requests
from typing import List, Dict, Optional
from src.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

class OpenRouterAPI:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Debug: Check API key
        if not self.api_key:
            print("⚠️ WARNING: OPENROUTER_API_KEY is not set!")
        else:
            print(f"✅ OpenRouter API Key loaded: {self.api_key[:20]}...")
    
    def chat_completion(self, messages: List[Dict], timeout: int = 30, temperature: float = 1.0) -> Optional[str]:
        """Get chat completion from OpenRouter"""
        try:
            print(f"🤖 Đang gửi request tới AI... (messages count: {len(messages)})")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model, 
                    "messages": messages,
                    "temperature": temperature
                },
                timeout=timeout
            )
            
            print(f"📡 AI Response status: {response.status_code}")
            if response.status_code == 200:
                result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"✅ AI response nhận được! Length: {len(result)} chars")
                return result
            else:
                print(f"❌ Lỗi AI response: Status {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Exception trong chat_completion: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    
    def transcribe_audio(self, audio_base64: str, timeout: int = 120) -> Optional[str]:
        """Transcribe audio using OpenRouter"""
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transcribe this audio accurately."},
                            {"type": "input_audio", "input_audio": {"data": audio_base64, "format": "mp3"}}
                        ]
                    }]
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"✅ Transcribe OK: {len(result)} chars")
                return result
            elif response.status_code == 413:
                print(f"❌ Transcribe failed: Status 413 (Request Entity Too Large)")
                return None
            else:
                print(f"❌ Transcribe failed: Status {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return None
        except Exception as e:
            print(f"❌ Exception in transcribe: {e}")
            import traceback
            traceback.print_exc()
            return None

