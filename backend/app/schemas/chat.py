from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str = Field(..., description="Message author role: 'user' or 'model'")
    content: str = Field(..., description="Message text content")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User query to the AI engineer")
    telemetry: Optional[Dict[str, Any]] = Field(default=None, description="Active IoT sensor telemetry snapshot")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Recent conversation turns")
    timestamp: Optional[str] = Field(default=None, description="Client timestamp")

class ChatResponse(BaseModel):
    reply: str
    model: str
    source: str = Field(..., description="'gemini-api' or 'xco-local-engine' or 'fallback'")
    timestamp: str
    telemetry_context: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
