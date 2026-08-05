from fastapi import APIRouter

from app.api.routes import admin, auth, face, kiosk, me, users


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(face.router)
api_router.include_router(kiosk.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
