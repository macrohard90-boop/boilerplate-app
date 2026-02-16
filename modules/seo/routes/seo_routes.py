"""Public SEO endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from modules.seo.models.schemas import MetaTagsResponse
from modules.seo.services.meta_service import get_meta_tags

router = APIRouter(tags=["seo"])


@router.get("/meta/{path:path}", response_model=MetaTagsResponse)
async def get_meta(path: str, db: AsyncSession = Depends(get_db)):
    """Get meta tags, OG tags, Twitter tags, and structured data for a page path."""
    return await get_meta_tags(db, path)
