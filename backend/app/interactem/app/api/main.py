from fastapi import APIRouter

from interactem.app.api.routes import (
    agents,
    deployments,
    login,
    operators,
    pipelines,
    users,
    utils,
)

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(
    deployments.router, prefix="/deployments", tags=["deployments"]
)
api_router.include_router(operators.router, prefix="/operators", tags=["operators"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
