from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import secrets

from app.database import get_db
from app.models import User, Meme, Like, Comment
from app.schemas import AdminUserOut, UserOut
from app.auth import get_current_user, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Только админ")
    return current


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.id.asc()))
    users = result.scalars().all()
    out = []
    for u in users:
        cnt = await db.scalar(select(func.count()).select_from(Meme).where(Meme.user_id == u.id))
        out.append(AdminUserOut(
            id=u.id, username=u.username, role=u.role, banned=u.banned,
            created_at=u.created_at, memes_count=cnt or 0,
        ))
    return out


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Нет пользователя")
    if u.role == "admin":
        raise HTTPException(status_code=400, detail="Админа нельзя банить")
    u.banned = not u.banned
    await db.commit()
    return {"banned": u.banned}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Нет пользователя")
    if u.role == "admin":
        raise HTTPException(status_code=400, detail="Админа нельзя удалить")
    await db.delete(u)
    await db.commit()
    return {"status": "deleted"}


@router.post("/users/{user_id}/set-role")
async def set_role(user_id: int, role: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role: admin или user")
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Нет пользователя")
    u.role = role
    await db.commit()
    return {"role": role}


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Нет пользователя")
    new_password = secrets.token_urlsafe(9)[:12]
    u.password_hash = hash_password(new_password)
    await db.commit()
    return {"username": u.username, "new_password": new_password}


@router.delete("/posts/{meme_id}")
async def admin_delete_post(meme_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    r = await db.execute(select(Meme).where(Meme.id == meme_id))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Нет мема")
    await db.delete(m)
    await db.commit()
    return {"status": "deleted"}


@router.post("/posts/{meme_id}/boost")
async def boost_likes(meme_id: int, count: int = 10,
                      db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Накрутка лайков. Создаёт N фейковых лайков от админа (уникальный user_id не нужен,
    но UNIQUE(user_id, meme_id) — обходим через отдельный технический аккаунт)."""
    if count < 1 or count > 1000:
        raise HTTPException(status_code=400, detail="count 1-1000")
    r = await db.execute(select(Meme).where(Meme.id == meme_id))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Нет мема")

    # Простой способ: считать лайки как likes_count + boost_offset.
    # Но у нас нет такого поля. Поэтому накручиваем реальные лайки от фейковых юзеров.
    # Создаём по одному фейк-юзеру на лайк — это работает, но засоряет users.
    # Лучше: добавить поле boost_offset в Meme и прибавлять его в _serialize.

    # Пока используем boost_offset (нужно добавить колонку в БД):
    m.boost_offset = (m.boost_offset or 0) + count
    await db.commit()
    return {"boost_offset": m.boost_offset}