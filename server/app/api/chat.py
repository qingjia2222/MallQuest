import json, logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.llm import LLMAdapter
from app.core.orchestrator import try_online, try_online_planning
from app.core.planner import detect_scene, create_plan, create_plan_from_agent, is_plain_query, is_plan_request
from app.core.tools import run_tool
from app.db import connection
log=logging.getLogger("mall-assistant.chat")

def _plan_existing(session):
    """取该会话当前已生成方案里的店铺名，供规划 agent 在其基础上增补。"""
    pid = session["plan_id"] if session and session["plan_id"] else None
    if not pid: return None
    with connection() as db:
        row = db.execute("SELECT itinerary_json FROM plans WHERE id=? AND user_id=?", (pid, session["user_id"])).fetchone()
    if not row: return None
    try:
        it = json.loads(row["itinerary_json"])
        names = [s.get("name") for s in it if s.get("name")]
        return "、".join(names) if names else None
    except Exception:
        return None

def _fallback_store_ids(agent):
    """大模型没写 store_ids 时，从它 search_stores 的结果里兜底取店。"""
    for obs in agent.get("tool_calls", []) or []:
        if obs.get("name") == "search_stores":
            res = obs.get("result")
            if isinstance(res, list) and res:
                ids = [s.get("id") for s in res if s.get("id")]
                if ids: return ids[:5]
    return []

router=APIRouter(tags=["chat"])
class ChatBody(BaseModel): session_id:str; message:str
@router.post("/chat")
def chat(body:ChatBody,auth:AuthContext=Depends(require_auth)):
    with connection() as db: session=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=?",(body.session_id,auth.user_id)).fetchone()
    if not session: raise HTTPException(status_code=404,detail="session not found")
    text=body.message
    context={"user_id":auth.user_id,"mall_id":session["mall_id"],"session_id":body.session_id}
    scene=detect_scene(text)
    if not scene and is_plan_request(text) and not is_plain_query(text): scene="casual"
    if scene:
        existing=_plan_existing(session)
        agent=try_online_planning(text,context,scene,existing)
        if agent and agent.get("reply"):
            try:
                pd=agent.get("plan_json") or {}
                if not pd.get("store_ids"):
                    pd["store_ids"]=_fallback_store_ids(agent)
                plan = create_plan_from_agent(auth.user_id,session["mall_id"],body.session_id,text,scene,pd,agent.get("reply","")) if pd.get("store_ids") else create_plan(auth.user_id,session["mall_id"],body.session_id,text,scene)
                if plan and plan.get("itinerary"):
                    return envelope({"reply":agent.get("reply") or "已为你智能规划出方案，请确认后再执行预约或排号。","intent":"plan","plan":plan,"cards":[plan["card"]],"tool_calls":agent.get("tool_calls",[]),"degraded":False,"mode":"online","source":"online_agent"})
            except HTTPException:
                pass
            except Exception as exc:
                log.exception("plan_from_agent_failed error_type=%s",type(exc).__name__)
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,scene); return envelope({"reply":"我已理解目标并生成方案，请确认后再执行预约、领券或购票。","intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":True,"degraded_reason":"scripted fallback"})
    online=try_online(text,context)
    if online: return envelope({**online,"intent":"online_tool_loop","cards":[]})
    if "停车" in text: tool="query_parking_status"; args={}; reply="已查询 QD square 停车状态。"; card="parking"
    elif "积分" in text and any(w in text for w in ["过期","生日","兑换","规则"]): tool="query_points_rules"; args={"query":text}; reply="以下回答只依据积分规则知识库。"; card="rag"
    elif "积分" in text: tool="query_member_points"; args={}; reply="已查询你的会员积分。"; card="member"
    elif "优惠" in text or "特惠" in text: tool="get_today_deals"; args={}; reply="这是今天仍有库存的特惠。"; card="deals"
    else: tool="search_stores"; args={"keyword":text}; reply="已在当前商场私有店铺库中搜索。"; card="stores"
    result=run_tool(tool,context,args); mode=LLMAdapter().chat([])
    return envelope({"reply":reply,"intent":tool,"tool_calls":[{"name":tool,"arguments":args}],"result":result,"cards":[{"type":card,"data":result}],**mode})
