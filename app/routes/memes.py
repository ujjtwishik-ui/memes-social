import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Meme, Like, User
from app.schemas import MemeOut, UserOut
from app.auth import get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/memes", tags=["memes"])


async def _serialize_meme(meme: Meme, db: AsyncSession, current_user: User | None) -> MemeOut:
    likes_count = await db.scalar(
        select(func.count()).select_from(Like).where(Like.meme_id == meme.id)
    )
    liked = False
    if current_user:
        liked = bool(await db.scalar(
            select(func.count()).select_from(Like).where(
                Like.meme_id == meme.id, Like.user_id == current_user.id
            )
        ))
    return MemeOut(
        id=meme.id,
        image_url=meme.image_url,
        caption=meme.caption or "",
        created_at=meme.created_at,
        author=UserOut.model_validate(meme.author),
        likes_count=likes_count or 0,
        liked_by_me=liked,
    )


@router.post("/", response_model=MemeOut)
async def create_meme(
    file: UploadFile = File(...),
    caption: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Только изображения")

    try:
        result = cloudinary.uploader.upload(file.file, folder="memes", resource_type="image")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Cloudinary: {e}")

    meme = Meme(user_id=current.id, image_url=result["secure_url"], caption=caption[:500])
    db.add(meme)
    await db.commit()

    res = await db.execute(select(Meme).options(selectinload(Meme.author)).where(Meme.id == meme.id))
    return await _serialize_meme(res.scalar_one(), db, current)


@router.get("/", response_model=list[MemeOut])
async def feed(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current: User | None = Depends(get_current_user_optional),
):
    limit = min(limit, 50)
    result = await db.execute(
        select(Meme)
        .options(selectinload(Meme.author))
        .order_by(Meme.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return [await _serialize_meme(m, db, current) for m in result.scalars().all()]


@router.get("/my", response_model=list[MemeOut])
async def my_memes(db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    result = await db.execute(
        select(Meme)
        .options(selectinload(Meme.author))
        .where(Meme.user_id == current.id)
        .order_by(Meme.created_at.desc())
    )
    return [await _serialize_meme(m, db, current) for m in result.scalars().all()]


@router.delete("/{meme_id}")
async def delete_meme(
    meme_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    result = await db.execute(select(Meme).where(Meme.id == meme_id))
    meme = result.scalar_one_or_none()
    if not meme:
        raise HTTPException(status_code=404, detail="Не найдено")
    if meme.user_id != current.id:
        raise HTTPException(status_code=403, detail="Не ваш мем")
    await db.delete(meme)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{meme_id}/like")
async def toggle_like(
    meme_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    exists = await db.scalar(select(func.count()).select_from(Meme).where(Meme.id == meme_id))
    if not exists:
        raise HTTPException(status_code=404, detail="Не найдено")

    existing = await db.scalar(
        select(Like).where(Like.user_id == current.id, Like.meme_id == meme_id)
    )
    if existing:
        await db.delete(existing)
        await db.commit()
        return {"liked": False}

    db.add(Like(user_id=current.id, meme_id=meme_id))
    await db.commit()
    return {"liked": True}