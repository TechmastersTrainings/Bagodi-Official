from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Application process health")
async def health():
    return {"status": "ok"}
