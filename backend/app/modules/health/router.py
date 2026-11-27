from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", summary="Application process health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/health/ready", summary="Application readiness and database connectivity")
async def health_ready(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() != 1:
            raise ValueError("Unexpected query result")
        return {
            "status": "ready",
            "database": "connected",
        }
    except (SQLAlchemyError, Exception):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "database": "disconnected"},
        ) from None
