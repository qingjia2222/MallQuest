"""商场 AI 私域服务助手 - 统一后端入口.

双端（微信小程序 / Web）共用一套后端与私有数据源。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import scan, auth, chat, plan, parking, points, coupons, reservations

app = FastAPI(title="商场 AI 私域服务助手", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一路由前缀，所有接口返回 response_envelope
for router in (
    scan.router,
    auth.router,
    chat.router,
    plan.router,
    parking.router,
    points.router,
    coupons.router,
    reservations.router,
):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"code": 0, "message": "ok", "data": {"status": "up"}}
