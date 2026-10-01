from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MemeOut(BaseModel):
    id: int
    image_url: str
    caption: str
    created_at: datetime
    author: UserOut
    likes_count: int = 0
    liked_by_me: bool = False

    class Config:
        from_attributes = True


class CommentOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    author: UserOut

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)