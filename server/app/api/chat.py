import json, logging, re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.llm import LLMAdapter
from app.core.navigation import is_navigation_intent, resolve_navigation
from app.core.orchestrator import try_online, try_online_planning
from app.core.planner import detect_scene, create_plan, create_plan_from_agent, is_plain_query, is_plan_request
from app.core.tools import run_tool
from app.datasource.registry import registry
from app.db import connection, load_json, now_iso, rows_to_dicts
from app.core.text import plain_text
log=logging.getLogger("mall-assistant.chat")

ACTION_WORDS={
    "reserve_restaurant": ("预约", "预订", "订位", "排号"),
    "claim_coupon": ("领券", "领取优惠券", "领优惠券"),
    "buy_ticket": ("买电影票", "购买电影票", "订电影票", "购票"),
    "purchase_deal": ("抢购", "购买特惠", "购买优惠", "下单特惠"),
}
ACTION_LABELS={"reserve_restaurant":"预约","claim_coupon":"领取优惠券","buy_ticket":"购买电影票","purchase_deal":"购买限时特惠"}

def _explicit_action(text):
    """识别需要写业务数据的明确动作；真正写入仍必须经过 Plan 确认门禁。"""
    if any(word in text for word in ("规划", "方案", "攻略", "行程", "路线", "安排")):
        return None
    if "优惠券" in text and any(word in text for word in ("领", "领取", "帮我拿")):
        return "claim_coupon"
    for action,words in ACTION_WORDS.items():
        if any(word in text for word in words): return action
    return None

def _mentioned_stores(mall_id,text,action):
    """优先按数据库中的完整店名识别，避免把“帮我预约沃德面包”整句送进 LIKE。"""
    stores=registry.stores(mall_id,"")
    exact=[store for store in stores if store.get("name") and store["name"] in text]
    if exact: return sorted(exact,key=lambda item:len(item["name"]),reverse=True)
    if action=="buy_ticket":
        cinemas=[store for store in stores if store.get("category")=="影院"]
        if len(cinemas)==1: return cinemas
    cleaned=text
    for words in ACTION_WORDS.values():
        for word in words: cleaned=cleaned.replace(word,"")
    cleaned=re.sub(r"^(?:请|麻烦|帮我|我要|我想|想要)+|(?:一下|一个|吧|。|！|!|？|\?)+$","",cleaned.strip())
    return registry.stores(mall_id,cleaned) if cleaned else []

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

def _history(session):
    context=load_json(session["context_json"]); history=context.get("conversation_history") or []
    return [item for item in history[-12:] if item.get("role") in {"user","assistant"} and item.get("content")]

def _remember(session_id,user_text,assistant_text):
    with connection() as db:
        row=db.execute("SELECT context_json FROM sessions WHERE id=?",(session_id,)).fetchone(); context=load_json(row["context_json"] if row else "{}")
        history=context.get("conversation_history") or []; history.extend([{"role":"user","content":user_text},{"role":"assistant","content":plain_text(assistant_text)}])
        context["conversation_history"]=history[-20:]
        db.execute("UPDATE sessions SET context_json=?,updated_at=? WHERE id=?",(json.dumps(context,ensure_ascii=False),now_iso(),session_id))

router=APIRouter(tags=["chat"])
class ChatBody(BaseModel): session_id:str; message:str
@router.post("/chat")
def chat(body:ChatBody,auth:AuthContext=Depends(require_auth)):
    with connection() as db: session=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=?",(body.session_id,auth.user_id)).fetchone()
    if not session: raise HTTPException(status_code=404,detail="session not found")
    text=body.message
    context={"user_id":auth.user_id,"mall_id":session["mall_id"],"session_id":body.session_id,"history":_history(session)}
    def done(payload):
        payload["reply"]=plain_text(payload.get("reply") or "")
        _remember(body.session_id,text,payload["reply"])
        return envelope(payload)
    if is_navigation_intent(text):
        session_context=load_json(session["context_json"]); navigation=resolve_navigation(session["mall_id"],text,session_context.get("entry_node"))
        destination=navigation["destination_store"]
        return done({"reply":f"已为你找到前往{destination['name']}的路线，路线动画已打开。当前预计排队 {destination['queue_minutes']} 分钟。","intent":"navigation","navigation":navigation,"cards":[navigation],"degraded":False})
    action=_explicit_action(text)
    if action:
        matches=_mentioned_stores(session["mall_id"],text,action)
        if action=="buy_ticket": matches=[store for store in matches if store.get("category")=="影院"]
        if not matches:
            if action=="buy_ticket":
                return done({"reply":"当前地图与商场数据库中没有电影院，暂不提供电影票购买。我不会创建虚假影院或票务记录。","intent":"movie_ticket_unavailable","result":[],"cards":[],"degraded":False,"source":"transaction_router"})
            return done({"reply":f"我识别到你要{ACTION_LABELS[action]}，但当前商场没有找到对应店铺。请只补充店名，我会接着处理。","intent":"action_store_missing","result":[],"cards":[{"type":"stores","data":[]}],"degraded":False,"source":"transaction_router"})
        store=matches[0]
        if action=="reserve_restaurant" and not store.get("reservable"):
            return done({"reply":f"已找到{store['name']}，但该店当前未开放预约。你可以让我查询实时排队，或换一家可预约店铺。","intent":"reservation_unavailable","result":[store],"cards":[{"type":"stores","data":[store]}],"degraded":False,"source":"transaction_router"})
        slots={"requested_actions":[action]}
        if action=="purchase_deal":
            with connection() as db:
                deals=rows_to_dicts(db.execute("SELECT id,title,stock FROM deals WHERE mall_id=? AND store_id=? AND stock>0 ORDER BY id",(session["mall_id"],store["id"])).fetchall())
            if not deals:
                return done({"reply":f"已找到{store['name']}，但该店当前没有可购买的限时特惠。你可以让我查询今日特惠。","intent":"deal_unavailable","result":[store],"cards":[{"type":"stores","data":[store]}],"degraded":False,"source":"transaction_router"})
            selected=next((deal for deal in deals if deal["title"] in text),deals[0]);slots["requested_deal_id"]=selected["id"]
        people=re.search(r"(\d+|[一二两三四五六七八九十])\s*(?:位|个人|人)",text)
        if people:
            raw=people.group(1); slots["people"]=int(raw) if raw.isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}[raw]
        time_match=re.search(r"((?:今天|今晚|明天|明晚)?\s*(?:下午|晚上)?\s*\d{1,2}(?::\d{2}|点\d{0,2}分?))",text)
        if time_match: slots["time"]=time_match.group(1).replace(" ","")
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,"casual",slots,{"store_ids":[store["id"]]},source="transaction_router")
        when=plan["slots"].get("time","今天18:00"); count=plan["slots"].get("people",2)
        reply=f"已找到{store['name']}（{store['floor']}F），并生成{ACTION_LABELS[action]}确认方案：{when}，{count}人。确认后才会正式写入，时间和人数仍可调整。"
        return done({"reply":reply,"intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":False,"mode":"deterministic","source":"transaction_router"})
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
                    return done({"reply":agent.get("reply") or "已为你智能规划出方案，请确认后再执行预约或排号。","intent":"plan","plan":plan,"cards":[plan["card"]],"tool_calls":agent.get("tool_calls",[]),"degraded":False,"mode":"online","source":"online_agent"})
            except HTTPException:
                pass
            except Exception as exc:
                log.exception("plan_from_agent_failed error_type=%s",type(exc).__name__)
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,scene); return done({"reply":"我已结合你的目标与当前排队时间生成方案，请选择用时最短或路程最近方案，确认后再执行预约、领券或购票。","intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":True,"degraded_reason":"scripted fallback"})
    code_match=re.search(r"(?:QD|MAP)-[A-Z0-9-]+",text.upper())
    if code_match:
        args={"keyword":code_match.group(0)}; result=run_tool("search_stores",context,args)
        reply=(f"店铺编码 {code_match.group(0)} 对应 {result[0]['name']}，位于 {result[0]['floor']}F，当前状态为 {result[0]['open_status']}。" if result else f"当前商场没有找到店铺编码 {code_match.group(0)}，请核对后再试。")
        return done({"reply":reply,"intent":"search_stores","tool_calls":[{"name":"search_stores","arguments":args}],"result":result,"cards":[{"type":"stores","data":result}],"degraded":False,"source":"private_store_code_tool"})
    online=try_online(text,context)
    if online: return done({**online,"intent":"online_tool_loop","cards":[]})
    if "停车" in text: tool="query_parking_status"; args={}; reply="已查询星河里停车状态。"; card="parking"
    elif "积分" in text and any(w in text for w in ["过期","生日","兑换","规则"]): tool="query_points_rules"; args={"query":text}; reply="以下回答只依据积分规则知识库。"; card="rag"
    elif "积分" in text: tool="query_member_points"; args={}; reply="已查询你的会员积分。"; card="member"
    elif "排队" in text or "等位" in text: tool="query_queue_status"; args={}; reply="以下店铺当前需要排队，已按等候时间从长到短排列。"; card="queue"
    elif "优惠" in text or "特惠" in text: tool="get_today_deals"; args={}; reply="这是今天仍有库存的特惠。"; card="deals"
    else: tool="search_stores"; args={"keyword":text}; reply="已在当前商场私有店铺库中搜索。"; card="stores"
    result=run_tool(tool,context,args); mode=LLMAdapter().chat([])
    return done({"reply":reply,"intent":tool,"tool_calls":[{"name":tool,"arguments":args}],"result":result,"cards":[{"type":card,"data":result}],**mode})
