import json, logging, re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.llm import LLMAdapter
from app.core.navigation import is_navigation_intent, resolve_navigation
from app.core.orchestrator import try_online, try_online_planning
from app.core.planner import detect_scene, create_plan, create_plan_from_agent, is_plain_query, is_plan_request, extract_slots
from app.core.tools import run_tool
from app.datasource.registry import registry
from app.db import connection, load_json, now_iso, rows_to_dicts
from app.core.text import plain_text
from app.core.activity_semantics import decorate_location, planning_pois
log=logging.getLogger("mall-assistant.chat")

ACTION_WORDS={
    "reserve_restaurant": ("预约", "预订", "订位", "排号"),
    "cancel_reservation": ("取消", "撤销"),
    "update_reservation": ("更改", "修改", "改期", "调整"),
    "claim_coupon": ("领券", "领取优惠券", "领优惠券"),
    "buy_ticket": ("买电影票", "购买电影票", "订电影票", "购票"),
    "purchase_deal": ("抢购", "购买特惠", "购买优惠", "下单特惠"),
}
ACTION_LABELS={"reserve_restaurant":"预约","cancel_reservation":"取消预约","update_reservation":"修改预约","claim_coupon":"领取优惠券","buy_ticket":"购买电影票","purchase_deal":"购买限时特惠"}
MOVIE_TERMS=("电影","影院","观影","电影票","购票")

def _movie_requested(text):
    return any(term in text for term in MOVIE_TERMS)

def _cinema_availability_query(text):
    return _movie_requested(text) and (
        any(word in text for word in ("有吗","有没有","是否有","哪里","在哪","哪家","几家","开业"))
        or "电影院吗" in text or "影院吗" in text
    )

def _sanitize_plan_reply(reply,allow_movie):
    """约会不默认绑定电影；仅删除模型偶发追加的影院句，不改动其余规划内容。"""
    if allow_movie or not reply: return reply
    sentences=re.split(r"(?<=[。！？!?])|\n",reply)
    kept=[sentence for sentence in sentences if sentence.strip() and not _movie_requested(sentence)]
    return "".join(kept).strip() or "已结合当前商场的真实店铺、排队与余位，为你生成了可调整的方案。"

def _knowledge_topic(text):
    """只把稳定规则与公共服务问题送进 RAG，实时事实继续查 SQLite。"""
    policy_words=("规则","怎么用","如何使用","能否","可以吗","可不可以","限制","门槛","叠加","有效期","过期","退款","返还","怎么办","怎么取消","如何取消","如何修改","流程","收费","计费","免费","减免","迟到","留位","保留多久")
    if "积分" in text and any(word in text for word in policy_words+("生日","兑换")):return "points"
    if any(word in text for word in ("会员等级","会员权益","普通会员","金卡")) and any(word in text for word in policy_words+("是什么","为什么",)):return "membership"
    if any(word in text for word in ("优惠券","代金券")) and any(word in text for word in policy_words+("怎么领取","如何领取")):return "coupon"
    if any(word in text for word in ("预约","预订","订位")) and any(word in text for word in policy_words+("改期","改人数","取消规则")):return "reservation"
    if "停车" in text and any(word in text for word in policy_words+("入场","离场","缴费","无障碍")):return "parking"
    if any(word in text for word in ("服务台","失物招领","卫生间","洗手间","厕所","母婴室","无障碍","消防","安保","急救")):return "service"
    if any(word in text for word in ("营业时间","几点开门","几点关门","跨楼层","电梯","扶梯","有线电视")):return "visitor"
    return None

def _live_knowledge_tool(topic,text):
    if topic=="points" and any(word in text for word in ("我的积分","积分余额","多少积分","现在积分")):return "query_member_points"
    if topic=="parking" and any(word in text for word in ("空位","剩余","还有位置","有位置")):return "query_parking_status"
    if topic=="coupon" and any(word in text for word in ("今天","现在","有哪些","有什么","可领","库存")):return "query_available_coupons"
    if topic=="reservation" and any(word in text for word in ("我的预约","已有预约","现在预约","预约记录")):return "query_my_reservations"
    return None

def _live_summary(tool,result):
    if tool=="query_member_points":
        return f"当前账户积分为{result['points']}，会员等级为{result['level']}。" if result else "当前账户没有查到会员积分记录。"
    if tool=="query_parking_status":return f"当前三个停车区域合计还有{result['total_free']}个空位。"
    if tool=="query_available_coupons":return f"当前共有{len(result)}张仍有库存的优惠券，其中{sum(1 for item in result if not item['claimed'])}张尚未领取。"
    if tool=="query_my_reservations":return f"当前共有{len(result)}条有效预约。"
    return ""

def _reservation_list_query(text):
    if any(word in text for word in ("取消","撤销","更改","修改","改期","调整","帮我预约","我要预约","想预约","预订","订位")):return False
    return any(word in text for word in ("我的预约","哪些预约","有什么预约","已有预约","预约记录","查询预约","查看预约"))

def _reservable_store_query(text):
    """Distinguish service capability from the current user's reservation orders."""
    if any(word in text for word in ("我的预约","预约记录","已预约","取消","修改","改期","帮我预约","我要预约","想预约")):return False
    reservation_words=("预约","预订","订位")
    capability_words=("哪些","哪家","什么店","有什么店","都有什么","可以","能","支持","开放")
    return any(word in text for word in reservation_words) and any(word in text for word in capability_words)

def _business_read_query(text):
    """Classify common read-only business questions before the generative model.

    The model may understand long-tail wording, but canonical business lists and
    balances must always be rendered from the same tool result as the UI.
    """
    list_words=("哪些","有什么","都有什么","可用","可领","还有","现在","今天","当前","多少")
    if "停车" in text and any(word in text for word in ("空位","车位","剩余","还有","多少")):return "query_parking_status"
    if "积分" in text and any(word in text for word in ("我的","余额","多少","现在","当前")):return "query_member_points"
    if any(word in text for word in ("优惠券","代金券")) and any(word in text for word in list_words):return "query_available_coupons"
    if any(word in text for word in ("特惠","优惠套餐","套餐活动")) and any(word in text for word in list_words):return "get_today_deals"
    if any(word in text for word in ("排队","等位")) and any(word in text for word in list_words+("多久","几分钟",)):return "query_queue_status"
    return None

def _store_catalog_query(text):
    if not any(word in text for word in ("哪些","有什么","都有什么","哪几家","店铺列表","商家列表")):return None
    mappings=(("餐厅","餐饮"),("餐饮","餐饮"),("吃饭","餐饮"),("甜品","甜品"),("饮品","饮品"),("零售","零售"),("服装","服装"),("美妆","美妆"),("母婴","母婴"),("影院","影院"),("电影院","影院"))
    for source,keyword in mappings:
        if source in text:return keyword
    if any(word in text for word in ("店铺","商店","商家")):return ""
    return None

def _canonical_read_reply(tool,result):
    if tool=="query_reservable_stores":
        if not result:return "当前没有开放预约服务的店铺。"
        lines=[f"当前共有{len(result)}家店铺开放预约，和预约页面显示一致："]
        lines.extend(f"{index}. {item['name']}（{item['floor']}F）" for index,item in enumerate(result,1))
        return "\n".join(lines)
    if tool=="query_parking_status":
        areas="；".join(f"{item['area']}剩余{item['free']}个" for item in result.get("areas",[]))
        return f"当前停车场合计剩余{result.get('total_free',0)}个车位。"+(f"\n{areas}。" if areas else "")
    if tool=="query_member_points":
        return f"你当前有{result['points']}积分，会员等级为{result['level']}，有效期至{result['expires_on']}。" if result else "当前没有查到你的会员积分记录。"
    if tool=="query_available_coupons":
        if not result:return "当前没有仍有库存的优惠券。"
        lines=[f"当前共有{len(result)}张仍有库存的优惠券："]
        lines.extend(f"{index}. {item['title']}（{item.get('store_name') or '全场'}，库存{item['stock']}，{'已领取' if item['claimed'] else '可领取'}）" for index,item in enumerate(result,1))
        return "\n".join(lines)
    if tool=="get_today_deals":
        if not result:return "今天暂时没有仍有库存的优惠套餐。"
        lines=[f"今天共有{len(result)}项仍有库存的优惠套餐："]
        lines.extend(f"{index}. {item['store_name']}：{item['title']}，¥{item['price']}，库存{item['stock']}" for index,item in enumerate(result,1))
        return "\n".join(lines)
    if tool=="query_queue_status":
        if not result:return "当前没有正在排队的店铺。"
        lines=[f"当前共有{len(result)}家店铺需要排队："]
        lines.extend(f"{index}. {item['name']}（{item['floor']}F），约{item['queue_minutes']}分钟" for index,item in enumerate(result,1))
        return "\n".join(lines)
    return "已完成查询。"

def _store_catalog_reply(result,keyword):
    if not result:return f"当前没有找到{keyword or '符合条件的'}店铺。"
    title=f"当前共有{len(result)}家{keyword}类店铺：" if keyword else f"当前商场共有{len(result)}家店铺："
    lines=[title]
    lines.extend(f"{index}. {item['name']}（{item['floor']}F，{'营业中' if item.get('open_status')!='closed' else '已停业'}）" for index,item in enumerate(result,1))
    return "\n".join(lines)

def _customer_facing_reply(text):
    """前端只展示业务答案，不暴露 RAG、知识库、数据库或工具等内部实现词。"""
    reply=plain_text(text or "")
    replacements=(
        ("知识库中未提供","本商城暂未提供"),("知识库未提供","本商城暂未提供"),("知识库暂未提供","本商城暂未提供"),
        ("根据知识库","根据本商城当前服务规则"),("依据知识库","依据本商城当前服务规则"),
        ("RAG 知识库","本商城服务规则"),("RAG知识库","本商城服务规则"),("知识库","本商城服务规则"),
    )
    for source,target in replacements:reply=reply.replace(source,target)
    return reply

def _remove_cinema_ids(mall_id,store_ids):
    cinemas={store.get("id") for store in registry.stores(mall_id,"") if store.get("category")=="影院"}
    return [store_id for store_id in (store_ids or []) if store_id not in cinemas]

def _explicit_action(text):
    """只有明确执行语气才能进入事务；咨询、能力询问和资产查询一律保持只读。"""
    if _knowledge_topic(text): return None
    if any(word in text for word in ("规划", "方案", "攻略", "行程", "路线", "安排")):
        return None
    question_words=("怎么","如何","哪些","什么","多少","有没有","是否","能否","可以吗","可不可以","为什么","规则","流程","记录","查询","查看")
    if any(word in text for word in question_words):return None
    if any(phrase in text for phrase in ("帮我取消","请取消","替我取消","我要取消","撤销我的","取消我在")) or re.match(r"^(?:取消|撤销).*(?:预约|预订|订位)",text):return "cancel_reservation"
    if any(phrase in text for phrase in ("帮我更改","帮我修改","请更改","请修改","替我改","我要改","把我的预约改","将我的预约改")):return "update_reservation"
    if any(phrase in text for phrase in ("帮我预约","请预约","替我预约","给我预约","我要预约","我想预约","想要预约","帮我预订","我要预订")) or re.match(r"^(?:预约|预订|订位)",text):return "reserve_restaurant"
    if any(phrase in text for phrase in ("帮我领券","帮我领取","请领取","替我领取","给我领","我要领券","我要领取")):return "claim_coupon"
    if any(phrase in text for phrase in ("帮我买电影票","帮我购买电影票","请买电影票","我要买电影票","我要购票")):return "buy_ticket"
    if any(phrase in text for phrase in ("帮我抢购","帮我购买特惠","帮我购买优惠","我要抢购","我要购买特惠","下单特惠")):return "purchase_deal"
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
    """把当前真实方案连同 ID/时间交给规划 Agent，避免它把增量修改当成重做。"""
    pid = session["plan_id"] if session and session["plan_id"] else None
    if not pid: return None
    with connection() as db:
        row = db.execute("SELECT itinerary_json FROM plans WHERE id=? AND user_id=?", (pid, session["user_id"])).fetchone()
    if not row: return None
    try:
        it = json.loads(row["itinerary_json"])
        current=[{"id":s.get("id"),"name":s.get("name"),"time":s.get("time_label"),"category":s.get("category"),"floor":s.get("floor")} for s in it if s.get("id")]
        return json.dumps({"edit_contract":"preserve_unmentioned_stops","itinerary":current},ensure_ascii=False) if current else None
    except Exception:
        return None

def _current_plan(session):
    pid=session["plan_id"] if session and session["plan_id"] else None
    if not pid: return None
    with connection() as db:
        row=db.execute("SELECT * FROM plans WHERE id=? AND user_id=?",(pid,session["user_id"])).fetchone()
    if not row:return None
    item=dict(row);item["slots"]=load_json(item.pop("slots_json"));item["itinerary"]=load_json(item.pop("itinerary_json"));item["route"]=load_json(item.pop("route_json"));return item

def _clock_hint(text):
    match=re.search(r"((?:今天|今晚|明天|明晚)?\s*(?:上午|中午|下午|晚上)?\s*\d{1,2}(?::\d{1,2}|点\d{0,2}分?))",text)
    if match:return match.group(1).replace(" ","")
    if any(word in text for word in ("晚上","晚餐","夜里")):return "晚上18:30"
    if any(word in text for word in ("中午","午餐")):return "中午12:00"
    if any(word in text for word in ("下午","下午茶")):return "下午14:00"
    if any(word in text for word in ("上午","早上","早餐")):return "上午10:00"
    return None

def _strategy_hint(text):
    if any(word in text for word in ("少走路","别绕路","路程近","距离短","回头路少")):return "shortest"
    if any(word in text for word in ("用时短","快一点","少排队","不想排队","赶时间")):return "fastest"
    return None

def _clock_minutes(value):
    match=re.search(r"(\d{1,2})(?::|点)(\d{1,2})?",value or "")
    if not match:return None
    hour=int(match.group(1));minute=int(match.group(2) or 0)
    if any(word in (value or "") for word in ("下午","晚上","今晚","晚餐","夜里")) and hour<12:hour+=12
    return hour*60+minute

def _operation_store_ids(operation,key="store_ids"):
    values=operation.get(key)
    if values is None and key=="store_ids":values=[operation.get("store_id")]
    elif values is None:values=[operation.get(key.removesuffix("s"))]
    if not isinstance(values,list):values=[values]
    return [value for value in values if isinstance(value,str) and value]

def _plan_edit_kind(text):
    """通用编辑意图分类，仅作为结构化输出校验，不负责挑店。"""
    if any(word in text for word in ("全部重做","整套重做","不要原方案","清空方案","从头规划")):return "replace_all"
    if any(word in text for word in ("替换","换掉","换成","改成另一家")):return "replace"
    if any(word in text for word in ("删除","删掉","去掉","移除","不要去")):return "remove"
    if any(word in text for word in ("增加","添加","加入","加上","再加","再安排","补充","顺便去")):return "add"
    if any(word in text for word in ("放第一","放最前","放最后","提前到","延后到","挪到","移动到","调整顺序")):return "move"
    if any(word in text for word in ("修改","调整","改为","改到","改时间","改人数","预算改")):return "update"
    return None

def _requested_count(text):
    match=re.search(r"([一二两三四五六七八九十]|\d+)\s*(?:个|家|项|站|处)",text)
    if not match:return 1
    raw=match.group(1);return max(1,min(int(raw) if raw.isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}[raw],5))

def _coerce_legacy_proposal_to_patch(current,proposal,text):
    """模型偶尔仍返回完整方案时，根据新旧差异转成 patch，禁止误覆盖旧方案。"""
    kind=_plan_edit_kind(text)
    if not current or kind in (None,"replace_all") or proposal.get("mode")=="patch":return proposal
    old_ids=[item["id"] for item in current.get("itinerary") or []];proposed=[item for item in proposal.get("store_ids") or [] if isinstance(item,str)]
    added=[item for item in proposed if item not in old_ids];removed=[item for item in old_ids if item not in proposed];operations=[]
    patch_slots=dict(proposal.get("slots") or {})
    if kind=="add":patch_slots.pop("time",None)
    if kind=="add" and (added or proposed):operations=[{"op":"add","store_ids":added or proposed,"count":_requested_count(text),"time":_clock_hint(text),"position":"chronological"}]
    elif kind=="remove" and removed:operations=[{"op":"remove","store_ids":removed}]
    elif kind=="replace" and removed and added:operations=[{"op":"replace","target_store_ids":removed,"replacement_store_ids":added}]
    elif kind=="move" and proposed and set(proposed)==set(old_ids):operations=[{"op":"reorder","store_ids":proposed}]
    elif kind=="update":operations=[{"op":"update_slots","slots":proposal.get("slots") or {}}]
    return {**proposal,"mode":"patch","slots":patch_slots,"operations":operations}

def _insert_position(ids,time_plan,operation):
    position=operation.get("position") or "chronological"
    if position in ("first","start"):return 0
    if position in ("last","end"):return len(ids)
    anchor=operation.get("anchor_store_id")
    if anchor in ids:return ids.index(anchor)+(1 if position=="after" else 0)
    requested=_clock_minutes(operation.get("time") or "")
    if requested is not None:
        for index,store_id in enumerate(ids):
            existing=_clock_minutes(time_plan.get(store_id) or "")
            if existing is not None and requested<existing:return index
    return len(ids)

def _apply_plan_operations(auth,session,text,edit_data):
    """将 LLM 的通用增量操作应用到 canonical plan；未被操作点名的内容一律保留。"""
    current=_current_plan(session);operations=edit_data.get("operations") or []
    if not current or not current.get("itinerary") or not isinstance(operations,list):return None
    locations=[decorate_location(item) for item in registry.stores(session["mall_id"],"")]+planning_pois(session["mall_id"])
    stores={item["id"]:item for item in locations};ids=[item["id"] for item in current["itinerary"]]
    time_plan={item["id"]:item.get("time_label") for item in current["itinerary"] if item.get("time_label")};changed=False
    slots=dict(current.get("slots") or {});slot_changes=edit_data.get("slots") or {}
    for key,value in slot_changes.items():
        if value is not None and slots.get(key)!=value:slots[key]=value;changed=True
    strategy=edit_data.get("strategy") or (current.get("route") or {}).get("selected_strategy") or "fastest"
    for operation in operations:
        if not isinstance(operation,dict):continue
        op=operation.get("op")
        if op=="add":
            candidates=[store_id for store_id in _operation_store_ids(operation) if store_id in stores and store_id not in ids and stores[store_id].get("open_status")!="closed"]
            count=max(1,min(int(operation.get("count") or 1),5));selected=candidates[:count]
            position=_insert_position(ids,time_plan,operation);requested=operation.get("time")
            for offset,store_id in enumerate(selected):
                ids.insert(position+offset,store_id)
                if requested:
                    minutes=_clock_minutes(requested);time_plan[store_id]=(f"{(minutes+offset*45)//60%24:02d}:{(minutes+offset*45)%60:02d}" if minutes is not None else requested)
                changed=True
        elif op=="remove":
            for store_id in _operation_store_ids(operation):
                if store_id in ids and len(ids)>1:ids.remove(store_id);time_plan.pop(store_id,None);changed=True
        elif op=="replace":
            targets=_operation_store_ids(operation,"target_store_ids");replacements=_operation_store_ids(operation,"replacement_store_ids") or _operation_store_ids(operation)
            for target,replacement in zip(targets,replacements):
                if target in ids and replacement in stores and replacement not in ids and stores[replacement].get("open_status")!="closed":
                    index=ids.index(target);ids[index]=replacement
                    if target in time_plan:time_plan[replacement]=time_plan.pop(target)
                    changed=True
        elif op=="move":
            targets=_operation_store_ids(operation)
            for target in targets:
                if target in ids:
                    ids.remove(target);ids.insert(_insert_position(ids,time_plan,operation),target);changed=True
        elif op=="reorder":
            requested=_operation_store_ids(operation)
            if requested and set(requested)==set(ids):ids=requested;changed=True
        elif op=="set_time":
            requested=operation.get("time");targets=_operation_store_ids(operation)
            if requested and targets:
                for target in targets:
                    if target in ids:time_plan[target]=requested;changed=True
            elif requested:
                slots["time"]=requested;changed=True
        elif op=="set_strategy" and operation.get("strategy") in ("fastest","shortest"):
            strategy=operation["strategy"];changed=True
        elif op=="update_slots":
            for key,value in (operation.get("slots") or {}).items():
                if value is not None and slots.get(key)!=value:slots[key]=value;changed=True
    if not changed or not ids:return None
    proposal={"store_ids":ids,"time_plan":time_plan,"strategy":strategy,"reason_by_store":edit_data.get("reason_by_store") or {}}
    return create_plan(auth.user_id,session["mall_id"],session["id"],text,current.get("scene") or "casual",slots,proposal,source="llm_plan_patch")

def _canonical_plan_reply(plan,user_text,reason_by_store=None,changed=False):
    """只描述后端已校验并持久化的方案，杜绝模型文案和执行卡片分叉。"""
    itinerary=plan.get("itinerary") or []; slots=plan.get("slots") or {}; route=plan.get("route") or {}; reasons=reason_by_store or {}
    scene_labels={"date":"约会","banquet":"家宴","gift":"礼物","family_day":"亲子","business":"商务","casual":"休闲"}
    intro=("明白，我已保留未被你点名修改的内容，并按要求更新方案、检查时间冲突和重算路线。" if changed else f"明白，我已为你生成{scene_labels.get(plan.get('scene'),'本次')}方案。")
    lines=[intro,"下面文字、方案卡片和地图路线来自同一份已校验结果："]
    for index,store in enumerate(itinerary,1):
        time=store.get("time_label") or f"第{index}站"; queue=int(store.get("queue_minutes") or 0); seats=store.get("seats_available")
        status="免排队" if queue<=0 else f"预计排队{queue}分钟"
        if seats is not None:status+=f"，余位{seats}"
        reason=plain_text(reasons.get(store.get("id"),""))
        extra=f"；{reason}" if reason else ""
        role=store.get("activity_role") or store.get("category");duration=store.get("duration_minutes")
        stay=f"，建议停留约{duration}分钟" if duration else ""
        lines.append(f"{index}. {time} 到 {store.get('name')}（{store.get('floor')}F · {role}），{status}{stay}{extra}")
    metrics=(route.get("optimization") or {})
    if metrics:
        lines.append(f"预计总用时{metrics.get('estimated_total_minutes',0)}分钟，步行距离{metrics.get('estimated_distance',0)}米，等待约{metrics.get('estimated_wait_minutes',0)}分钟。")
    if slots.get("people"):lines.append(f"当前按{slots['people']}人安排；确认前仍可继续改时间、人数、顺序或地点。")
    lines.append("你可以直接说“加上某店”“删掉某店”“把某店放第一站”或“改成晚上7点开始”。")
    return "\n".join(lines)

def _named_plan_adjustment(auth,session,text):
    """对常见增删、替换、排序和时间指令做确定性落地；复杂偏好仍交给在线规划 Agent。"""
    current=_current_plan(session)
    if not current or not current.get("itinerary"):return None
    all_stores=registry.stores(session["mall_id"],""); mentioned=[store for store in all_stores if store.get("name") and store["name"] in text]
    ids=[store["id"] for store in current["itinerary"]]; by_name={store["name"]:store for store in all_stores}; changed=False
    replace=re.search(r"(?:把|将)?(.+?)(?:换成|替换成|改成)(.+?)(?:店|作为|，|。|$)",text)
    if replace:
        old=next((name for name in by_name if name in replace.group(1)),None);new=next((name for name in by_name if name in replace.group(2)),None)
        if old and new and by_name[old]["id"] in ids:
            ids[ids.index(by_name[old]["id"])]=by_name[new]["id"];changed=True
    for store in mentioned:
        name=store["name"]
        if any(pattern in text for pattern in (f"删掉{name}",f"删除{name}",f"去掉{name}",f"不要{name}")) and store["id"] in ids:
            ids.remove(store["id"]);changed=True
        elif any(pattern in text for pattern in (f"加上{name}",f"添加{name}",f"加入{name}",f"再加{name}")) and store["id"] not in ids:
            ids.append(store["id"]);changed=True
        if store["id"] in ids and any(pattern in text for pattern in (f"把{name}放第一",f"把{name}放最前",f"{name}先去")):
            ids.remove(store["id"]);ids.insert(0,store["id"]);changed=True
        elif store["id"] in ids and any(pattern in text for pattern in (f"把{name}放最后",f"{name}最后去")):
            ids.remove(store["id"]);ids.append(store["id"]);changed=True
    generic_replan=any(word in text for word in ("换一版","换一下方案","换个方案","重新规划","重新推荐"))
    if generic_replan and not mentioned:return None
    slots=dict(current.get("slots") or {}); parsed=extract_slots(current.get("scene") or "casual",text); hint=_clock_hint(text)
    if parsed:slots.update(parsed);changed=True
    if hint and hint!=slots.get("time"):slots["time"]=hint;changed=True
    if not changed or not ids:return None
    proposal={"store_ids":ids,"strategy":_strategy_hint(text) or (current.get("route") or {}).get("selected_strategy") or "fastest"};plan=create_plan(auth.user_id,session["mall_id"],session["id"],text,current.get("scene") or "casual",slots,proposal,source="conversation_edit")
    return plan

def _compare_recent_plans(user_id,session_id):
    with connection() as db:rows=db.execute("SELECT * FROM plans WHERE user_id=? AND session_id=? ORDER BY created_at DESC LIMIT 2",(user_id,session_id)).fetchall()
    if len(rows)<2:return None
    blocks=[]
    for index,row in enumerate(reversed(rows),1):
        itinerary=load_json(row["itinerary_json"]);route=load_json(row["route_json"]);metrics=route.get("optimization") or {}
        blocks.append(f"方案{index}："+" → ".join(f"{item.get('time_label','')} {item.get('name','')}" for item in itinerary)+f"；预计{metrics.get('estimated_total_minutes',0)}分钟，距离{metrics.get('estimated_distance',0)}米。")
    return "我把最近两套真实方案并列好了，以下内容直接来自已生成方案：\n"+"\n".join(blocks)+"\n如果你说“选方案1/2”或指出要保留、替换哪一站，我可以继续调整。"

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
        payload["reply"]=_customer_facing_reply(payload.get("reply") or "")
        _remember(body.session_id,text,payload["reply"])
        return envelope(payload)
    if _cinema_availability_query(text):
        cinemas=[store for store in registry.stores(session["mall_id"],"") if store.get("category")=="影院"]
        if not cinemas:
            return done({"reply":"本商城暂时无电影院设施，即将开业敬请期待。","intent":"cinema_unavailable","result":[],"cards":[],"degraded":False,"source":"private_store_database"})
        return done({"reply":f"本商城现有{len(cinemas)}家影院："+"、".join(store["name"] for store in cinemas)+"。","intent":"cinema_available","result":cinemas,"cards":[{"type":"stores","data":cinemas}],"degraded":False,"source":"private_store_database"})
    if is_navigation_intent(text):
        session_context=load_json(session["context_json"]); navigation=resolve_navigation(session["mall_id"],text,session_context.get("entry_node"))
        destination=navigation["destination_store"]
        return done({"reply":f"已为你找到前往{destination['name']}的路线，路线动画已打开。当前预计排队 {destination['queue_minutes']} 分钟。","intent":"navigation","navigation":navigation,"cards":[navigation],"degraded":False})
    if any(word in text for word in ("两个方案","两套方案","前两个方案")) and any(word in text for word in ("放在一起","对比","比较","并列")):
        comparison=_compare_recent_plans(auth.user_id,body.session_id)
        if comparison:return done({"reply":comparison,"intent":"compare_plans","cards":[],"degraded":False,"source":"validated_plan_history"})
    if _reservation_list_query(text):
        result=run_tool("query_my_reservations",context,{})
        if result:
            lines=["你当前的有效预约如下："]
            lines.extend(f"{index}. {item['store_name']}，{item['reserved_for']}，{item['people']}人。" for index,item in enumerate(result,1))
            reply="\n".join(lines)
        else:
            reply="你当前没有有效预约。"
        return done({"reply":reply,"intent":"query_my_reservations","tool_calls":[{"name":"query_my_reservations","arguments":{}}],"result":result,"cards":[],"degraded":False,"source":"private_reservation_database"})
    if _reservable_store_query(text):
        result=run_tool("query_reservable_stores",context,{})
        return done({"reply":_canonical_read_reply("query_reservable_stores",result),"intent":"query_reservable_stores","tool_calls":[{"name":"query_reservable_stores","arguments":{}}],"result":result,"cards":[{"type":"stores","data":result}],"degraded":False,"source":"canonical_business_data"})
    read_tool=None if _knowledge_topic(text) else _business_read_query(text)
    if read_tool:
        result=run_tool(read_tool,context,{})
        card={"query_parking_status":"parking","query_member_points":"member","query_available_coupons":"coupons","get_today_deals":"deals","query_queue_status":"queue"}[read_tool]
        return done({"reply":_canonical_read_reply(read_tool,result),"intent":read_tool,"tool_calls":[{"name":read_tool,"arguments":{}}],"result":result,"cards":[{"type":card,"data":result}],"degraded":False,"source":"canonical_business_data"})
    store_keyword=_store_catalog_query(text)
    if store_keyword is not None:
        args={"keyword":store_keyword}; result=run_tool("search_stores",context,args)
        return done({"reply":_store_catalog_reply(result,store_keyword),"intent":"search_stores","tool_calls":[{"name":"search_stores","arguments":args}],"result":result,"cards":[{"type":"stores","data":result}],"degraded":False,"source":"canonical_business_data"})
    action=_explicit_action(text)
    if action:
        matches=_mentioned_stores(session["mall_id"],text,action)
        if action=="buy_ticket": matches=[store for store in matches if store.get("category")=="影院"]
        if not matches:
            if action=="buy_ticket":
                return done({"reply":"本商城暂时无电影院设施，即将开业敬请期待。","intent":"movie_ticket_unavailable","result":[],"cards":[],"degraded":False,"source":"transaction_router"})
            return done({"reply":f"我识别到你要{ACTION_LABELS[action]}，但当前商场没有找到对应店铺。请只补充店名，我会接着处理。","intent":"action_store_missing","result":[],"cards":[{"type":"stores","data":[]}],"degraded":False,"source":"transaction_router"})
        store=matches[0]
        people=re.search(r"(\d+|[一二两三四五六七八九十])\s*(?:位|个人|人)",text)
        people_value=None
        if people:
            raw=people.group(1); people_value=int(raw) if raw.isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}[raw]
        time_match=re.search(r"((?:今天|今晚|明天|明晚)?\s*(?:下午|晚上)?\s*\d{1,2}(?::\d{2}|点\d{0,2}分?))",text)
        time_value=time_match.group(1).replace(" ","") if time_match else None
        if action in ("cancel_reservation","update_reservation"):
            with connection() as db:
                reservation=db.execute("""SELECT * FROM reservations WHERE user_id=? AND mall_id=? AND store_id=? AND status!='cancelled'
                  ORDER BY created_at DESC LIMIT 1""",(auth.user_id,session["mall_id"],store["id"])).fetchone()
            if not reservation:
                return done({"reply":f"没有找到你在{store['name']}的有效预约，因此无法{ACTION_LABELS[action]}。","intent":"reservation_not_found","result":[],"cards":[],"degraded":False,"source":"transaction_router"})
            if action=="update_reservation" and people_value is None and time_value is None:
                return done({"reply":f"已找到你在{store['name']}的预约。请告诉我要改成几点、几个人，至少提供一项。","intent":"reservation_change_missing","result":[dict(reservation)],"cards":[],"degraded":False,"source":"transaction_router"})
            slots={"requested_actions":[action],"target_reservation_id":reservation["id"],"people":people_value or reservation["people"],"time":time_value or reservation["reserved_for"]}
            plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,"casual",slots,{"store_ids":[store["id"]]},source="transaction_router")
            detail=(f"改为{slots['time']}，{slots['people']}人" if action=="update_reservation" else f"取消{reservation['reserved_for']}、{reservation['people']}人的预约")
            return done({"reply":f"已找到你在{store['name']}的预约，确认后将{detail}。","intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":False,"mode":"deterministic","source":"transaction_router"})
        if action=="reserve_restaurant" and not store.get("reservable"):
            return done({"reply":f"已找到{store['name']}，但该店当前未开放预约。你可以让我查询实时排队，或换一家可预约店铺。","intent":"reservation_unavailable","result":[store],"cards":[{"type":"stores","data":[store]}],"degraded":False,"source":"transaction_router"})
        slots={"requested_actions":[action]}
        if action=="purchase_deal":
            with connection() as db:
                deals=rows_to_dicts(db.execute("SELECT id,title,stock FROM deals WHERE mall_id=? AND store_id=? AND stock>0 ORDER BY id",(session["mall_id"],store["id"])).fetchall())
            if not deals:
                return done({"reply":f"已找到{store['name']}，但该店当前没有可购买的限时特惠。你可以让我查询今日特惠。","intent":"deal_unavailable","result":[store],"cards":[{"type":"stores","data":[store]}],"degraded":False,"source":"transaction_router"})
            selected=next((deal for deal in deals if deal["title"] in text),deals[0]);slots["requested_deal_id"]=selected["id"]
        if people_value is not None: slots["people"]=people_value
        if time_value is not None: slots["time"]=time_value
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,"casual",slots,{"store_ids":[store["id"]]},source="transaction_router")
        when=plan["slots"].get("time","今天18:00"); count=plan["slots"].get("people",2)
        reply=f"已找到{store['name']}（{store['floor']}F），并生成{ACTION_LABELS[action]}确认方案：{when}，{count}人。确认后才会正式写入，时间和人数仍可调整。"
        return done({"reply":reply,"intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":False,"mode":"deterministic","source":"transaction_router"})
    current_for_replan=_current_plan(session)
    scene=detect_scene(text)
    if not scene and is_plan_request(text) and not is_plain_query(text): scene=(current_for_replan or {}).get("scene") or "casual"
    if scene:
        allow_movie=_movie_requested(text)
        existing=_plan_existing(session)
        agent=try_online_planning(text,context,scene,existing)
        if agent and (agent.get("plan_json") or agent.get("reply")):
            try:
                pd=agent.get("plan_json") or {}
                pd=_coerce_legacy_proposal_to_patch(current_for_replan,pd,text)
                if _strategy_hint(text):pd["strategy"]=_strategy_hint(text)
                if not allow_movie:
                    pd.setdefault("slots",{})["want_movie"]=False
                    pd["store_ids"]=_remove_cinema_ids(session["mall_id"],pd.get("store_ids"))
                    for operation in pd.get("operations") or []:
                        if isinstance(operation,dict) and operation.get("store_ids"):
                            operation["store_ids"]=_remove_cinema_ids(session["mall_id"],operation["store_ids"])
                    agent["reply"]=_sanitize_plan_reply(agent.get("reply",""),False)
                plan=_apply_plan_operations(auth,session,text,pd) if pd.get("mode")=="patch" or pd.get("operations") else None
                if not plan:
                    if not pd.get("store_ids"):pd["store_ids"]=_fallback_store_ids(agent)
                    plan=create_plan_from_agent(auth.user_id,session["mall_id"],body.session_id,text,scene,pd,agent.get("reply","")) if pd.get("store_ids") else None
                if plan and plan.get("itinerary"):
                    reasons=pd.get("reason_by_store") or pd.get("reasons") or {}
                    return done({"reply":_canonical_plan_reply(plan,text,reasons,changed=bool(existing)),"intent":"plan","plan":plan,"cards":[plan["card"]],"tool_calls":agent.get("tool_calls",[]),"degraded":False,"mode":"online","source":"online_agent_validated"})
            except HTTPException:
                pass
            except Exception as exc:
                log.exception("plan_from_agent_failed error_type=%s",type(exc).__name__)
        adjustment=_named_plan_adjustment(auth,session,text)
        if adjustment:
            return done({"reply":_canonical_plan_reply(adjustment,text,changed=True),"intent":"plan","plan":adjustment,"cards":[adjustment["card"]],"degraded":True,"degraded_reason":"online edit parser unavailable","mode":"deterministic_edit","source":"validated_plan"})
        fallback_slots=dict((current_for_replan or {}).get("slots") or {});fallback_slots.update(extract_slots(scene,text));hint=_clock_hint(text)
        if hint:fallback_slots["time"]=hint
        proposal={"strategy":_strategy_hint(text)} if _strategy_hint(text) else None
        plan=create_plan(auth.user_id,session["mall_id"],body.session_id,text,scene,fallback_slots or None,proposal); return done({"reply":_canonical_plan_reply(plan,text,changed=bool(existing)),"intent":"plan","plan":plan,"cards":[plan["card"]],"degraded":True,"degraded_reason":"scripted fallback"})
    code_match=re.search(r"(?:QD|MAP)-[A-Z0-9-]+",text.upper())
    if code_match:
        args={"keyword":code_match.group(0)}; result=run_tool("search_stores",context,args)
        reply=(f"店铺编码 {code_match.group(0)} 对应 {result[0]['name']}，位于 {result[0]['floor']}F，当前状态为 {result[0]['open_status']}。" if result else f"当前商场没有找到店铺编码 {code_match.group(0)}，请核对后再试。")
        return done({"reply":reply,"intent":"search_stores","tool_calls":[{"name":"search_stores","arguments":args}],"result":result,"cards":[{"type":"stores","data":result}],"degraded":False,"source":"private_store_code_tool"})
    knowledge_topic=_knowledge_topic(text)
    if knowledge_topic:
        knowledge_args={"query":text,"topic":knowledge_topic}; knowledge=run_tool("search_mall_knowledge",context,knowledge_args)
        tool_calls=[{"name":"search_mall_knowledge","arguments":knowledge_args}]; result=knowledge; reply=knowledge["answer"]
        live_tool=_live_knowledge_tool(knowledge_topic,text)
        if live_tool:
            live=run_tool(live_tool,context,{})
            tool_calls.append({"name":live_tool,"arguments":{}}); result={"knowledge":knowledge,"live":live}
            reply=f"{reply}\n{_live_summary(live_tool,live)}"
        mode=LLMAdapter().chat([])
        return done({"reply":reply,"intent":"knowledge_hybrid" if live_tool else "search_mall_knowledge","tool_calls":tool_calls,"result":result,"cards":[{"type":"rag","data":knowledge}],**mode})
    online=try_online(text,context)
    if online: return done({**online,"intent":"online_tool_loop","cards":[]})
    if "停车" in text: tool="query_parking_status"; args={}; reply="已查询星河里停车状态。"; card="parking"
    elif "积分" in text and any(w in text for w in ["过期","生日","兑换","规则"]): tool="query_points_rules"; args={"query":text}; reply="以下回答依据本商城当前积分规则。"; card="rag"
    elif "积分" in text: tool="query_member_points"; args={}; reply="已查询你的会员积分。"; card="member"
    elif "排队" in text or "等位" in text: tool="query_queue_status"; args={}; reply="以下店铺当前需要排队，已按等候时间从长到短排列。"; card="queue"
    elif "优惠" in text or "特惠" in text: tool="get_today_deals"; args={}; reply="这是今天仍有库存的特惠。"; card="deals"
    else: tool="search_stores"; args={"keyword":text}; reply="已在当前商场私有店铺库中搜索。"; card="stores"
    result=run_tool(tool,context,args); mode=LLMAdapter().chat([])
    return done({"reply":reply,"intent":tool,"tool_calls":[{"name":tool,"arguments":args}],"result":result,"cards":[{"type":card,"data":result}],**mode})
