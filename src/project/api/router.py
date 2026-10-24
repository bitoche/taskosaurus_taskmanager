from fastapi import APIRouter

from project.api.routes import comments, health, priorities, remote_db, tags, tasks

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(comments.router, prefix="/tasks", tags=["comments"])
api_router.include_router(tags.router, prefix="/task_tags", tags=["tags"])
api_router.include_router(priorities.router, prefix="/priority", tags=["priorities"])
api_router.include_router(remote_db.router, prefix="/remote_db", tags=["remote_db"])
