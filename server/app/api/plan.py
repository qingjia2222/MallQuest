import json, re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.planner import confirm_plan, copy_plan_for_edit, create_plan, get_plan, revise_plan
from app.core.tools import live_store_status
from app.db import connection, rows_to_dicts

router=APIRouter(prefix="/plan",tags=["plan"])
class PlanBody(BaseModel): session_id:str; text:str=""; scene:str|None=None; slots:dict=Field(default_factory=dict)
class ConfirmBody(BaseModel): plan_id:str; decision:str; modifications:dict=Field(default_factory=dict)
class PlanPatchBody(BaseModel): itinerary:list[dict]|None=None; strategy:str|None=None; vertical_mode:str|None=None; selected_movie:str|None=None
class EditableCopyBody(BaseModel):
    session_id:str
    source_plan_id:str|None=None
    scene:str="date"
    slots:dict=Field(default_factory=dict)
    itinerary:list[dict]=Field(default_factory=list)
    vertical_mode:str="elevator"
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
    if body.modifications: revise_plan(auth.user_id,body.plan_id,body.modifications)
    return envelope(confirm_plan(auth.user_id,body.plan_id,body.decision))
@router.patch("/{plan_id}")
def patch_plan(plan_id:str,body:PlanPatchBody,auth:AuthContext=Depends(require_auth)):
    return envelope(revise_plan(auth.user_id,plan_id,body.model_dump(exclude_none=True)))
@router.post("/editable-copy")
def editable_copy(body:EditableCopyBody,auth:AuthContext=Depends(require_auth)):
    session=session_for(auth.user_id,body.session_id)
    return envelope(copy_plan_for_edit(auth.user_id,session["mall_id"],body.session_id,body.source_plan_id,body.scene,body.slots,body.itinerary,body.vertical_mode))
def _parse_time(text):
    """把「今晚19:00 / 明天下午3点」这类时间解析成 datetime，算不了就返回 None。"""
    if not text: return None
    t=text.strip(); now=datetime.now(); day=now.date()
    if "明天" in t or "明晚" in t: day=now.date()+timedelta(days=1)
    m=re.search(r"(\d{1,2})(?::|点)(\d{2})?", t) or re.search(r"(\d{1,2})\s*点", t)
    if not m: return None
    hh=int(m.group(1)); mm=int(m.group(2)) if m.group(2) else 0
    if ("下午" in t or "晚上" in t or "晚" in t) and hh<12: hh+=12
    try: return datetime.combine(day, datetime.min.time()).replace(hour=hh,minute=mm)
    except Exception: return None

@router.get("/live-status")
def live_status(plan_id:str=Query(...),auth:AuthContext=Depends(require_auth)):
    plan=get_plan(auth.user_id,plan_id); ids=[s["id"] for s in plan["itinerary"]]
    status=live_store_status(mall_id=plan["mall_id"],store_ids=ids)
    order={store_id:index for index,store_id in enumerate(ids)}
    status.sort(key=lambda item:order.get(item["store_id"],len(order)))
    if not ids: return envelope({"plan_id":plan_id,"state":plan["state"],"slots":plan["slots"],"status":[]})
    ph=",".join("?" for _ in ids)
    with connection() as db:
        rows=db.execute(f"SELECT * FROM reservations WHERE user_id=? AND store_id IN ({ph}) AND status IN ('queued','confirmed')",(auth.user_id,*ids)).fetchall()
    reservations={r["store_id"]:r for r in rows_to_dicts(rows)}
    names={s["id"]:s.get("name","") for s in plan["itinerary"]}
    planned_times={s["id"]:s.get("time_label") or plan["slots"].get("time") for s in plan["itinerary"]}
    now=datetime.now()
    for st in status:
        sid=st["store_id"]; r=reservations.get(sid)
        st["display_name"]=names.get(sid,"")
        st["reservation_status"]=r["status"] if r else None
        st["reservation_kind"]=r["kind"] if r else None
        st["reserved_for"]=r["reserved_for"] if r else None
        q=int(st.get("queue_minutes") or 0)
        st["ahead_tables"]=max(0,round(q/4))                 # 前面等候桌数（按排队时长估算）
        target=_parse_time(planned_times.get(sid))
        st["planned_time"]=planned_times.get(sid)
        st["arrival_in_minutes"]=max(0,int((target-now).total_seconds()//60)) if target else None  # 距该店计划到店时间还有多少分钟
        st["can_dine_on_time"]=(q <= (st["arrival_in_minutes"] or 0)) if target else None           # 能否准时就餐
    return envelope({"plan_id":plan_id,"state":plan["state"],"slots":plan["slots"],"status":status})
@router.get("/{plan_id}")
def plan_detail(plan_id:str,auth:AuthContext=Depends(require_auth)): return envelope(get_plan(auth.user_id,plan_id))
