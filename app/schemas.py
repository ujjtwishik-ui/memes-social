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
    theme: str = "dark"

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    avatar: str | None = None
    bio: str | None = None
    status: str | None = None
    theme: str | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=4, max_length=72)


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
    comments_count: int = 0

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


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    banned: bool
    created_at: datetime
    memes_count: int = 0

    class Config:
        from_attributes = True