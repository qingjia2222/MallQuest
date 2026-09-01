import logging, time, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.core.envelope import envelope
from app.core.metrics import metrics
from app.db import assert_database_ready, database_health, ensure_database

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("mall-assistant")
@asynccontextmanager
async def lifespan(_app):
    ensure_database()
    readiness=assert_database_ready()
    log.info("startup_ready database_instance=%s stores=%s bindings=%s",readiness["instance_id"],readiness["stores"],readiness["map_bindings"])
    yield

app=FastAPI(title="星河里 AI 私域服务助手",version="1.0.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def request_middleware(request:Request,call_next):
    request_id=request.headers.get("X-Request-ID",str(uuid.uuid4())); request.state.request_id=request_id; start=time.perf_counter()
    try: response=await call_next(request)
    except Exception:
        metrics.record_request(500,(time.perf_counter()-start)*1000); log.exception("request_failed request_id=%s path=%s",request_id,request.url.path); raise
    latency=(time.perf_counter()-start)*1000; metrics.record_request(response.status_code,latency); response.headers["X-Request-ID"]=request_id
    log.info("request_id=%s method=%s path=%s status=%s latency_ms=%.2f",request_id,request.method,request.url.path,response.status_code,latency); return response

@app.exception_handler(HTTPException)
async def http_error(request:Request,exc:HTTPException):
    return JSONResponse(status_code=exc.status_code,content={"code":exc.status_code,"message":str(exc.detail),"request_id":getattr(request.state,"request_id",str(uuid.uuid4())),"timestamp":int(time.time()),"data":{}})

@app.get("/health")
@app.get("/api/health")
def health():
    database=database_health()
    data={"status":"up" if database["ok"] else "degraded","ready":database["ok"],"mall":"星河里","llm_mode":settings.llm_mode,"tts_mode":settings.tts_mode,"database":database}
    if not database["ok"]: raise HTTPException(status_code=503,detail={"reason":"database_not_ready","database":database})
    return envelope(data)

from app.api import auth, business, chat, commercial, debug, plan, prompt_admin, scan, tts
for router in (auth.router,scan.router,chat.router,plan.router,business.router,commercial.router,prompt_admin.router,tts.router,debug.router): app.include_router(router,prefix="/api")
