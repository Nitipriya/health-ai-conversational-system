from fastapi import APIRouter

from app.api.v1 import auth, chats, messages

# All v1 routes live under /api/v1
api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(chats.router)
api_router.include_router(messages.router)
