from pydantic import BaseModel, Field, field_validator
from typing import Literal

class ContextMetadata(BaseModel):
    """Schema for AI-generated context metadata"""
    title: str = Field(
        ..., 
        min_length=1,
        max_length=35,
        description="Short descriptive title for the context"
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="Brief summary with keywords"
    )
    
    @field_validator('title')
    @classmethod
    def truncate_title(cls, v: str) -> str:
        """Ensure title is within limit"""
        return v.strip()[:35]
    
    @field_validator('summary')
    @classmethod
    def truncate_summary(cls, v: str) -> str:
        """Ensure summary is within limit"""
        return v.strip()[:80]
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Jensen - Nvidia startup story",
                    "summary": "Khởi nghiệp, GPU, đổi mới, vision, thất bại nhanh"
                }
            ]
        }
    }

class GetTranscriptionTool(BaseModel):
    """Function tool schema for returning full transcription"""
    name: Literal["get_full_transcription"] = "get_full_transcription"
    description: str = "Returns the full transcription text when user requests to see it"

