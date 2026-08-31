from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.llm import LLMAdapter
from app.core.navigation import is_navigation_intent, resolve_navigation
from app.core.orchestrator import try_online
from app.core.planner import detect_scene, create_plan
from app.core.tools import run_tool
from app.db import connection

router=APIRouter(tags=["chat"])
class ChatBody(BaseModel): session_id:str; message:str
@router.post("/chat")
def chat(body:ChatBody,auth:AuthContext=Depends(require_auth)):
    with connection() as db: session=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=?",(body.session_id,auth.user_id)).fetchone()
    if not session: raise HTTPException(status_code=404,detail="session not found")
    if is_navigation_intent(body.message):
        navigation=resolve_navigation(session["mall_id"],body.message)
        destination=navigation["destination_store"]
        reply=f"已为你找到前往{destination['name']}的路线，导航动画已打开。当前预计排队 {destination['queue_minutes']} 分钟。"
        return envelope({"reply":reply,"intent":"navigation","navigation":navigation,"cards":[navigation],"degraded":False})
    scene=detect_scene(body.message)
    if scene:
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,body.message,scene); return envelope({"reply":"我已理解目标并生成方案，请确认后再执行预约、领券或购票。","intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":True,"degraded_reason":"scripted fallback"})
    context={"user_id":auth.user_id,"mall_id":session["mall_id"],"session_id":body.session_id}; text=body.message
    online=try_online(text,context)
    if online: return envelope({**online,"intent":"online_tool_loop","cards":[]})
    if "停车" in text: tool="query_parking_status"; args={}; reply="已查询 QD square 停车状态。"; card="parking"
    elif "积分" in text and any(w in text for w in ["过期","生日","兑换","规则"]): tool="query_points_rules"; args={"query":text}; reply="以下回答只依据积分规则知识库。"; card="rag"
    elif "积分" in text: tool="query_member_points"; args={}; reply="已查询你的会员积分。"; card="member"
    elif "优惠" in text or "特惠" in text: tool="get_today_deals"; args={}; reply="这是今天仍有库存的特惠。"; card="deals"
    else: tool="search_stores"; args={"keyword":text}; reply="已在当前商场私有店铺库中搜索。"; card="stores"
    result=run_tool(tool,context,args); mode=LLMAdapter().chat([])
    return envelope({"reply":reply,"intent":tool,"tool_calls":[{"name":tool,"arguments":args}],"result":result,"cards":[{"type":card,"data":result}],**mode})
