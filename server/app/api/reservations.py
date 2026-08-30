"""路由骨架：实现 response_envelope 包装。"""
from fastapi import APIRouter

router = APIRouter()


def envelope(**data):
    return {"code": 0, "message": "ok", "data": data}
