from datetime import datetime
from pydantic import BaseModel, Field


OWNER_USERNAMES = ["lol", "qwyrta"]


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=72)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    avatar: str = ""
    bio: str = ""
    status: str = ""

    class Config:
        from_attributes = True


class Token(BaseModel):
    token: str
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