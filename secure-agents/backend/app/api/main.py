from fastapi import APIRouter

from app.api.routes import items, login, mcp_proxy, oauth, users, utils

api_router = APIRouter()
api_router.include_router(oauth.router, tags=["oauth"])
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(mcp_proxy.router, prefix="/v1", tags=["mcp"])
