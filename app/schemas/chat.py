from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class MessageBase(BaseModel):
    role: str
    content: str
    tool_calls: Optional[dict] = None

class MessageResponse(MessageBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class ConversationResponse(BaseModel):
    id: int
    title: str
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str
