from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin, Token, UserOut, OWNER_USERNAMES
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Логин 3-50 — уже проверено Pydantic, но проверим чисто для порядка
    if len(data.username) < 3 or len(data.username) > 50:
        raise HTTPException(status_code=400, detail="Логин 3-50 символов")
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Пароль минимум 4 символа")

    # Логин занят?
    ex = await db.execute(select(User).where(User.username == data.username))
    if ex.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Логин занят")

    # Владельцы получают роль admin
    role = "admin" if data.username in OWNER_USERNAMES else "user"

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user)
    return Token(token=token, user=UserOut.model_validate(user))


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

    token = create_access_token(user)
    return Token(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    return current