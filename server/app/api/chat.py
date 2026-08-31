import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.llm import LLMAdapter
from app.core.navigation import is_navigation_intent, resolve_navigation
from app.core.orchestrator import try_online, try_online_planning
from app.core.planner import detect_scene, create_plan, create_plan_from_agent
from app.core.tools import run_tool
from app.db import connection, load_json
from app.core.text import plain_text
log=logging.getLogger("mall-assistant.chat")

router=APIRouter(tags=["chat"])
class ChatBody(BaseModel): session_id:str; message:str
@router.post("/chat")
def chat(body:ChatBody,auth:AuthContext=Depends(require_auth)):
    with connection() as db: session=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=?",(body.session_id,auth.user_id)).fetchone()
    if not session: raise HTTPException(status_code=404,detail="session not found")
    text=body.message
    context={"user_id":auth.user_id,"mall_id":session["mall_id"],"session_id":body.session_id}
    if is_navigation_intent(text):
        session_context=load_json(session["context_json"])
        navigation=resolve_navigation(session["mall_id"],text,session_context.get("entry_node"))
        destination=navigation["destination_store"]
        reply=f"已为你找到前往{destination['name']}的路线，导航动画已打开。当前预计排队 {destination['queue_minutes']} 分钟。"
        return envelope({"reply":reply,"intent":"navigation","navigation":navigation,"cards":[navigation],"degraded":False})
    scene=detect_scene(text)
    if scene:
        agent=try_online_planning(text,context,scene)
        if agent and agent.get("plan_json"):
            try:
                plan=create_plan_from_agent(auth.user_id,session["mall_id"],body.session_id,text,scene,agent["plan_json"],agent.get("reply",""))
                if plan and plan.get("itinerary"):
                    return envelope({"reply":plain_text(agent.get("reply") or "已为你智能规划出方案，请确认后再执行预约或排号。"),"intent":"plan","plan":plan,"cards":[plan["card"]],"tool_calls":agent.get("tool_calls",[]),"degraded":False,"mode":"online","source":"online_agent"})
            except HTTPException:
                pass
            except Exception as exc:
                log.exception("plan_from_agent_failed error_type=%s",type(exc).__name__)
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,scene); return envelope({"reply":"我已理解目标并生成方案，请确认后再执行预约、领券或购票。","intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":True,"degraded_reason":"scripted fallback"})
    online=try_online(text,context)
    if online: return envelope({**online,"reply":plain_text(online.get("reply","")),"intent":"online_tool_loop","cards":[]})
    if "停车" in text: tool="query_parking_status"; args={}; reply="已查询星河里停车状态。"; card="parking"
    elif "积分" in text and any(w in text for w in ["过期","生日","兑换","规则"]): tool="query_points_rules"; args={"query":text}; reply="以下回答只依据积分规则知识库。"; card="rag"
    elif "积分" in text: tool="query_member_points"; args={}; reply="已查询你的会员积分。"; card="member"
    elif "排队" in text or "等位" in text: tool="query_queue_status"; args={}; reply="以下店铺当前需要排队，已按等候时间从长到短排列。"; card="queue"
    elif "优惠" in text or "特惠" in text: tool="get_today_deals"; args={}; reply="这是今天仍有库存的特惠。"; card="deals"
    else: tool="search_stores"; args={"keyword":text}; reply="已在当前商场私有店铺库中搜索。"; card="stores"
    result=run_tool(tool,context,args); mode=LLMAdapter().chat([])
    return envelope({"reply":reply,"intent":tool,"tool_calls":[{"name":tool,"arguments":args}],"result":result,"cards":[{"type":card,"data":result}],**mode})
