from pydantic import BaseModel, EmailStr, Field
from common import common_types

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)

class AppUser(UserBase):
    password: str = Field(min_length=8)

class AppUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)

class AppUserResponse(UserBase):
    id: int
    role: common_types.UserRole

class Token(BaseModel):
    access_token: str
    token_type: str