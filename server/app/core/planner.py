import itertools, json, math, re, uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app.core.metrics import metrics
from app.core.router import build_route
from app.core.tools import live_store_status
from app.core.activity_semantics import classify_activity, decorate_location, is_full_day, period_for_minutes, planning_pois, semantic_errors, semantic_schedule
from app.db import connection, now_iso

STATES=["IDLE","UNDERSTAND","COLLECT","PLAN","ROUTE","CONFIRM","EXECUTE","DONE"]
EXECUTABLE_ACTIONS={"reserve_restaurant","reserve_business_space","cancel_reservation","update_reservation","claim_coupon","buy_ticket","purchase_deal"}
TEMPLATES={
 "date":{"required":["time","people","budget_per_person","cuisine","want_movie"],"stores":["蜀签成都串串香","世界茶饮"],"actions":["reserve_restaurant","claim_coupon"]},
 "banquet":{"required":["time","people","total_budget","cuisine","private_room"],"stores":["川食公馆","金伯利"],"actions":["reserve_restaurant","claim_coupon"]},
 "gift":{"required":["recipient","budget","preferences","occasion"],"stores":["金伯利","大众书局","阅江轩"],"actions":["claim_coupon"]},
 "family_day":{"required":["child_age","duration","budget","interests","meal_preference"],"stores":["格瑞特运动馆","拼桌茶餐厅","满记甜品"],"actions":["buy_ticket","reserve_restaurant","claim_coupon"]},
 "business":{"required":["time","people","total_budget","level","quiet","meal_preference"],"stores":["星巴克","川食公馆"],"actions":["reserve_restaurant","claim_coupon"]},
 "casual":{"required":[],"stores":["途尚咖啡","大众书局"],"actions":[]}}
# 场景默认槽位：用户只说出「目标」(如「帮我规划约会」)但没给明细时，用默认值直接生成方案，避免空方案
DEFAULT_SLOTS={
 "date":{"time":"今晚7点","people":2,"budget_per_person":200,"cuisine":"川菜","want_movie":False},
 "banquet":{"time":"周末6点","people":6,"total_budget":1000,"cuisine":"川菜","private_room":True},
 "gift":{"recipient":"朋友","budget":300,"preferences":"设计感小物","occasion":"礼物"},
 "family_day":{"child_age":6,"duration":4,"budget":500,"interests":"游乐","meal_preference":"亲子餐"},
 "business":{"time":"明天下午3点","people":4,"total_budget":1500,"level":"高端","quiet":True,"meal_preference":"中餐"}}
DEFAULT_SLOTS["casual"]={"time":"今天18点","people":1,"budget":300}

def _merged_session_context(session_id, additions):
    with connection() as db: row=db.execute("SELECT context_json FROM sessions WHERE id=?",(session_id,)).fetchone()
    try: current=json.loads(row["context_json"]) if row else {}
    except Exception: current={}
    current.update(additions)
    return current

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
    if any(word in text for word in ("全天","一整天","一天","从早到晚")): slots.update({"full_day":True,"duration":max(8,int(slots.get("duration") or 0))})
    return {k:v for k,v in slots.items() if v is not None}

def create_plan(user_id,mall_id,session_id,text,scene=None,slots=None,proposal=None,source="state_machine"):
    scene=scene or detect_scene(text)
    if scene not in TEMPLATES: scene = detect_scene(text) or 'date'
    merged=extract_slots(scene,text); merged.update(slots or {})
    missing_original=[s for s in TEMPLATES[scene]["required"] if s not in merged]
    session_context=_merged_session_context(session_id,{"planner_source":source})
    missing=missing_original
    # 缺槽位 → 用场景默认槽位补全，使「只说目标」也能直接生成方案
    if missing:
        merged.update({k:v for k,v in DEFAULT_SLOTS[scene].items() if k not in merged})
        missing=[s for s in TEMPLATES[scene]["required"] if s not in merged]
        if missing: state="COLLECT"; itinerary=[]; route={}; history=["IDLE","UNDERSTAND","COLLECT"]; plan_id="plan_"+uuid.uuid4().hex[:12]; now=now_iso()
        else: plan_id,itinerary,route,state,history=_build_itinerary(user_id,mall_id,scene,merged,proposal)
    else:
        plan_id,itinerary,route,state,history=_build_itinerary(user_id,mall_id,scene,merged,proposal)
    if state=="COLLECT":
        now=now_iso()
        with connection() as db:
            session_context.update({"state_history":history,"missing_slots":missing_original})
            db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),plan_id,state,json.dumps(session_context,ensure_ascii=False),now))
            db.execute("INSERT INTO plans(id,session_id,user_id,mall_id,scene,slots_json,state,itinerary_json,route_json,action_results_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(plan_id,session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),state,json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),"[]",now,now))
        return {"plan_id":plan_id,"revision":1,"session_id":session_id,"scene":scene,"slots":merged,"missing_slots":missing_original,"state":state,"state_history":history,"itinerary":itinerary,"route":route,"card":{"type":"plan","title":f"{scene} 方案","status":state}}
    now=now_iso()
    with connection() as db:
        session_context.update({"state_history":history,"missing_slots":missing_original})
        db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),plan_id,state,json.dumps(session_context,ensure_ascii=False),now))
        db.execute("INSERT INTO plans(id,session_id,user_id,mall_id,scene,slots_json,state,itinerary_json,route_json,action_results_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(plan_id,session_id,user_id,mall_id,scene,json.dumps(merged,ensure_ascii=False),state,json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),"[]",now,now))
    return {"plan_id":plan_id,"revision":1,"session_id":session_id,"scene":scene,"slots":merged,"missing_slots":missing_original,"state":state,"state_history":history,"itinerary":itinerary,"route":route,"card":{"type":"plan","title":f"{scene} 方案","status":state}}

PLAN_KEYWORDS=['规划','方案','路线','行程','安排','休闲','娱乐','甜点','甜品','想吃','想喝','想买','逛逛','逛街','去逛','去玩','走走','玩玩','放松','休息','遛','怎么玩','散心','电影','影片','购物','买东西','买点','去哪','去哪里','吃什','喝什','带娃','带小孩','周末','一天','半日','有啥','推荐一下','陪','早餐','午餐','晚餐','夜宵','下午茶','西餐','中餐','日料','火锅','韩餐','补充','加上','添加','加入','还想','还要','再加','删掉','删除','去掉','不要','替换','换成','放第一','放最前','放最后','更新','修改','改成','调整','顺便','顺道','晚上','下午','中午','少走路','别绕路','路程近','用时短','快一点','少排队','不想排队','人均','预算']
def is_plan_request(text):
    t=text or ''
    return any(k in t for k in PLAN_KEYWORDS)
QUERY_WORDS=['停车','积分','特惠','优惠','优惠券','折扣','营业','几点开门','几点关门','几点闭店','营业时间','闭店','电话','地址','在哪','哪里','哪层','怎么走','wifi','充电','寄存','会员','发票','兑换','充值','售后','服务台','卫生间','无障碍','婴儿','母婴','导航','导览','路线图','有哪','哪些店','搜索','查询','还剩','余额']
def is_plain_query(text):
    t=text or ''
    return any(w in t for w in QUERY_WORDS)
SCENE_NAMES={"date":"约会","banquet":"家宴","gift":"礼物","family_day":"带娃","business":"商务","casual":"休闲","leisure":"休闲"}

def _seq_times(n, seed=""):
    """按顺序生成每站的时间点（大模型没给具体时间时兜底）。"""
    from datetime import datetime, timedelta
    base=None
    m=re.search(r"(\d{1,2})(?::|点)(\d{2})?", seed or "")
    if m:
        hh=int(m.group(1)); mm=int(m.group(2) or 0)
        if ("下午" in seed or "晚" in seed) and hh<12: hh+=12
        base=datetime(2000,1,1,hh,mm)
    else:
        base=datetime(2000,1,1,18,0)
    return [(base+timedelta(minutes=idx*45)).strftime("%H:%M") for idx in range(n)]

def _time_minutes(label):
    match=re.search(r"(\d{1,2})(?::|点)(\d{1,2})?",label or "")
    if not match:return None
    hour=int(match.group(1));minute=int(match.group(2) or 0)
    if any(word in (label or "") for word in ("下午","晚上","今晚","明晚","晚餐")) and hour<12:hour+=12
    return hour*60+minute

def _canonical_times(itinerary,time_plan,seed):
    """保证一条行程按顺序递增，模型即使给出重复时间也不会生成并行到店。"""
    defaults=_seq_times(len(itinerary),seed);previous=None;result=[]
    for index,store in enumerate(itinerary):
        label=(time_plan or {}).get(store["id"]) or defaults[index];minutes=_time_minutes(label)
        if minutes is None:minutes=(_time_minutes(defaults[index]) or 18*60)
        if previous is not None and minutes<=previous:minutes=previous+45
        result.append(f"{(minutes//60)%24:02d}:{minutes%60:02d}");previous=minutes
    return result

def _annotate_itinerary(itinerary):
    for item in itinerary:
        item["activity_role"]=classify_activity(item)
        period=period_for_minutes(_time_minutes(item.get("time_label")))
        item["day_period"]=period["key"] if period else "自由活动"
        default_duration=75 if item["activity_role"]=="正餐" else 45
        matched_period=period and item["activity_role"] in period.get("preferred_roles",[])
        item["duration_minutes"]=int((period.get("duration") if matched_period else None) or item.get("suggested_duration_minutes") or default_duration)
    return itinerary

def _scheduled_iso(label):
    match=re.search(r"(\d{1,2})(?::|点)(\d{2})?",label or "")
    if not match: return None
    now=datetime.now(timezone.utc).astimezone(); day=now.date()+(timedelta(days=1) if "明" in label else timedelta())
    hour=int(match.group(1)); minute=int(match.group(2) or 0)
    if any(word in label for word in ("下午","晚上","今晚","明晚")) and hour<12: hour+=12
    return datetime.combine(day,datetime.min.time(),tzinfo=now.tzinfo).replace(hour=hour,minute=minute).astimezone(timezone.utc).isoformat()

def create_plan_from_agent(user_id,mall_id,session_id,text,scene,plan_data,reply=""):
    """Compatibility wrapper: online suggestions enter the one canonical state machine."""
    selected=scene if scene in TEMPLATES else (plan_data.get("scene") or detect_scene(text) or "casual")
    slots=dict(DEFAULT_SLOTS.get(selected,{})); slots.update(plan_data.get("slots") or {})
    return create_plan(user_id,mall_id,session_id,text,selected,slots,proposal=plan_data,source="online_agent")

# 场景规则：scenes 按槽位动态挑店（category / tags / avg_price 匹配），体现用户偏好
SCENE_PICKS = {
  "date":     [("drink", ["奶茶","咖啡","烘焙","甜品","茶歇"]), ("movie", ["影院"])],
  "banquet":  [("restaurant", ["川菜","粤菜","高端餐厅"]), ("gift", ["礼品"])],
  "gift":     [("gift", ["礼品","香氛","设计零售","玩具"])],
  "family_day": [("kid", ["儿童乐园","亲子餐厅","玩具"]), ("restaurant", ["亲子餐厅"]), ("drink", ["甜品","奶茶","烘焙"])],
  "business": [("biz", ["高端餐厅","商务空间","茶歇","轻食"])],
  "casual": [("browse", ["零售","饮品甜品","咖啡","甜品","礼品","设计零售"])],
}

STRATEGY_LABELS={"fastest":"用时最短","shortest":"路程最近、回头路最少"}
OPTIMIZATION_WEIGHTS={
  "fastest":{"wait_minute":1.0,"walk_minute":1.0,"floor_transfer":2.0,"budget_overage":0.03},
  "shortest":{"distance":1.0,"backtrack_distance":2.0,"floor_transfer":25.0,"wait_minute":0.0},
}

def _live_stores(mall_id):
    with connection() as db: rows=db.execute("SELECT s.*,sd.details_json FROM stores s LEFT JOIN store_details sd ON sd.store_id=s.id WHERE s.mall_id=?",(mall_id,)).fetchall()
    stores=[]
    for row in rows:
        item=dict(row); details=json.loads(item.pop("details_json") or "{}"); item.update({key:value for key,value in details.items() if key not in item or item[key] in (None,"")}); stores.append(decorate_location(item))
    status={item["store_id"]:item for item in live_store_status(mall_id=mall_id,store_ids=[s["id"] for s in stores])}
    for item in stores:
        live=status.get(item["id"])
        if live: item.update({"open_status":live["open_status"],"queue_minutes":live["queue_minutes"],"seats_available":live["seats_available"]})
    return stores

def _plan_locations(mall_id):
    return _live_stores(mall_id)+planning_pois(mall_id)

def _resolve_locations(mall_id,location_ids):
    by={item["id"]:item for item in _plan_locations(mall_id)}
    return [dict(by[item]) for item in location_ids if item in by]

def _category(stores,names):
    return [s for s in stores if (s["category"] in names or any(name in (s.get("tags") or "") for name in names)) and s["category"]!="服务台" and s["open_status"]!="closed"]

def _candidate_groups(scene,stores,slots):
    cuisine=slots.get("cuisine") or slots.get("meal_preference")
    restaurants=_match_cuisine(stores,cuisine)
    restaurants=[s for s in restaurants if s["open_status"]!="closed" and s["category"]!="服务台"] or _category(stores,["餐饮","川菜","粤菜","日料","西餐","高端餐厅","亲子餐厅","轻食"])
    if scene=="date":
        per_person=float(slots.get("budget_per_person") or 0); affordable=[s for s in restaurants if not per_person or float(s.get("avg_price") or 0)<=per_person]
        if is_full_day(slots):
            by_role=lambda role:[s for s in stores if classify_activity(s)==role and s.get("open_status")!="closed"]
            varied=by_role("文化")+by_role("运动")+by_role("购物")+by_role("亲子")
            scenic=by_role("公共景观")+by_role("休息")
            return [by_role("饮品甜品"),affordable or restaurants,varied,by_role("饮品甜品"),affordable or restaurants,scenic]
        groups=[affordable or restaurants,_category(stores,["饮品甜品","奶茶","咖啡","烘焙","甜品","茶歇"])]
        if slots.get("want_movie",False): groups.append(_category(stores,["影院"]))
        return groups
    if scene=="banquet": return [restaurants,_category(stores,["礼品","零售"])]
    if scene=="gift": return [_category(stores,["礼品","香氛","设计零售","玩具","零售"])]
    if scene=="family_day": return [_category(stores,["儿童乐园","玩具","亲子","运动","书店"]),_category(stores,["亲子餐厅","餐饮"]),_category(stores,["饮品甜品","甜品","奶茶","烘焙"])]
    if scene=="business": return [_category(stores,["商务空间","咖啡","办公"]),_category(stores,["茶歇","咖啡","轻食","饮品甜品"]),_category(stores,["高端餐厅","粤菜","川菜","餐饮"])]
    if scene=="casual": return [_category(stores,["零售","饮品甜品","咖啡","甜品","礼品","设计零售"])]
    return []

def _backtrack_distance(route):
    seen=set(); repeated=0.0
    for a,b in zip(route.get("nodes",[]),route.get("nodes",[])[1:]):
        edge=tuple(sorted((a["node_id"],b["node_id"]))); distance=math.dist((a["x"],a["y"]),(b["x"],b["y"])) if a["floor"]==b["floor"] else 0
        if edge in seen: repeated+=distance
        seen.add(edge)
    return round(repeated,1)

def _plan_metrics(itinerary,route,slots,strategy):
    waiting=sum(int(s.get("queue_minutes") or 0) for s in itinerary); distance=float(route.get("estimated_distance") or 0); walking=round(distance/75,1)
    activity=sum(int(s.get("duration_minutes") or s.get("suggested_duration_minutes") or (75 if classify_activity(s)=="正餐" else 45)) for s in itinerary)
    transfers=sum(1 for segment in route.get("polyline_segments",[]) if segment.get("transfer_instruction")); backtrack=_backtrack_distance(route)
    budget=sum(float(s.get("avg_price") or 0) for s in itinerary); target=float(slots.get("budget_per_person") or slots.get("budget") or slots.get("total_budget") or budget or 0)
    weights=OPTIMIZATION_WEIGHTS[strategy]
    score=(waiting+walking+transfers*2+max(0,budget-target)*weights.get("budget_overage",0)) if strategy=="fastest" else distance+backtrack*2+transfers*25
    return {"strategy":strategy,"label":STRATEGY_LABELS[strategy],"score":round(score,2),"estimated_wait_minutes":waiting,"estimated_walk_minutes":walking,"estimated_activity_minutes":activity,"estimated_total_minutes":round(activity+waiting+walking+transfers*2,1),"estimated_distance":round(distance,1),"backtrack_distance":backtrack,"transfer_count":transfers,"estimated_spend_per_person":round(budget,1),"weights":weights}

def _optimized_option(mall_id,groups,slots,strategy,exclude_ids=None):
    cap=2 if len(groups)>4 else 12
    valid=[group[:cap] for group in groups if group]
    if not valid: return None
    candidates=[]
    for combo in itertools.product(*valid):
        if len({s["id"] for s in combo})!=len(combo): continue
        if exclude_ids and tuple(s["id"] for s in combo)==tuple(exclude_ids): continue
        itinerary=[dict(s) for s in combo]; route=build_route(mall_id,[s["id"] for s in itinerary],vertical_mode="elevator"); metrics=_plan_metrics(itinerary,route,slots,strategy)
        candidates.append((metrics["score"],tuple(s["id"] for s in itinerary),itinerary,route,metrics))
    if not candidates: return None
    _,_,itinerary,route,metrics=min(candidates,key=lambda item:(item[0],item[1])); times=semantic_schedule(itinerary,slots) or _seq_times(len(itinerary),slots.get("time",""))
    for index,store in enumerate(itinerary):
        store["time_label"]=times[index]; store["planned_wait_minutes"]=int(store.get("queue_minutes") or 0); store["activity_role"]=classify_activity(store)
    _annotate_itinerary(itinerary)
    route["optimization"]=metrics
    return {"strategy":strategy,"label":STRATEGY_LABELS[strategy],"itinerary":itinerary,"route":route,"metrics":metrics}

def _optimized_alternatives(mall_id,scene,slots):
    stores=_plan_locations(mall_id) if is_full_day(slots) else _live_stores(mall_id); groups=_candidate_groups(scene,stores,slots)
    fastest=_optimized_option(mall_id,groups,slots,"fastest")
    shortest=_optimized_option(mall_id,groups,slots,"shortest",[s["id"] for s in fastest["itinerary"]] if fastest else None) or _optimized_option(mall_id,groups,slots,"shortest")
    return [option for option in (fastest,shortest) if option]

def _route_bundle(alternatives,selected_strategy="fastest"):
    selected=next((item for item in alternatives if item["strategy"]==selected_strategy),alternatives[0]); route=dict(selected["route"])
    route["selected_strategy"]=selected["strategy"]; route["optimization"]=selected["metrics"]
    route["alternatives"]=[{"strategy":item["strategy"],"label":item["label"],"itinerary":item["itinerary"],"route":item["route"],"metrics":item["metrics"]} for item in alternatives]
    return route

def _match_cuisine(stores, cuisine):
    if not cuisine: return []
    c = cuisine.strip()
    # 直接按 category 含口味 或 tags 含
    hit = [s for s in stores if c in s["category"] or c in s["tags"]]
    return hit

def _build_itinerary(user_id, mall_id, scene, slots, proposal=None):
    # An online proposal only supplies candidates/times; this canonical state
    # machine still validates ids, builds corridor routes and persists the plan.
    selected_strategy=(proposal or {}).get("strategy") if (proposal or {}).get("strategy") in OPTIMIZATION_WEIGHTS else "fastest"
    proposed_ids=[item for item in ((proposal or {}).get("store_ids") or []) if isinstance(item,str)]
    itinerary=[]; route={}
    if proposed_ids:
        itinerary=_resolve_locations(mall_id,proposed_ids)
        if len(itinerary)==len(proposed_ids):
            time_plan=(proposal or {}).get("time_plan") or {};times=semantic_schedule(itinerary,slots,time_plan=time_plan) or _canonical_times(itinerary,time_plan,slots.get("time",""))
            for index,store in enumerate(itinerary):store["time_label"]=times[index];store["activity_role"]=classify_activity(store)
            _annotate_itinerary(itinerary)
            if semantic_errors(itinerary,slots):itinerary=[]
        if itinerary:
            base_route=build_route(mall_id,[store["id"] for store in itinerary]); metrics=_plan_metrics(itinerary,base_route,slots,selected_strategy)
            route=dict(base_route); route.update({"selected_strategy":selected_strategy,"optimization":metrics,"semantic_validation":{"valid":True,"errors":[]},"alternatives":[{"strategy":selected_strategy,"label":STRATEGY_LABELS[selected_strategy],"itinerary":itinerary,"route":base_route,"metrics":metrics}]})
    if not itinerary:
        alternatives=_optimized_alternatives(mall_id,scene,slots)
        if alternatives:
            selected=next((item for item in alternatives if item["strategy"]==selected_strategy),alternatives[0]); itinerary=selected["itinerary"]; route=_route_bundle(alternatives,selected["strategy"])
        else:
            stores=_plan_locations(mall_id); itinerary=[s for s in stores if s["category"]!="服务台"][:1]; route=build_route(mall_id,[s["id"] for s in itinerary])
    route["semantic_validation"]={"valid":not semantic_errors(itinerary,slots),"errors":semantic_errors(itinerary,slots)}
    return "plan_"+uuid.uuid4().hex[:12], itinerary, route, "CONFIRM", ["IDLE","UNDERSTAND","COLLECT","PLAN","ROUTE","CONFIRM"]

def _claim(db,user_id,mall_id,coupon_id):
    row=db.execute("SELECT * FROM coupons WHERE id=? AND mall_id=? AND stock>0",(coupon_id,mall_id)).fetchone()
    if not row: raise HTTPException(status_code=409,detail="优惠券不存在或已领完")
    existing=db.execute("SELECT * FROM user_coupons WHERE coupon_id=? AND user_id=? AND mall_id=?",(coupon_id,user_id,mall_id)).fetchone()
    if existing: return {"tool":"claim_coupon","status":"already_claimed","coupon_id":coupon_id}
    cid="uc_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO user_coupons VALUES(?,?,?,?,?)",(cid,coupon_id,user_id,mall_id,now_iso())); db.execute("UPDATE coupons SET stock=stock-1 WHERE id=?",(coupon_id,)); return {"tool":"claim_coupon","status":"success","coupon_id":coupon_id,"user_coupon_id":cid}

def confirm_plan(user_id,plan_id,decision,expected_revision=None):
    with connection(immediate=True) as db:
        row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
        if not row: raise HTTPException(status_code=404,detail="plan not found")
        if decision not in ("confirm","确认","同意"): raise HTTPException(status_code=422,detail="only explicit confirm executes writes")
        if row["state"]=="DONE":
            metrics.increment("plan_confirm_idempotent_replay")
            return get_plan(user_id,plan_id)
        if expected_revision is not None and row["revision"]!=expected_revision:
            raise HTTPException(status_code=409,detail="plan revision conflict; reload the latest plan before confirming")
        if row["state"]!="CONFIRM": raise HTTPException(status_code=409,detail="plan is not awaiting confirmation")
        scene=row["scene"]; mall=row["mall_id"]; slots=json.loads(row["slots_json"]); results=[]; itinerary=json.loads(row["itinerary_json"]); route=json.loads(row["route_json"])
        selected_movie=slots.get("selected_movie")
        if selected_movie:
            movie_store=next((store for store in itinerary if store.get("category")=="影院"),None)
            if not movie_store: raise HTTPException(status_code=409,detail="selected movie requires a cinema in itinerary")
            details=db.execute("SELECT details_json FROM store_details WHERE store_id=?",(movie_store["id"],)).fetchone()
            showing=(json.loads(details["details_json"]).get("now_showing") if details else []) or []
            if showing and selected_movie not in showing: raise HTTPException(status_code=409,detail="selected movie is not showing")
        revision=db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM plan_snapshots WHERE plan_id=?",(plan_id,)).fetchone()[0]
        snapshot={"plan_id":plan_id,"revision":revision,"scene":scene,"slots":slots,"itinerary":itinerary,"route":route,"selected_movie":selected_movie}
        db.execute("INSERT INTO plan_snapshots VALUES(?,?,?,?,?)",("snap_"+uuid.uuid4().hex[:10],plan_id,revision,json.dumps(snapshot,ensure_ascii=False),now_iso()))
        db.execute("UPDATE plans SET state='EXECUTE',updated_at=? WHERE id=?",(now_iso(),plan_id))
        requested=slots.get("requested_actions")
        actions=[action for action in requested if action in EXECUTABLE_ACTIONS] if isinstance(requested,list) else TEMPLATES[scene]["actions"]
        for action in dict.fromkeys(actions):
            itinerary_ids=[store["id"] for store in itinerary]; marks=",".join("?" for _ in itinerary_ids)
            if action=="claim_coupon":
                coupons=db.execute(f"SELECT id,store_id,stock FROM coupons WHERE mall_id=? AND store_id IN ({marks}) ORDER BY stock DESC,id",(mall,*itinerary_ids)).fetchall() if itinerary_ids else []
                claimed_ids={item["coupon_id"] for item in db.execute("SELECT coupon_id FROM user_coupons WHERE user_id=? AND mall_id=?",(user_id,mall)).fetchall()}
                available=next((item for item in coupons if item["stock"]>0 and item["id"] not in claimed_ids),None)
                claimed=next((item for item in coupons if item["id"] in claimed_ids),None)
                if available:
                    results.append(_claim(db,user_id,mall,available["id"]))
                elif claimed:
                    results.append({"tool":"claim_coupon","status":"already_claimed","coupon_id":claimed["id"],"reason":"对应优惠券已经领取过"})
                elif coupons:
                    results.append({"tool":"claim_coupon","status":"unavailable","reason_code":"coupon_sold_out","reason":"方案商家的对应优惠券已领完"})
                else:
                    store_names="、".join(store.get("name","") for store in itinerary if store.get("name"))
                    results.append({"tool":"claim_coupon","status":"unavailable","reason_code":"coupon_not_published","reason":f"{store_names or '方案中的商家'}没有对应优惠券"})
            elif action=="buy_ticket":
                product_row=db.execute(f"SELECT * FROM ticket_products WHERE mall_id=? AND store_id IN ({marks}) AND stock>0 ORDER BY id LIMIT 1",(mall,*itinerary_ids)).fetchone() if itinerary_ids else None
                if product_row:
                    product=product_row["id"]; qty=slots.get("people",1); tid="ut_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO user_tickets VALUES(?,?,?,?,?,?)",(tid,product,user_id,mall,qty,now_iso())); db.execute("UPDATE ticket_products SET stock=stock-? WHERE id=?",(qty,product)); results.append({"tool":"buy_ticket","status":"success","ticket_id":tid,"store_id":product_row["store_id"],"quantity":qty,"selected_movie":selected_movie})
                else: results.append({"tool":"buy_ticket","status":"unavailable","reason":"当前方案不含可购票项目"})
            elif action=="purchase_deal":
                requested_deal=slots.get("requested_deal_id")
                deal=db.execute(f"SELECT * FROM deals WHERE mall_id=? AND store_id IN ({marks}) AND stock>0 AND (? IS NULL OR id=?) ORDER BY id LIMIT 1",(mall,*itinerary_ids,requested_deal,requested_deal)).fetchone() if itinerary_ids else None
                if deal:
                    quantity=max(1,int(slots.get("quantity") or 1));updated=db.execute("UPDATE deals SET stock=stock-? WHERE id=? AND stock>=?",(quantity,deal["id"],quantity))
                    if updated.rowcount:
                        purchase_id="dp_"+uuid.uuid4().hex[:10];db.execute("INSERT INTO deal_purchases VALUES(?,?,?,?,?,?,?,?)",(purchase_id,deal["id"],user_id,mall,quantity,deal["price"],"paid",now_iso()));results.append({"tool":"purchase_deal","status":"success","purchase_id":purchase_id,"deal_id":deal["id"],"store_id":deal["store_id"],"quantity":quantity})
                    else: results.append({"tool":"purchase_deal","status":"unavailable","reason":"特惠库存不足"})
                else: results.append({"tool":"purchase_deal","status":"unavailable","reason":"当前方案店铺没有可购买的限时特惠"})
            elif action in ("reserve_restaurant","reserve_business_space"):
                wanted="商务空间" if action=="reserve_business_space" else None; store=next((s for s in itinerary if (wanted and s["category"]==wanted) or (not wanted and s["reservable"] and s["category"]!="商务空间")),None)
                if store:
                    rid="res_"+uuid.uuid4().hex[:10]; planned=store.get("time_label") or slots.get("time","演示时段")
                    db.execute("""INSERT INTO reservations(id,user_id,mall_id,store_id,kind,reserved_for,people,notes,status,created_at,scheduled_at,duration_minutes)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,user_id,mall,store["id"],"business" if wanted else "restaurant",planned,slots.get("people",2),"由确认后的规划创建","confirmed",now_iso(),_scheduled_iso(planned),60)); results.append({"tool":action,"status":"success","reservation_id":rid,"store_id":store["id"],"reserved_for":planned})
            elif action in ("cancel_reservation","update_reservation"):
                reservation_id=slots.get("target_reservation_id")
                reservation=db.execute("SELECT * FROM reservations WHERE id=? AND user_id=? AND mall_id=?",(reservation_id,user_id,mall)).fetchone() if reservation_id else None
                if not reservation or reservation["status"]=="cancelled":
                    results.append({"tool":action,"status":"unavailable","reason":"没有找到可操作的有效预约"})
                elif action=="cancel_reservation":
                    db.execute("UPDATE reservations SET status='cancelled' WHERE id=? AND user_id=?",(reservation_id,user_id))
                    results.append({"tool":action,"status":"success","reservation_id":reservation_id,"store_id":reservation["store_id"]})
                else:
                    reserved_for=slots.get("time") or reservation["reserved_for"]; people=max(1,int(slots.get("people") or reservation["people"]))
                    db.execute("UPDATE reservations SET reserved_for=?,people=?,scheduled_at=? WHERE id=? AND user_id=?",(reserved_for,people,_scheduled_iso(reserved_for),reservation_id,user_id))
                    results.append({"tool":action,"status":"success","reservation_id":reservation_id,"store_id":reservation["store_id"],"reserved_for":reserved_for,"people":people})
        # 为方案中可预约/需排队的店批量建档，供「到号提醒」使用
        queued_ids={r["store_id"] for r in results if r.get("store_id")}
        for store in itinerary:
            sid=store.get("id")
            if not sid or sid in queued_ids: continue
            if not store.get("reservable"): continue
            q=int(store.get("queue_minutes") or 0)
            rid="res_"+uuid.uuid4().hex[:10]
            planned=store.get("time_label") or slots.get("time","演示时段")
            db.execute("""INSERT INTO reservations(id,user_id,mall_id,store_id,kind,reserved_for,people,notes,status,created_at,scheduled_at,duration_minutes)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,user_id,mall,sid,"queue",planned,slots.get("people",2),f"规划排队约{q}分钟","queued",now_iso(),_scheduled_iso(planned),60))
            results.append({"tool":"queue","status":"queued","store_id":sid,"queue_minutes":q,"reservation_id":rid})
        db.execute("UPDATE plans SET state='DONE',action_results_json=?,updated_at=?,revision=revision+1 WHERE id=?",(json.dumps(results,ensure_ascii=False),now_iso(),plan_id)); db.execute("UPDATE sessions SET plan_state='DONE',updated_at=? WHERE id=?",(now_iso(),row["session_id"]))
    metrics.increment(f"scenario_{scene}_success"); metrics.increment("tool_calls"); return get_plan(user_id,plan_id)

def revise_plan(user_id,plan_id,modifications,expected_revision=None):
    with connection(immediate=True) as db:
        row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
        if not row: raise HTTPException(status_code=404,detail="plan not found")
        if expected_revision is not None and row["revision"]!=expected_revision:
            raise HTTPException(status_code=409,detail="plan revision conflict; reload the latest plan before editing")
        if row["state"]!="CONFIRM": raise HTTPException(status_code=409,detail="only a pending plan can be modified")
        changes=modifications or {}; slots=json.loads(row["slots_json"]); slots.update({k:v for k,v in changes.items() if k not in {"strategy","vertical_mode","itinerary"}})
        itinerary=json.loads(row["itinerary_json"]); old_route=json.loads(row["route_json"]); alternatives=old_route.get("alternatives") or []
        if isinstance(changes.get("itinerary"),list):
            requested=changes["itinerary"]; ids=[item.get("id") for item in requested if isinstance(item,dict) and item.get("id")]
            if not ids: raise HTTPException(status_code=422,detail="itinerary must contain at least one store")
            by={item["id"]:item for item in _resolve_locations(row["mall_id"],ids)}
            if len(by)!=len(set(ids)): raise HTTPException(status_code=422,detail="itinerary contains an invalid store")
            itinerary=[]
            for index,item in enumerate(requested):
                store=by[item["id"]]; store["time_label"]=item.get("time_label") or _seq_times(len(requested),slots.get("time",""))[index]; itinerary.append(store)
            alternatives=[]
        selected_strategy=changes.get("strategy"); selected=next((item for item in alternatives if item.get("strategy")==selected_strategy),None)
        if selected: itinerary=selected["itinerary"]
        if changes.get("cheaper") and itinerary: itinerary=sorted(itinerary,key=lambda item:item["avg_price"])
        _annotate_itinerary(itinerary)
        vertical_mode=changes.get("vertical_mode") or old_route.get("vertical_mode","elevator")
        route=build_route(row["mall_id"],[item["id"] for item in itinerary],vertical_mode=vertical_mode)
        strategy=selected_strategy or old_route.get("selected_strategy","fastest"); metrics=_plan_metrics(itinerary,route,slots,strategy if strategy in OPTIMIZATION_WEIGHTS else "fastest")
        validation=semantic_errors(itinerary,slots)
        route.update({"selected_strategy":strategy,"optimization":metrics,"semantic_validation":{"valid":not validation,"errors":validation},"alternatives":alternatives})
        db.execute("UPDATE plans SET slots_json=?,state='CONFIRM',itinerary_json=?,route_json=?,updated_at=?,revision=revision+1 WHERE id=?",(json.dumps(slots,ensure_ascii=False),json.dumps(itinerary,ensure_ascii=False),json.dumps(route,ensure_ascii=False),now_iso(),plan_id))
        db.execute("UPDATE sessions SET slots_json=?,plan_state='CONFIRM',updated_at=? WHERE id=?",(json.dumps(slots,ensure_ascii=False),now_iso(),row["session_id"]))
    result=get_plan(user_id,plan_id); result["state_history"]=["CONFIRM","PLAN","ROUTE","CONFIRM"]; return result

def copy_plan_for_edit(user_id,mall_id,session_id,source_plan_id=None,scene=None,slots=None,itinerary=None,vertical_mode="elevator"):
    """把已执行方案或客户端保存的旧快照复制成新的 CONFIRM 草稿。

    已确认方案的事务快照保持不可变；编辑永远发生在新 plan_id 上。若演示数据库曾重建，
    客户端可提交原 itinerary，服务端仍会按当前 mall 校验 store_id 并重建真实路线。
    """
    with connection() as db:
        session=db.execute("SELECT * FROM sessions WHERE id=? AND user_id=? AND mall_id=?",(session_id,user_id,mall_id)).fetchone()
        if not session: raise HTTPException(status_code=404,detail="session not found")
        source=db.execute("SELECT * FROM plans WHERE id=? AND user_id=? AND mall_id=?",(source_plan_id,user_id,mall_id)).fetchone() if source_plan_id else None
        source_slots=json.loads(source["slots_json"]) if source else dict(slots or {})
        source_scene=source["scene"] if source else (scene or "date")
        requested=json.loads(source["itinerary_json"]) if source else list(itinerary or [])
        ids=[item.get("id") for item in requested if isinstance(item,dict) and item.get("id")]
        if not ids: raise HTTPException(status_code=422,detail="editable copy requires at least one store")
        by={item["id"]:item for item in _resolve_locations(mall_id,ids)}
        if len(by)!=len(set(ids)): raise HTTPException(status_code=422,detail="editable copy contains an invalid store")
        copied=[]; generated=_seq_times(len(requested),source_slots.get("time",""))
        for index,item in enumerate(requested):
            store=by[item["id"]]
            store["time_label"]=item.get("time_label") or generated[index]
            copied.append(store)
        _annotate_itinerary(copied)
        mode=vertical_mode or (json.loads(source["route_json"]).get("vertical_mode") if source else None) or "elevator"
        route=build_route(mall_id,ids,vertical_mode=mode)
        strategy=(json.loads(source["route_json"]).get("selected_strategy") if source else None) or "fastest"
        validation=semantic_errors(copied,source_slots)
        route.update({"selected_strategy":strategy,"optimization":_plan_metrics(copied,route,source_slots,strategy if strategy in OPTIMIZATION_WEIGHTS else "fastest"),"semantic_validation":{"valid":not validation,"errors":validation},"alternatives":[]})
        plan_id="plan_"+uuid.uuid4().hex[:12]; now=now_iso()
        db.execute("INSERT INTO plans(id,session_id,user_id,mall_id,scene,slots_json,state,itinerary_json,route_json,action_results_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(plan_id,session_id,user_id,mall_id,source_scene,json.dumps(source_slots,ensure_ascii=False),"CONFIRM",json.dumps(copied,ensure_ascii=False),json.dumps(route,ensure_ascii=False),"[]",now,now))
        db.execute("UPDATE sessions SET slots_json=?,plan_state='CONFIRM',updated_at=? WHERE id=?",(json.dumps(source_slots,ensure_ascii=False),now,session_id))
    result=get_plan(user_id,plan_id); result["copied_from_plan_id"]=source_plan_id; result["state_history"]=["PLAN","ROUTE","CONFIRM"]; return result

def get_plan(user_id,plan_id):
    with connection() as db:
        row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(plan_id,user_id)).fetchone()
        snapshot_row=db.execute("SELECT snapshot_json FROM plan_snapshots WHERE plan_id=? ORDER BY revision DESC LIMIT 1",(plan_id,)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="plan not found")
    state=row["state"]; state_history=STATES[:STATES.index(state)+1]
    return {"plan_id":row["id"],"revision":row["revision"],"session_id":row["session_id"],"mall_id":row["mall_id"],"scene":row["scene"],"slots":json.loads(row["slots_json"]),"state":state,"state_history":state_history,"itinerary":json.loads(row["itinerary_json"]),"route":json.loads(row["route_json"]),"action_results":json.loads(row["action_results_json"]),"confirmation_snapshot":json.loads(snapshot_row["snapshot_json"]) if snapshot_row else None,"card":{"type":"itinerary" if state=="DONE" else "plan","status":state}}
