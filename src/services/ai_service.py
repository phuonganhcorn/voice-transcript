from typing import Optional, List, Dict
from src.clients.openrouter_api import OpenRouterAPI
from src.utils.schemas import ContextMetadata, GetTranscriptionTool
from datetime import datetime
import json

class AIService:
    def __init__(self):
        self.api = OpenRouterAPI()
    
    async def get_response(self, text: str, transcription: Optional[str] = None, 
                          history: Optional[List[Dict]] = None) -> Optional[str]:
        """Get AI response with function calling support"""
        messages = []
        
        # Ensure transcription is a string, not None
        transcription = transcription or ""
        
        if transcription and transcription.strip():
            messages.append({
                "role": "system",
                "content": f"""You are an AI assistant specialized in analyzing audio/video content.

IMPORTANT: The content of the audio/video has ALREADY BEEN TRANSCRIBED and is provided below.
ANALYZE DIRECTLY based on the provided transcription.

=== TRANSCRIPTION CONTENT ===
{transcription}
=== END OF TRANSCRIPTION ===

Instructions:
- Answer ALL questions with the context of the transcription above.
- If the user requests for full transcript, full transcription, xem toàn bộ transcript, cho tôi full transcript or similar requests, 
  you MUST call the get_full_transcription function. DO NOT return the transcription text yourself.
- If user ask things out of context, answer like normal chatbot, not based on the transcription.
- Answer language based on user's language if user not choose specific language.

Available Tool:
- get_full_transcription: Call this when user wants to see the full/complete transcription text."""
            })
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": text})
        
        # Check if user is requesting full transcription
        request_lower = text.lower()
        transcription_keywords = [
            'full transcript', 'full transcription', 'toàn bộ transcript',
            'cho tôi full transcript', 'xem transcript', 'view transcript',
            'show transcript', 'hiện transcript', 'transcript đầy đủ',
            'show me the transcript', 'give me transcript', 'transcript hoàn chỉnh'
        ]
        
        if any(keyword in request_lower for keyword in transcription_keywords):
            # Return special marker to indicate function call
            return "__FUNCTION_CALL__get_full_transcription"
        
        return self.api.chat_completion(messages)
    
    async def generate_metadata(self, transcription: str) -> ContextMetadata:
        """Generate title and summary using structured output with schema validation"""
        
        # Get JSON schema from Pydantic model
        schema = ContextMetadata.model_json_schema()
        
        system_prompt = """You are a metadata generator for audio/video transcriptions.
You MUST return ONLY valid JSON matching the provided schema.
No other text, no markdown, just pure JSON.

Guidelines:
- title: Concise, descriptive (max 35 chars). Format: "Topic" or "Speaker - Topic"
- summary: Keywords separated by commas (max 80 chars)
"""

        user_prompt = f"""Analyze this transcript and generate metadata:

{transcription[:1200]}...

Schema:
{json.dumps(schema, indent=2)}

Return JSON:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.api.chat_completion(messages, temperature=0.1)
            if not response:
                raise ValueError("Empty response from AI")
            
            # Clean response (remove markdown code blocks if any)
            clean = response.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
                if clean.startswith("json"):
                    clean = clean[4:].strip()
            
            # Parse and validate with Pydantic
            data = json.loads(clean)
            metadata = ContextMetadata(**data)
            
            print(f"✅ Generated metadata: {metadata.title}")
            return metadata
            
        except (json.JSONDecodeError, ValueError, Exception) as e:
            print(f"⚠️ Metadata generation failed: {e}, using fallback")
            # Fallback to simple metadata
            return self._generate_fallback_metadata(transcription)
    
    def _generate_fallback_metadata(self, transcription: str) -> ContextMetadata:
        """Generate simple fallback metadata without AI"""
        # Extract first meaningful words for title
        words = transcription.split()[:6]
        title = " ".join(words)
        if len(title) > 35:
            title = title[:32] + "..."
        
        # Use first sentence or words for summary
        first_part = transcription[:77]
        if len(transcription) > 77:
            first_part += "..."
        
        return ContextMetadata(
            title=title or f"Video {datetime.now().strftime('%d/%m %H:%M')}",
            summary=first_part
        )

