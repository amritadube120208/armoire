import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserPreferenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    style_tags: List[str] = Field(default_factory=list)
    color_affinity: Dict[str, float] = Field(default_factory=dict)
    category_affinity: Dict[str, float] = Field(default_factory=dict)
    dress_code_overrides: Dict[str, Any] = Field(default_factory=dict)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    name: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    units: str = "metric"
    created_at: datetime
    preference: Optional[UserPreferenceSchema] = None


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    units: Optional[str] = None
    style_tags: Optional[List[str]] = None
    color_affinity: Optional[Dict[str, float]] = None
    category_affinity: Optional[Dict[str, float]] = None
    dress_code_overrides: Optional[Dict[str, Any]] = None
