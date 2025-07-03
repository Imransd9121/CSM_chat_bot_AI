from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, Literal

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class DocumentCreate(BaseModel):
    user_id: Optional[str] = None
    name: str
    type: Literal['pdf', 'doc', 'url']
    url: Optional[HttpUrl] = None
    content: Optional[str] = None
    uploaded_at: Optional[str] = None
    processed: Optional[bool] = False

class ChatMessage(BaseModel):
    user_id: str
    doc_id: str
    question: str
    answer: str
    timestamp: Optional[str] = None 