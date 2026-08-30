import json
from fastapi import APIRouter, Depends, HTTPException
from app.config import settings
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.metrics import metrics
from app.db import connection
router=APIRouter(prefix="/debug",tags=["debug"])
@router.get("/metrics")
def metric_view(auth:AuthContext=Depends(require_auth)):
    if not settings.demo_debug: raise HTTPException(status_code=404,detail="debug disabled")
    return envelope(metrics.snapshot())
@router.get("/session/{session_id}")
def session_view(session_id:str,auth:AuthContext=Depends(require_auth)):
    if not settings.demo_debug: raise HTTPException(status_code=404,detail="debug disabled")
    with connection() as db: row=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=?",(session_id,auth.user_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="session not found")
    data=dict(row); data["slots"]=json.loads(data.pop("slots_json")); data["context"]=json.loads(data.pop("context_json")); return envelope(data)
