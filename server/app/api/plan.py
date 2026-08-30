import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.planner import confirm_plan, create_plan, get_plan, revise_plan
from app.core.tools import live_store_status
from app.db import connection

router=APIRouter(prefix="/plan",tags=["plan"])
class PlanBody(BaseModel): session_id:str; text:str=""; scene:str|None=None; slots:dict=Field(default_factory=dict)
class ConfirmBody(BaseModel): plan_id:str; decision:str; modifications:dict=Field(default_factory=dict)
def session_for(user_id,session_id):
    with connection() as db: row=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=?",(session_id,user_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="session not found")
    return row
@router.post("/date")
@router.post("/goal")
def plan_goal(body:PlanBody,auth:AuthContext=Depends(require_auth)):
    session=session_for(auth.user_id,body.session_id); return envelope(create_plan(auth.user_id,session["mall_id"],body.session_id,body.text,body.scene,body.slots))
@router.get("/route")
def route(plan_id:str=Query(...),auth:AuthContext=Depends(require_auth)): return envelope(get_plan(auth.user_id,plan_id)["route"])
@router.post("/confirm")
def confirm(body:ConfirmBody,auth:AuthContext=Depends(require_auth)):
    if body.decision in ("modify","换一版","修改"): return envelope(revise_plan(auth.user_id,body.plan_id,body.modifications))
    return envelope(confirm_plan(auth.user_id,body.plan_id,body.decision))
@router.get("/live-status")
def live_status(plan_id:str=Query(...),auth:AuthContext=Depends(require_auth)):
    plan=get_plan(auth.user_id,plan_id); ids=[s["id"] for s in plan["itinerary"]]; return envelope({"plan_id":plan_id,"status":live_store_status(mall_id=plan["mall_id"],store_ids=ids)})
@router.get("/{plan_id}")
def plan_detail(plan_id:str,auth:AuthContext=Depends(require_auth)): return envelope(get_plan(auth.user_id,plan_id))
