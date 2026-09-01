from app.core.metrics import metrics
from app.core.rag import answer
from app.core.business_data import get_store, list_coupons, list_deals, list_reservations, list_stores
from app.core.activity_semantics import ACTIVITY_ROLES, decorate_location, planning_pois
from app.datasource.registry import registry
from app.db import connection, rows_to_dicts
from datetime import datetime, timezone
def _minutes_since(iso):
    try:
        dt=datetime.fromisoformat(iso); return max(0,(datetime.now(timezone.utc)-dt).total_seconds()/60)
    except Exception: return 0
def query_mall_info(*,mall_id,**_): return {"mall_id":mall_id,"name":registry.get(mall_id).name}
def query_parking_status(*,mall_id,**_):
    with connection() as db: rows=db.execute("SELECT area,total,free,updated_at FROM parking WHERE mall_id=? ORDER BY area",(mall_id,)).fetchall()
    return {"areas":rows_to_dicts(rows),"total_free":sum(r["free"] for r in rows)}
def search_stores(*,mall_id,keyword="",**_): return list_stores(mall_id,keyword)
def query_planning_locations(*,mall_id,activity_role=None,**_):
    locations=[decorate_location(item) for item in list_stores(mall_id)]+planning_pois(mall_id)
    return [item for item in locations if not activity_role or item.get("activity_role")==activity_role]
def query_reservable_stores(*,mall_id,keyword="",**_): return list_stores(mall_id,keyword,reservable_only=True)
def get_store_detail(*,mall_id,store_id,**_): return get_store(mall_id,store_id)
def query_member_points(*,mall_id,user_id,**_):
    with connection() as db: row=db.execute("SELECT points,level,expires_on FROM members WHERE mall_id=? AND user_id=?",(mall_id,user_id)).fetchone()
    return dict(row) if row else None
def search_mall_knowledge(*,mall_id,query,topic=None,**_):
    result=answer(query,mall_id,topic)
    metrics.increment("rag_hit_count" if result["sources"] else "rag_miss_count")
    return result
def query_points_rules(*,mall_id,query="积分",**_): return search_mall_knowledge(mall_id=mall_id,query=query,topic="points")
def get_today_deals(*,mall_id,**_):
    return list_deals(mall_id,available_only=True)
def query_queue_status(*,mall_id,**_):
    with connection() as db:
        rows=db.execute("""SELECT s.id,s.name,s.category,s.floor,ss.open_status,ss.queue_minutes,ss.seats_available,sp.store_code
          FROM stores s JOIN store_status ss ON ss.store_id=s.id LEFT JOIN store_profiles sp ON sp.store_id=s.id
          WHERE s.mall_id=? AND ss.queue_minutes>0 AND ss.open_status!='closed' ORDER BY ss.queue_minutes DESC,s.name""",(mall_id,)).fetchall()
    return rows_to_dicts(rows)
def my_coupons(*,mall_id,user_id,**_):
    with connection() as db: rows=db.execute("SELECT uc.*,c.title,c.store_id FROM user_coupons uc JOIN coupons c ON c.id=uc.coupon_id WHERE uc.mall_id=? AND uc.user_id=?",(mall_id,user_id)).fetchall()
    return rows_to_dicts(rows)
def query_available_coupons(*,mall_id,user_id,**_):
    return list_coupons(mall_id,user_id,available_only=True)
def query_my_reservations(*,mall_id,user_id,**_):
    return list_reservations(user_id,mall_id,active_only=True)
def live_store_status(*,mall_id,store_ids,**_):
    if not store_ids:return []
    with connection() as db: rows=db.execute(f"SELECT * FROM store_status WHERE mall_id=? AND store_id IN ({','.join('?' for _ in store_ids)})",(mall_id,*store_ids)).fetchall()
    out=rows_to_dicts(rows)
    for r in out:
        q=int(r.get("queue_minutes") or 0)
        # SQLite 中的值是商户最后一次上报的实时快照；不要按服务运行时长擅自递减，
        # 否则 Web、地图详情和商户端会显示互相矛盾的排队分钟数。
        r["queue_minutes"]=max(0,q)
        r["wait_seconds"]=r["queue_minutes"]*60
    return out
TOOLS={name:{"name":name,"description":desc,"parameters":params,"kind":"read","callback":cb} for name,desc,params,cb in [
 ("query_mall_info","查询当前商场信息",{"type":"object","properties":{}},query_mall_info),("query_parking_status","查询当前商场停车空位；收费、减免和使用规则应另查商场知识库",{"type":"object","properties":{}},query_parking_status),("search_stores","按明确的店名、类别、标签或编码搜索当前商场全部店铺，不用于查询个人预约",{"type":"object","properties":{"keyword":{"type":"string"}}},search_stores),("query_planning_locations","按活动角色查询所有可规划地点，包含真实店铺和瀑布厅、美食广场等非商户POI",{"type":"object","properties":{"activity_role":{"type":"string","enum":list(ACTIVITY_ROLES)}}},query_planning_locations),("query_reservable_stores","查询当前商场开放预约服务的全部店铺；回答‘哪些店可以预约’时必须使用它，不得使用个人预约记录",{"type":"object","properties":{"keyword":{"type":"string"}}},query_reservable_stores),("get_store_detail","查询当前商场单店详情",{"type":"object","properties":{"store_id":{"type":"string"}},"required":["store_id"]},get_store_detail),("query_member_points","查询当前用户积分余额和等级；积分有效期或兑换规则应另查商场知识库",{"type":"object","properties":{}},query_member_points),("search_mall_knowledge","检索当前商场稳定的规则、流程和公共服务知识。适用于积分、优惠券、预约、停车、会员和商场服务规则，不用于实时库存、排队、余额或订单",{"type":"object","properties":{"query":{"type":"string"},"topic":{"type":"string","enum":["points","membership","coupon","reservation","parking","service","visitor"]}},"required":["query"]},search_mall_knowledge),("query_points_rules","兼容旧流程的积分规则知识库检索",{"type":"object","properties":{"query":{"type":"string"}}},query_points_rules),("get_today_deals","查询今日仍有库存的限时特惠",{"type":"object","properties":{}},get_today_deals),("query_queue_status","查询当前需要排队的店铺",{"type":"object","properties":{}},query_queue_status),("query_available_coupons","查询当前商场仍有库存的优惠券以及当前用户是否已领取",{"type":"object","properties":{}},query_available_coupons),("query_my_reservations","只查询当前用户在当前商场已经创建且有效的预约订单；绝不能用于回答哪些店开放预约",{"type":"object","properties":{}},query_my_reservations),("my_coupons","查询当前用户已经领取的优惠券",{"type":"object","properties":{}},my_coupons),("live_store_status","查询店铺实时状态",{"type":"object","properties":{"store_ids":{"type":"array","items":{"type":"string"}}}},live_store_status)]}

for name,description in [("goal_analyze","分析规划目标与槽位"),("plan_goal","生成候选方案"),("generate_route","生成室内路线"),("present_plan","展示待确认方案"),("confirm_plan","确认计划"),("reserve_restaurant","预约餐厅"),("cancel_reservation","取消预约"),("claim_coupon","领取优惠券"),("buy_ticket","购买演示票"),("reserve_business_space","预约商务空间")]:
    TOOLS[name]={"name":name,"description":description,"parameters":{"type":"object","properties":{}},"kind":"write" if name in {"confirm_plan","reserve_restaurant","cancel_reservation","claim_coupon","buy_ticket","reserve_business_space"} else "plan","callback":None}
def schemas(): return [{k:v for k,v in t.items() if k!="callback"} for t in TOOLS.values()]
def run_tool(name,context,args=None):
    if name not in TOOLS: raise KeyError(f"unknown tool {name}")
    if TOOLS[name]["callback"] is None: raise PermissionError(f"tool {name} is controlled by the planner confirmation gate")
    clean=dict(args or {}); clean.pop("mall_id",None); clean.pop("user_id",None); clean.pop("session_id",None)
    return TOOLS[name]["callback"](mall_id=context["mall_id"],user_id=context["user_id"],session_id=context.get("session_id"),**clean)
