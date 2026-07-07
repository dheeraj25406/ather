from pydantic import BaseModel, Field
from typing import Optional, List, Any


class SessionCreateResponse(BaseModel):
    session_id: str


class Message(BaseModel):
    role: str
    content: str


class ToolCall(BaseModel):
    name: str
    args: dict


class SessionQueryRequest(BaseModel):
    user_prompt: str


class SessionResponse(BaseModel):
    session_id: str
    result: str
    tool_calls: Optional[List[ToolCall]] = []
    memory_used: Optional[List[Any]] = []
