import json, re, uuid
from fastapi import HTTPException
from app.core.metrics import metrics
from app.core.router import build_route
from app.db import connection, now_iso

STATES=["IDLE","UNDERSTAND","COLLECT","PLAN","ROUTE","CONFIRM","EXECUTE","DONE"]
TEMPLATES={
 "date":{"required":["time","people","budget_per_person","cuisine","want_movie"],"stores":["s01","s07","s09"],"actions":["reserve_restaurant","claim_coupon","buy_ticket"]},
 "banquet":{"required":["time","people","total_budget","cuisine","private_room"],"stores":["s02","s19"],"actions":["reserve_restaurant","claim_coupon"]},
 "gift":{"required":["recipient","budget","preferences","occasion"],"stores":["s13","s14","s06"],"actions":["claim_coupon"]},
 "family_day":{"required":["child_age","duration","budget","interests","meal_preference"],"stores":["s10","s12","s11"],"actions":["buy_ticket","reserve_restaurant","claim_coupon"]},
 "business":{"required":["time","people","total_budget","level","quiet","meal_preference"],"stores":["s16","s05","s17"],"actions":["reserve_business_space","reserve_restaurant","claim_coupon"]}}
# 场景默认槽位：用户只说出「目标」(如「帮我规划约会」)但没给明细时，用默认值直接生成方案，避免空方案
DEFAULT_SLOTS={
 "date":{"time":"今晚7点","people":2,"budget_per_person":200,"cuisine":"川菜","want_movie":True},
 "banquet":{"time":"周末6点","people":6,"total_budget":1000,"cuisine":"川菜","private_room":True},
 "gift":{"recipient":"朋友","budget":300,"preferences":"设计感小物","occasion":"礼物"},
 "family_day":{"child_age":6,"duration":4,"budget":500,"interests":"游乐","meal_preference":"亲子餐"},
 "business":{"time":"明天下午3点","people":4,"total_budget":1500,"level":"高端","quiet":True,"meal_preference":"中餐"}}

def detect_scene(text):
    for scene,words in [("business",["商务","客户"]),("family_day",["带娃","孩子","亲子"]),("gift",["礼物","生日"]),("banquet",["家宴","包间"]),("date",["约会","电影"])]:
        if any(w in text for w in words): return scene
    return None

def extract_slots(scene,text):
    slots={}; num=re.search(r"(\d+|[一二两三四五六七八九十])\s*(?:位|个人|人)",text); money=re.search(r"(?:人均|预算)\s*(\d+)",text); time=re.search(r"((?:今晚|明天|周末)?\s*(?:下午|晚上)?\s*\d{1,2}\s*点)",text)
    if num:
        raw=num.group(1); slots["people"]=int(raw) if raw.isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}[raw]
    if money: slots["budget_per_person" if "人均" in text and scene=="date" else "total_budget" if scene in ("banquet","business") else "budget"]=int(money.group(1))
    if time: slots["time"]=time.group(1).replace(" ","")
    if scene=="date": slots.update({"cuisine":"川菜" if "川菜" in text else None,"want_movie":"电影" in text or "观影" in text})
    elif scene=="banquet": slots.update({"cuisine":"川菜" if "川菜" in text else "粤菜" if "粤菜" in text else None,"private_room":"包间" in text})
    elif scene=="gift": slots.update({"recipient":"22岁女生" if "22" in text else "朋友" if "朋友" in text else None,"preferences":"香氛和设计感小物" if "香氛" in text else None,"occasion":"生日" if "生日" in text else None})
    elif scene=="family_day":
        age=re.search(r"(\d+)\s*岁",text); duration=re.search(r"(\d+)\s*小时",text); slots.update({"child_age":int(age.group(1)) if age else None,"duration":int(duration.group(1)) if duration else None,"interests":"游乐" if "玩" in text else None,"meal_preference":"亲子餐" if "吃饭" in text else None})
    elif scene=="business": slots.update({"level":"高端" if "档次" in text or "高端" in text else None,"quiet":"安静" in text,"meal_preference":"高端中餐" if "吃饭" in text else None})
    return {k:v for k,v in slots.items() if v is not None}

def create_plan(user_id,mall_id,session_id,text,scene=None,slots=None):
    scene=scene or detect_scene(text)
    if scene not in TEMPLATES: raise HTTPException(status_code=422,detail="无法识别规划场景")
    merged=extract_slots(scene,text); merged.update(slots or {})
    missing_original=[s for s in TEMPLATES[scene]["required"] if s not in merged]
    missing=missing_original
    # 缺槽位 → 用场景默认槽位补全，使「只说目标」也能直接生成方案
    if missing:
        merged.update({k:v for k,v in DEFAULT_SLOTS[scene].items() if k not in merged})
        missing=[s for s in TEMPLATES[scene]["required"] if s not in merged]
        if missing: state="COLLECT"; itinerary=[]; route={}; history=["IDLE","UNDERSTAND","COLLECT"]; plan_id="plan_"+uuid.uuid4().hex[:12]; now=now_iso()
        else: plan_id,itinerary,route,state,history=_build_itinerary(user_id,mall_id,scene,merged)
    else:
        plan_id,itinerary,route,state,history=_build_itinerary(user_id,mall_id,scene,merged)
    if state=="COLLECT":
        now=now_iso()
        with connection() as db:
            db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),plan_id,state,json.dumps({"state_history":history,"missing_slots":missing_original},ensure_ascii=False),now))
            db.execute("INSERT INTO plans VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(plan_id,session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),state,json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),"[]",now,now))
        return {"plan_id":plan_id,"session_id":session_id,"scene":scene,"slots":merged,"missing_slots":missing_original,"state":state,"state_history":history,"itinerary":itinerary,"route":route,"card":{"type":"plan","title":f"{scene} 方案","status":state}}
    now=now_iso()
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),plan_id,state,json.dumps({"state_history":history,"missing_slots":missing_original},ensure_ascii=False),now))
        db.execute("INSERT INTO plans VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(plan_id,session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),state,json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),"[]",now,now))
    return {"plan_id":plan_id,"session_id":session_id,"scene":scene,"slots":merged,"missing_slots":missing_original,"state":state,"state_history":history,"itinerary":itinerary,"route":route,"card":{"type":"plan","title":f"{scene} 方案","status":state}}

SCENE_NAMES={"date":"约会","banquet":"家宴","gift":"礼物","family_day":"带娃","business":"商务"}

def create_plan_from_agent(user_id,mall_id,session_id,text,scene,plan_data,reply=""):
    """把在线大模型规划选中的店固化为可确认、可预约的方案记录（state=CONFIRM）。"""
    if scene not in TEMPLATES: scene=detect_scene(text) or "date"
    ids=[i for i in (plan_data.get("store_ids") or []) if isinstance(i,str)]
    stores=[]
    if ids:
        ph=",".join("?" for _ in ids)
        with connection() as db:
            rows=db.execute(f"SELECT * FROM stores WHERE mall_id=? AND id IN ({ph})",(mall_id,*ids)).fetchall()
        by={r["id"]:dict(r) for r in rows}; stores=[by[i] for i in ids if i in by]
    if not stores:
        # 大模型没给出有效店 → 回退到规则方案，避免空方案
        return create_plan(user_id,mall_id,session_id,text,scene)
    slots=dict(DEFAULT_SLOTS.get(scene,{})); slots.update(plan_data.get("slots") or {})
    time_plan=plan_data.get("time_plan") or {}
    for s in stores: s["time_label"]=time_plan.get(s["id"]) or slots.get("time","")
    node_ids=[s["id"] for s in stores]; route=build_route(mall_id,node_ids)
    plan_id="plan_"+uuid.uuid4().hex[:12]; history=["IDLE","UNDERSTAND","COLLECT","PLAN","ROUTE","CONFIRM"]; state="CONFIRM"; now=now_iso()
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,user_id,mall_id,scene,json.dumps(slots,ensure_ascii=False),plan_id,state,json.dumps({"state_history":history,"missing_slots":[],"source":"online_agent"},ensure_ascii=False),now))
        db.execute("INSERT INTO plans VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(plan_id,session_id,user_id,mall_id,scene,json.dumps(slots,ensure_ascii=False),state,json.dumps(stores,ensure_ascii=False),json.dumps(route,ensure_ascii=False),"[]",now,now))
    return {"plan_id":plan_id,"session_id":session_id,"scene":scene,"slots":slots,"missing_slots":[],"state":state,"state_history":history,"itinerary":stores,"route":route,"source":"online_agent","card":{"type":"plan","title":f"{SCENE_NAMES.get(scene,scene)} 方案（智能 Agent）","status":state}}

# 场景规则：scenes 按槽位动态挑店（category / tags / avg_price 匹配），体现用户偏好
SCENE_PICKS = {
  "date":     [("drink", ["奶茶","咖啡","烘焙","甜品","茶歇"]), ("movie", ["影院"])],
  "banquet":  [("restaurant", ["川菜","粤菜","高端餐厅"]), ("gift", ["礼品"])],
  "gift":     [("gift", ["礼品","香氛","设计零售","玩具"])],
  "family_day": [("kid", ["儿童乐园","亲子餐厅","玩具"]), ("restaurant", ["亲子餐厅"]), ("drink", ["甜品","奶茶","烘焙"])],
  "business": [("biz", ["高端餐厅","商务空间","茶歇","轻食"])],
}

def _match_cuisine(stores, cuisine):
    if not cuisine: return []
    c = cuisine.strip()
    # 直接按 category 含口味 或 tags 含
    hit = [s for s in stores if c in s["category"] or c in s["tags"]]
    return hit

def _build_itinerary(user_id, mall_id, scene, slots):
    with connection() as db: stores=[dict(r) for r in db.execute("SELECT * FROM stores WHERE mall_id=?", (mall_id,)).fetchall()]
    chosen=[]; used=set()
    cuisine = slots.get("cuisine") or slots.get("meal_preference")
    # 1) 按槽位口味优先匹配餐厅（取一家，避免同菜系重复）
    if cuisine:
        for s in _match_cuisine(stores, cuisine):
            if s["id"] not in used and s["category"] not in ("服务台",):
                chosen.append(s); used.add(s["id"]); break   # 只取第一家
    # 2) 按场景类型补齐其它业态
    for kind, cats in SCENE_PICKS.get(scene, []):
        cand=[s for s in stores if s["id"] not in used and s["category"] in cats and s["category"]!="服务台"]
        if cand: chosen.append(cand[0]); used.add(cand[0]["id"])
    # 3) 若还没凑齐场景模板数量，用模板店铺兜底
    ids=[s["id"] for s in chosen]
    for sid in TEMPLATES[scene]["stores"]:
        if len(ids) >= len(TEMPLATES[scene]["stores"]): break
        if sid not in ids:
            row=[s for s in stores if s["id"]==sid]
            if row: chosen.append(row[0]); ids.append(sid)
    itinerary=chosen[:max(len(TEMPLATES[scene]["stores"]),1)]
    # 若仍有空，用任意非服务台店填充
    if not itinerary:
        fallback=[s for s in stores if s["category"]!="服务台"]
        itinerary=fallback[:len(TEMPLATES[scene]["stores"])]
    node_ids=[s["id"] for s in itinerary]
    history=["IDLE","UNDERSTAND","COLLECT","PLAN"]
    history.append("ROUTE"); route=build_route(mall_id,node_ids); history.append("CONFIRM")
    return "plan_"+uuid.uuid4().hex[:12], itinerary, route, "CONFIRM", history

def _claim(db,user_id,mall_id,coupon_id):
    row=db.execute("SELECT * FROM coupons WHERE id=? AND mall_id=? AND stock>0",(coupon_id,mall_id)).fetchone()
    if not row: raise HTTPException(status_code=409,detail="coupon unavailable")
    existing=db.execute("SELECT * FROM user_coupons WHERE coupon_id=? AND user_id=? AND mall_id=?",(coupon_id,user_id,mall_id)).fetchone()
    if existing: return {"tool":"claim_coupon","status":"already_claimed","coupon_id":coupon_id}
    cid="uc_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO user_coupons VALUES(?,?,?,?,?)",(cid,coupon_id,user_id,mall_id,now_iso())); db.execute("UPDATE coupons SET stock=stock-1 WHERE id=?",(coupon_id,)); return {"tool":"claim_coupon","status":"success","coupon_id":coupon_id,"user_coupon_id":cid}

def confirm_plan(user_id,plan_id,decision):
    with connection() as db:
        row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
        if not row: raise HTTPException(status_code=404,detail="plan not found")
        if decision not in ("confirm","确认","同意"): raise HTTPException(status_code=422,detail="only explicit confirm executes writes")
        if row["state"]!="CONFIRM": raise HTTPException(status_code=409,detail="plan is not awaiting confirmation")
        scene=row["scene"]; mall=row["mall_id"]; slots=json.loads(row["slots_json"]); results=[]; itinerary=json.loads(row["itinerary_json"])
        db.execute("UPDATE plans SET state='EXECUTE',updated_at=? WHERE id=?",(now_iso(),plan_id))
        for action in TEMPLATES[scene]["actions"]:
            if action=="claim_coupon": results.append(_claim(db,user_id,mall,{"date":"c1","banquet":"c1","gift":"c2","family_day":"c3","business":"c4"}[scene]))
            elif action=="buy_ticket":
                product="t_movie" if scene=="date" else "t_child"; product_row=db.execute("SELECT * FROM ticket_products WHERE id=? AND mall_id=? AND stock>0",(product,mall)).fetchone()
                if product_row:
                    qty=slots.get("people",1); tid="ut_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO user_tickets VALUES(?,?,?,?,?,?)",(tid,product,user_id,mall,qty,now_iso())); db.execute("UPDATE ticket_products SET stock=stock-? WHERE id=?",(qty,product)); results.append({"tool":"buy_ticket","status":"success","ticket_id":tid,"quantity":qty})
            elif action in ("reserve_restaurant","reserve_business_space"):
                wanted="商务空间" if action=="reserve_business_space" else None; store=next((s for s in itinerary if (wanted and s["category"]==wanted) or (not wanted and s["reservable"] and s["category"]!="商务空间")),None)
                if store:
                    rid="res_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)",(rid,user_id,mall,store["id"],"business" if wanted else "restaurant",slots.get("time","演示时段"),slots.get("people",2),"由确认后的规划创建","confirmed",now_iso())); results.append({"tool":action,"status":"success","reservation_id":rid,"store_id":store["id"]})
        # 为方案中可预约/需排队的店批量建档，供「到号提醒」使用
        queued_ids={r["store_id"] for r in results if r.get("store_id")}
        for store in itinerary:
            sid=store.get("id")
            if not sid or sid in queued_ids: continue
            if not store.get("reservable"): continue
            q=int(store.get("queue_minutes") or 0)
            rid="res_"+uuid.uuid4().hex[:10]
            db.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)",(rid,user_id,mall,sid,"queue",slots.get("time","演示时段"),slots.get("people",2),f"规划排队约{q}分钟","queued",now_iso()))
            results.append({"tool":"queue","status":"queued","store_id":sid,"queue_minutes":q,"reservation_id":rid})
        db.execute("UPDATE plans SET state='DONE',action_results_json=?,updated_at=? WHERE id=?",(json.dumps(results,ensure_ascii=False),now_iso(),plan_id)); db.execute("UPDATE sessions SET plan_state='DONE',updated_at=? WHERE id=?",(now_iso(),row["session_id"]))
    metrics.increment(f"scenario_{scene}_success"); metrics.increment("tool_calls"); return get_plan(user_id,plan_id)

def revise_plan(user_id,plan_id,modifications):
    with connection() as db:
        row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
        if not row: raise HTTPException(status_code=404,detail="plan not found")
        if row["state"]!="CONFIRM": raise HTTPException(status_code=409,detail="only a pending plan can be modified")
        slots=json.loads(row["slots_json"]); slots.update(modifications or {}); itinerary=json.loads(row["itinerary_json"])
        if modifications.get("cheaper") and itinerary:
            itinerary=sorted(itinerary,key=lambda item:item["avg_price"])
        route=build_route(row["mall_id"],[item["id"] for item in itinerary])
        db.execute("UPDATE plans SET slots_json=?,state='CONFIRM',itinerary_json=?,route_json=?,updated_at=? WHERE id=?",(json.dumps(slots,ensure_ascii=False),json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),now_iso(),plan_id))
        db.execute("UPDATE sessions SET slots_json=?,plan_state='CONFIRM',updated_at=? WHERE id=?",(json.dumps(slots,ensure_ascii=False),now_iso(),row["session_id"]))
    result=get_plan(user_id,plan_id); result["state_history"]=["CONFIRM","PLAN","ROUTE","CONFIRM"]; return result

def get_plan(user_id,plan_id):
    with connection() as db: row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="plan not found")
    state=row["state"]; state_history=STATES[:STATES.index(state)+1]
    return {"plan_id":row["id"],"session_id":row["session_id"],"mall_id":row["mall_id"],"scene":row["scene"],"slots":json.loads(row["slots_json"]),"state":state,"state_history":state_history,"itinerary":json.loads(row["itinerary_json"]),"route":json.loads(row["route_json"]),"action_results":json.loads(row["action_results_json"]),"card":{"type":"itinerary" if state=="DONE" else "plan","status":state}}
