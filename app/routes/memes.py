import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Meme, Like, Comment, User
from app.schemas import MemeOut, CommentOut, CommentCreate, UserOut
from app.auth import get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/memes", tags=["memes"])


async def _serialize_meme(meme: Meme, db: AsyncSession, current_user: User | None) -> MemeOut:
    likes_count = await db.scalar(select(func.count()).select_from(Like).where(Like.meme_id == meme.id))
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
        raise HTTPException(status_code=400, detail="Можно загружать только изображения")

    try:
        result = cloudinary.uploader.upload(
            file.file,
            folder="memes",
            resource_type="image",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {e}")

    meme = Meme(user_id=current.id, image_url=result["secure_url"], caption=caption)
    db.add(meme)
    await db.commit()

    result = await db.execute(
        select(Meme).options(selectinload(Meme.author)).where(Meme.id == meme.id)
    )
    meme = result.scalar_one()
    return await _serialize_meme(meme, db, current)


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
    memes = result.scalars().all()
    return [await _serialize_meme(m, db, current) for m in memes]


@router.get("/my", response_model=list[MemeOut])
async def my_memes(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Meme)
        .options(selectinload(Meme.author))
        .where(Meme.user_id == current.id)
        .order_by(Meme.created_at.desc())
    )
    memes = result.scalars().all()
    return [await _serialize_meme(m, db, current) for m in memes]


@router.delete("/{meme_id}")
async def delete_meme(
    meme_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    result = await db.execute(select(Meme).where(Meme.id == meme_id))
    meme = result.scalar_one_or_none()
    if not meme:
        raise HTTPException(status_code=404, detail="Мем не найден")
    if meme.user_id != current.id:
        raise HTTPException(status_code=403, detail="Это не ваш мем")
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
        raise HTTPException(status_code=404, detail="Мем не найден")

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


@router.get("/{meme_id}/comments", response_model=list[CommentOut])
async def get_comments(meme_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.meme_id == meme_id)
        .order_by(Comment.created_at.asc())
    )
    return [CommentOut.model_validate(c) for c in result.scalars().all()]


@router.post("/{meme_id}/comments", response_model=CommentOut)
async def add_comment(
    meme_id: int,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    exists = await db.scalar(select(func.count()).select_from(Meme).where(Meme.id == meme_id))
    if not exists:
        raise HTTPException(status_code=404, detail="Мем не найден")

    comment = Comment(user_id=current.id, meme_id=meme_id, text=data.text)
    db.add(comment)
    await db.commit()

    result = await db.execute(
        select(Comment).options(selectinload(Comment.author)).where(Comment.id == comment.id)
    )
    return CommentOut.model_validate(result.scalar_one())