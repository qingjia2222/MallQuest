import itertools, json, math, re, uuid
from fastapi import HTTPException
from app.core.metrics import metrics
from app.core.router import build_route
from app.core.tools import live_store_status
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
    if scene=="date":
        movie=None
        if any(word in text for word in ("不要电影","不看电影","不观影")): movie=False
        elif "电影" in text or "观影" in text: movie=True
        slots.update({"cuisine":"川菜" if "川菜" in text else None,"want_movie":movie})
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
    alternatives=_optimized_alternatives(mall_id,scene,slots)
    if alternatives:
        selected=alternatives[0]; stores=selected["itinerary"]; route=_route_bundle(alternatives,selected["strategy"])
    else:
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

STRATEGY_LABELS={"fastest":"用时最短","shortest":"路程最近、回头路最少"}
# 可解释的固定权重：用时方案以分钟为主；短路方案以地图距离为主并对回头路双倍惩罚。
OPTIMIZATION_WEIGHTS={
  "fastest":{"wait_minute":1.0,"walk_minute":1.0,"floor_transfer":2.0,"budget_overage":0.03},
  # “路程最近”中排队仍会展示给用户，但不改变空间最优解，避免它退化成另一份“用时最短”。
  "shortest":{"distance":1.0,"backtrack_distance":2.0,"floor_transfer":25.0,"wait_minute":0.0},
}

def _live_stores(mall_id):
    with connection() as db: stores=[dict(row) for row in db.execute("SELECT * FROM stores WHERE mall_id=?",(mall_id,)).fetchall()]
    status={item["store_id"]:item for item in live_store_status(mall_id=mall_id,store_ids=[s["id"] for s in stores])}
    for item in stores:
        live=status.get(item["id"])
        if live: item.update({"open_status":live["open_status"],"queue_minutes":live["queue_minutes"],"seats_available":live["seats_available"]})
    return stores

def _category(stores,names):
    return [s for s in stores if s["category"] in names and s["category"]!="服务台" and s["open_status"]!="closed"]

def _candidate_groups(scene,stores,slots):
    cuisine=slots.get("cuisine") or slots.get("meal_preference")
    restaurants=_match_cuisine(stores,cuisine)
    restaurants=[s for s in restaurants if s["open_status"]!="closed" and s["category"]!="服务台"] or _category(stores,["川菜","粤菜","日料","西餐","高端餐厅","亲子餐厅","轻食"])
    if scene=="date":
        per_person=float(slots.get("budget_per_person") or 0)
        affordable=[s for s in restaurants if not per_person or float(s.get("avg_price") or 0)<=per_person]
        if affordable: restaurants=affordable
        groups=[restaurants,_category(stores,["奶茶","咖啡","烘焙","甜品","茶歇"])]
        if slots.get("want_movie",True): groups.append(_category(stores,["影院"]))
        return groups
    if scene=="banquet": return [restaurants,_category(stores,["礼品"])]
    if scene=="gift": return [_category(stores,["礼品","香氛","设计零售","玩具"])]
    if scene=="family_day": return [_category(stores,["儿童乐园","玩具"]),_category(stores,["亲子餐厅"]),_category(stores,["甜品","奶茶","烘焙"])]
    if scene=="business": return [_category(stores,["商务空间"]),_category(stores,["茶歇","咖啡","轻食"]),_category(stores,["高端餐厅","粤菜","川菜"])]
    return []

def _backtrack_distance(route):
    seen=set(); repeated=0.0
    for a,b in zip(route.get("nodes",[]),route.get("nodes",[])[1:]):
        edge=tuple(sorted((a["node_id"],b["node_id"])))
        distance=math.dist((a["x"],a["y"]),(b["x"],b["y"])) if a["floor"]==b["floor"] else 0
        if edge in seen: repeated+=distance
        seen.add(edge)
    return round(repeated,1)

def _plan_metrics(itinerary,route,slots,strategy):
    waiting=sum(int(s.get("queue_minutes") or 0) for s in itinerary)
    distance=float(route.get("estimated_distance") or 0); walking=round(distance/75,1)
    transfers=sum(1 for segment in route.get("polyline_segments",[]) if segment.get("transfer_instruction"))
    backtrack=_backtrack_distance(route)
    budget=sum(float(s.get("avg_price") or 0) for s in itinerary)
    target=float(slots.get("budget_per_person") or slots.get("budget") or slots.get("total_budget") or budget or 0)
    budget_penalty=max(0,budget-target)
    weights=OPTIMIZATION_WEIGHTS[strategy]
    if strategy=="fastest": score=waiting*weights["wait_minute"]+walking*weights["walk_minute"]+transfers*weights["floor_transfer"]+budget_penalty*weights["budget_overage"]
    else: score=distance*weights["distance"]+backtrack*weights["backtrack_distance"]+transfers*weights["floor_transfer"]+waiting*weights["wait_minute"]
    return {"strategy":strategy,"label":STRATEGY_LABELS[strategy],"score":round(score,2),
        "estimated_wait_minutes":waiting,"estimated_walk_minutes":walking,"estimated_total_minutes":round(waiting+walking+transfers*2,1),
        "estimated_distance":round(distance,1),"backtrack_distance":backtrack,"transfer_count":transfers,"estimated_spend_per_person":round(budget,1),"weights":weights}

def _optimized_option(mall_id,groups,slots,strategy):
    valid=[group for group in groups if group]
    if not valid: return None
    candidates=[]
    for combo in itertools.product(*valid):
        if len({s["id"] for s in combo})!=len(combo): continue
        itinerary=[dict(s) for s in combo]
        route=build_route(mall_id,[s["id"] for s in itinerary],vertical_mode="elevator")
        metrics=_plan_metrics(itinerary,route,slots,strategy)
        candidates.append((metrics["score"],tuple(s["id"] for s in itinerary),itinerary,route,metrics))
    if not candidates: return None
    _,_,itinerary,route,metrics=min(candidates,key=lambda item:(item[0],item[1]))
    for index,store in enumerate(itinerary,1):
        store["time_label"]=f"第 {index} 站"; store["planned_wait_minutes"]=int(store.get("queue_minutes") or 0)
    route["optimization"]=metrics
    return {"strategy":strategy,"label":STRATEGY_LABELS[strategy],"itinerary":itinerary,"route":route,"metrics":metrics}

def _optimized_alternatives(mall_id,scene,slots):
    stores=_live_stores(mall_id); groups=_candidate_groups(scene,stores,slots)
    options=[_optimized_option(mall_id,groups,slots,strategy) for strategy in ("fastest","shortest")]
    return [option for option in options if option]

def _route_bundle(alternatives,selected_strategy="fastest"):
    selected=next((item for item in alternatives if item["strategy"]==selected_strategy),alternatives[0])
    route=dict(selected["route"])
    route["selected_strategy"]=selected["strategy"]
    route["optimization"]=selected["metrics"]
    route["alternatives"]=[{"strategy":item["strategy"],"label":item["label"],"itinerary":item["itinerary"],"route":item["route"],"metrics":item["metrics"]} for item in alternatives]
    return route

def _match_cuisine(stores, cuisine):
    if not cuisine: return []
    c = cuisine.strip()
    # 直接按 category 含口味 或 tags 含
    hit = [s for s in stores if c in s["category"] or c in s["tags"]]
    return hit

def _build_itinerary(user_id, mall_id, scene, slots):
    alternatives=_optimized_alternatives(mall_id,scene,slots)
    if alternatives:
        selected=alternatives[0]; itinerary=selected["itinerary"]; route=_route_bundle(alternatives,selected["strategy"])
    else:
        stores=_live_stores(mall_id); itinerary=[s for s in stores if s["category"]!="服务台"][:1]
        route=build_route(mall_id,[s["id"] for s in itinerary])
    history=["IDLE","UNDERSTAND","COLLECT","PLAN"]
    history.append("ROUTE"); history.append("CONFIRM")
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
            itinerary_ids=[store["id"] for store in itinerary]
            marks=','.join('?' for _ in itinerary_ids)
            if action=="claim_coupon":
                coupon=db.execute(f"SELECT id FROM coupons WHERE mall_id=? AND store_id IN ({marks}) AND stock>0 ORDER BY id LIMIT 1",(mall,*itinerary_ids)).fetchone() if itinerary_ids else None
                if coupon: results.append(_claim(db,user_id,mall,coupon["id"]))
                else: results.append({"tool":"claim_coupon","status":"unavailable","reason":"方案店铺暂无可领优惠券"})
            elif action=="buy_ticket":
                product_row=db.execute(f"SELECT * FROM ticket_products WHERE mall_id=? AND store_id IN ({marks}) AND stock>0 ORDER BY id LIMIT 1",(mall,*itinerary_ids)).fetchone() if itinerary_ids else None
                if product_row:
                    product=product_row["id"]; qty=slots.get("people",1); tid="ut_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO user_tickets VALUES(?,?,?,?,?,?)",(tid,product,user_id,mall,qty,now_iso())); db.execute("UPDATE ticket_products SET stock=stock-? WHERE id=?",(qty,product)); results.append({"tool":"buy_ticket","status":"success","ticket_id":tid,"store_id":product_row["store_id"],"quantity":qty})
                else: results.append({"tool":"buy_ticket","status":"unavailable","reason":"当前方案不含可购票项目"})
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
        slots=json.loads(row["slots_json"]); slots.update({k:v for k,v in (modifications or {}).items() if k not in {"strategy","vertical_mode"}}); itinerary=json.loads(row["itinerary_json"]); old_route=json.loads(row["route_json"])
        selected_strategy=(modifications or {}).get("strategy")
        vertical_mode=(modifications or {}).get("vertical_mode")
        alternatives=old_route.get("alternatives") or []
        selected=next((item for item in alternatives if item.get("strategy")==selected_strategy),None)
        if vertical_mode in {"elevator","escalator"}:
            route=build_route(row["mall_id"],[item["id"] for item in itinerary],vertical_mode=vertical_mode)
            strategy=old_route.get("selected_strategy","fastest"); metrics=_plan_metrics(itinerary,route,slots,strategy)
            route["selected_strategy"]=strategy; route["optimization"]=metrics; route["alternatives"]=alternatives
        elif selected:
            itinerary=selected["itinerary"]
            preferred_mode=old_route.get("vertical_mode","elevator")
            route=build_route(row["mall_id"],[item["id"] for item in itinerary],vertical_mode=preferred_mode)
            metrics=_plan_metrics(itinerary,route,slots,selected_strategy)
            route["selected_strategy"]=selected_strategy; route["optimization"]=metrics; route["alternatives"]=alternatives
        elif modifications.get("cheaper") and itinerary:
            itinerary=sorted(itinerary,key=lambda item:item["avg_price"])
            route=build_route(row["mall_id"],[item["id"] for item in itinerary])
        else: route=build_route(row["mall_id"],[item["id"] for item in itinerary])
        db.execute("UPDATE plans SET slots_json=?,state='CONFIRM',itinerary_json=?,route_json=?,updated_at=? WHERE id=?",(json.dumps(slots,ensure_ascii=False),json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),now_iso(),plan_id))
        db.execute("UPDATE sessions SET slots_json=?,plan_state='CONFIRM',updated_at=? WHERE id=?",(json.dumps(slots,ensure_ascii=False),now_iso(),row["session_id"]))
    result=get_plan(user_id,plan_id); result["state_history"]=["CONFIRM","PLAN","ROUTE","CONFIRM"]; return result

def get_plan(user_id,plan_id):
    with connection() as db: row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="plan not found")
    state=row["state"]; state_history=STATES[:STATES.index(state)+1]
    return {"plan_id":row["id"],"session_id":row["session_id"],"mall_id":row["mall_id"],"scene":row["scene"],"slots":json.loads(row["slots_json"]),"state":state,"state_history":state_history,"itinerary":json.loads(row["itinerary_json"]),"route":json.loads(row["route_json"]),"action_results":json.loads(row["action_results_json"]),"card":{"type":"itinerary" if state=="DONE" else "plan","status":state}}
