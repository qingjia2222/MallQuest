from app.core.rag import answer
from app.datasource.registry import registry
from app.db import connection, rows_to_dicts
def query_mall_info(*,mall_id,**_): return {"mall_id":mall_id,"name":registry.get(mall_id).name}
def query_parking_status(*,mall_id,**_):
    with connection() as db: rows=db.execute("SELECT area,total,free,updated_at FROM parking WHERE mall_id=? ORDER BY area",(mall_id,)).fetchall()
    return {"areas":rows_to_dicts(rows),"total_free":sum(r["free"] for r in rows)}
def search_stores(*,mall_id,keyword="",**_): return registry.stores(mall_id,keyword)
def query_queue_status(*,mall_id,minimum_minutes=1,**_):
    with connection() as db:
        rows=db.execute("""SELECT s.id,s.name,s.category,s.floor,ss.open_status,
            ss.queue_minutes,ss.seats_available,ss.updated_at
            FROM stores s JOIN store_status ss ON ss.store_id=s.id AND ss.mall_id=s.mall_id
            WHERE s.mall_id=? AND ss.queue_minutes>=?
            ORDER BY ss.queue_minutes DESC,s.name""",(mall_id,minimum_minutes)).fetchall()
    return rows_to_dicts(rows)
def get_store_detail(*,mall_id,store_id,**_):
    with connection() as db: row=db.execute("SELECT * FROM stores WHERE mall_id=? AND id=?",(mall_id,store_id)).fetchone()
    return dict(row) if row else None
def query_member_points(*,mall_id,user_id,**_):
    with connection() as db: row=db.execute("SELECT points,level,expires_on FROM members WHERE mall_id=? AND user_id=?",(mall_id,user_id)).fetchone()
    return dict(row) if row else None
def query_points_rules(*,mall_id,query="积分",**_): return answer(query,mall_id)
def get_today_deals(*,mall_id,**_):
    with connection() as db: rows=db.execute("SELECT * FROM deals WHERE mall_id=? AND stock>0",(mall_id,)).fetchall()
    return rows_to_dicts(rows)
def my_coupons(*,mall_id,user_id,**_):
    with connection() as db: rows=db.execute("SELECT uc.*,c.title,c.store_id FROM user_coupons uc JOIN coupons c ON c.id=uc.coupon_id WHERE uc.mall_id=? AND uc.user_id=?",(mall_id,user_id)).fetchall()
    return rows_to_dicts(rows)
def live_store_status(*,mall_id,store_ids,**_):
    if not store_ids:return []
    with connection() as db: rows=db.execute(f"SELECT * FROM store_status WHERE mall_id=? AND store_id IN ({','.join('?' for _ in store_ids)})",(mall_id,*store_ids)).fetchall()
    return rows_to_dicts(rows)
TOOLS={name:{"name":name,"description":desc,"parameters":params,"kind":"read","callback":cb} for name,desc,params,cb in [
 ("query_mall_info","查询当前商场信息",{"type":"object","properties":{}},query_mall_info),("query_parking_status","查询当前商场停车空位",{"type":"object","properties":{}},query_parking_status),("search_stores","按店名或类别关键词搜索当前商场店铺",{"type":"object","properties":{"keyword":{"type":"string"}}},search_stores),("query_queue_status","查询当前需要排队的店铺并按等待时间排序",{"type":"object","properties":{"minimum_minutes":{"type":"integer","minimum":1}}},query_queue_status),("get_store_detail","查询当前商场单店详情",{"type":"object","properties":{"store_id":{"type":"string"}},"required":["store_id"]},get_store_detail),("query_member_points","查询当前用户积分",{"type":"object","properties":{}},query_member_points),("query_points_rules","检索积分规则知识库",{"type":"object","properties":{"query":{"type":"string"}}},query_points_rules),("get_today_deals","查询今日特惠",{"type":"object","properties":{}},get_today_deals),("my_coupons","查询当前用户优惠券",{"type":"object","properties":{}},my_coupons),("live_store_status","查询店铺实时状态",{"type":"object","properties":{"store_ids":{"type":"array","items":{"type":"string"}}}},live_store_status)]}

for name,description in [("goal_analyze","分析规划目标与槽位"),("plan_goal","生成候选方案"),("generate_route","生成室内路线"),("present_plan","展示待确认方案"),("confirm_plan","确认计划"),("reserve_restaurant","预约餐厅"),("cancel_reservation","取消预约"),("claim_coupon","领取优惠券"),("buy_ticket","购买演示票"),("reserve_business_space","预约商务空间")]:
    TOOLS[name]={"name":name,"description":description,"parameters":{"type":"object","properties":{}},"kind":"write" if name in {"confirm_plan","reserve_restaurant","cancel_reservation","claim_coupon","buy_ticket","reserve_business_space"} else "plan","callback":None}
def schemas(): return [{k:v for k,v in t.items() if k!="callback"} for t in TOOLS.values()]
def run_tool(name,context,args=None):
    if name not in TOOLS: raise KeyError(f"unknown tool {name}")
    if TOOLS[name]["callback"] is None: raise PermissionError(f"tool {name} is controlled by the planner confirmation gate")
    clean=dict(args or {}); clean.pop("mall_id",None); clean.pop("user_id",None); clean.pop("session_id",None)
    return TOOLS[name]["callback"](mall_id=context["mall_id"],user_id=context["user_id"],session_id=context.get("session_id"),**clean)
