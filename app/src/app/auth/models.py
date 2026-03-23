"""Pydantic models for authentication."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    id: str
    email: str
    hashed_password: str
    created_at: str


class UserResponse(BaseModel):
    id: str
    email: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: str
    token_type: str  # "access" | "refresh"


class RefreshRequest(BaseModel):
    refresh_token: str
