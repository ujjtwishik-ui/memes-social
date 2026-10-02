from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Meme
from app.schemas import (
    UserRegister, UserLogin, Token, UserOut, UserProfileUpdate,
    PasswordChange, OWNER_USERNAMES, MemeOut,
)
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


def _safe_profile_fields(data: str) -> bool:
    """Простейшая защита от XSS в bio/status/avatar."""
    if not data:
        return True
    bad = ["<script", "<iframe", "javascript:", "onerror=", "onload="]
    low = data.lower()
    return not any(b in low for b in bad)


@router.post("/register", response_model=Token)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    if len(data.username) < 3 or len(data.username) > 50:
        raise HTTPException(status_code=400, detail="Логин 3-50 символов")
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Пароль минимум 4 символа")

    ex = await db.execute(select(User).where(User.username == data.username))
    if ex.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Логин занят")

    role = "admin" if data.username in OWNER_USERNAMES else "user"
    user = User(username=data.username, password_hash=hash_password(data.password), role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return Token(token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Нет такого пользователя")
    if user.banned:
        raise HTTPException(status_code=403, detail="Вы забанены")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный пароль")

    return Token(token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    return current


@router.put("/me", response_model=UserOut)
async def update_me(
    data: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if data.avatar is not None:
        if not _safe_profile_fields(data.avatar):
            raise HTTPException(status_code=400, detail="Запрещённый контент в avatar")
        current.avatar = data.avatar[:500]
    if data.bio is not None:
        if not _safe_profile_fields(data.bio):
            raise HTTPException(status_code=400, detail="Запрещённый контент в bio")
        current.bio = data.bio[:500]
    if data.status is not None:
        if not _safe_profile_fields(data.status):
            raise HTTPException(status_code=400, detail="Запрещённый контент в status")
        current.status = data.status[:255]
    if data.theme is not None and data.theme in ("dark", "light"):
        current.theme = data.theme

    await db.commit()
    await db.refresh(current)
    return current


@router.put("/me/password")
async def change_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not verify_password(data.old_password, current.password_hash):
        raise HTTPException(status_code=400, detail="Неверный старый пароль")
    if len(data.new_password) < 4:
        raise HTTPException(status_code=400, detail="Пароль минимум 4 символа")
    current.password_hash = hash_password(data.new_password)
    await db.commit()
    return {"ok": True}


@router.get("/users/{username}", response_model=UserOut)
async def get_user(username: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(User).where(User.username == username))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Нет пользователя")
    return UserOut.model_validate(user)


@router.get("/users/{username}/memes", response_model=list[MemeOut])
async def user_memes(username: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(User).where(User.username == username))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Нет пользователя")

    from app.models import Like
    result = await db.execute(
        select(Meme).where(Meme.user_id == user.id).order_by(Meme.created_at.desc()).limit(100)
    )
    memes = result.scalars().all()
    out = []
    for m in memes:
        likes_count = await db.scalar(select(func.count()).select_from(Like).where(Like.meme_id == m.id))
        comments_count = await db.scalar(
            select(func.count()).select_from(__import__("app.models", fromlist=["Comment"]).Comment).where(
                __import__("app.models", fromlist=["Comment"]).Comment.meme_id == m.id
            )
        )
        out.append(MemeOut(
            id=m.id, image_url=m.image_url, caption=m.caption or "",
            created_at=m.created_at, author=UserOut.model_validate(user),
            likes_count=likes_count or 0, liked_by_me=False, comments_count=comments_count or 0,
        ))
    return out