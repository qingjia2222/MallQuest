"""Planning semantics shared by online LLM plans and deterministic fallback.

Stable business facts remain in SQLite.  This module only adds the planning
meaning that the database did not previously express: activity roles, day
periods and non-merchant POIs that already exist on the indoor map.
"""
from __future__ import annotations

from copy import deepcopy


ACTIVITY_ROLES=("正餐","饮品甜品","购物","文化","运动","亲子","休息","公共景观")
FOOD_ROLES={"正餐","饮品甜品"}

TIME_PERIODS=(
    {"key":"早餐","start":8*60,"end":10*60+30,"duration":45,"preferred_roles":["正餐","饮品甜品"]},
    {"key":"午餐","start":11*60+30,"end":13*60+30,"duration":75,"preferred_roles":["正餐"]},
    {"key":"下午茶","start":14*60,"end":16*60+30,"duration":45,"preferred_roles":["饮品甜品","休息"]},
    {"key":"晚餐","start":17*60+30,"end":20*60,"duration":90,"preferred_roles":["正餐"]},
    {"key":"夜间休闲","start":20*60,"end":22*60,"duration":45,"preferred_roles":["文化","休息","公共景观"]},
)

_POIS={
    "mall_demo":[
        {"id":"poi_waterfall_hall_f1","name":"瀑布厅","floor":1,"category":"公共景观","activity_role":"公共景观","route_node":"f1_c_18p000_0p000","description":"商场一层中央公共景观与休息区域","tags":"景观,休息,拍照","suggested_duration_minutes":35},
        {"id":"poi_food_court_f2","name":"美食广场","floor":2,"category":"公共空间","activity_role":"休息","route_node":"f2_c_18p000_0p000","description":"商场二层公共就餐与休息区域，不代表具体餐厅预约","tags":"公共空间,休息,集合","suggested_duration_minutes":30},
        {"id":"poi_children_area_f2","name":"儿童乐园","floor":2,"category":"亲子","activity_role":"亲子","route_node":"f2_c_m18p000_0p000","description":"商场二层亲子活动公共区域","tags":"亲子,儿童,活动","suggested_duration_minutes":60},
    ]
}


def classify_activity(item:dict)->str:
    explicit=item.get("activity_role")
    if explicit in ACTIVITY_ROLES:return explicit
    text=" ".join(str(item.get(key) or "") for key in ("name","category","tags","description")).lower()
    rules=(
        ("亲子",("亲子","儿童","婴幼儿","玩具")),
        ("运动",("运动","健身","瑜伽","球馆","游泳")),
        ("文化",("书局","书店","影院","电影","展览","文创","艺术")),
        ("公共景观",("景观","瀑布","中庭","花园")),
        ("休息",("休息","公共空间","美食广场","服务空间")),
        ("饮品甜品",("饮品甜品","咖啡","茶饮","奶茶","甜品","烘焙","蛋糕","糖水","面包")),
        ("正餐",("餐饮","餐厅","火锅","料理","寿司","面食","牛排","川菜","粤菜","日料","西餐","茶餐厅","饭店")),
        ("购物",("零售","美妆","珠宝","服装","数码","家居","眼镜","礼品","商店")),
    )
    for role,words in rules:
        if any(word in text for word in words):return role
    return "购物"


def decorate_location(item:dict,kind:str|None=None)->dict:
    result=dict(item)
    result["location_kind"]=kind or result.get("location_kind") or "store"
    result["activity_role"]=classify_activity(result)
    result.setdefault("suggested_duration_minutes",75 if result["activity_role"]=="正餐" else 45)
    return result


def planning_pois(mall_id:str)->list[dict]:
    result=[]
    for raw in _POIS.get(mall_id,[]):
        item=deepcopy(raw)
        item.update({"mall_id":mall_id,"location_kind":"poi","open_status":"open","queue_minutes":0,"seats_available":None,"reservable":0,"avg_price":0})
        result.append(item)
    return result


def period_for_minutes(minutes:int|None)->dict|None:
    if minutes is None:return None
    return next((item for item in TIME_PERIODS if item["start"]<=minutes<=item["end"]),None)


def is_full_day(slots:dict,text:str="",itinerary:list[dict]|None=None)->bool:
    if any(word in (text or "") for word in ("全天","一整天","一天","从早到晚")):return True
    try:
        if float(slots.get("duration") or 0)>=6:return True
    except (TypeError,ValueError):pass
    values=[]
    for item in itinerary or []:
        label=item.get("time_label") or ""
        if ":" in label:
            try:
                hour,minute=label.split(":",1);values.append(int(hour)*60+int(minute[:2]))
            except ValueError:pass
    return bool(values and max(values)-min(values)>=6*60)


def semantic_errors(itinerary:list[dict],slots:dict,text:str="")->list[str]:
    """Reject structurally possible but humanly implausible plans."""
    if not itinerary:return ["方案没有地点"]
    roles=[classify_activity(item) for item in itinerary]
    errors=[]
    if len(set(item.get("id") for item in itinerary))!=len(itinerary):errors.append("方案包含重复地点")
    if any(a==b==c for a,b,c in zip(roles,roles[1:],roles[2:])):errors.append("连续安排了三个同类活动")
    if is_full_day(slots,text,itinerary):
        if all(role in FOOD_ROLES for role in roles):errors.append("整日方案不能全部是餐饮或甜品")
        if len(set(roles))<3:errors.append("整日方案的活动类型不足")
        timed=[(item, _minutes(item.get("time_label"))) for item in itinerary]
        for key,start,end in (("午餐",11*60+30,13*60+30),("晚餐",17*60+30,20*60)):
            if timed and min((m for _,m in timed if m is not None),default=24*60)<=end and max((m for _,m in timed if m is not None),default=0)>=start:
                if not any(start<=m<=end and classify_activity(item)=="正餐" for item,m in timed if m is not None):errors.append(f"{key}时段缺少正餐")
    return list(dict.fromkeys(errors))


def _minutes(label:str|None)->int|None:
    if not label or ":" not in label:return None
    try:
        hour,minute=label.split(":",1);return int(hour)*60+int(minute[:2])
    except ValueError:return None


def semantic_schedule(itinerary:list[dict],slots:dict,text:str="",time_plan:dict|None=None)->list[str]:
    """Create human time points; explicit valid model times remain authoritative."""
    if is_full_day(slots,text,itinerary):
        anchors={"饮品甜品":["10:00","15:00"],"正餐":["12:00","18:30"],"购物":["13:30"],"文化":["14:00","20:15"],"运动":["14:00"],"亲子":["14:00"],"休息":["16:00","20:30"],"公共景观":["20:30"]}
        counters={};result=[];last=9*60+15
        for item in itinerary:
            explicit=(time_plan or {}).get(item.get("id"));value=_minutes(explicit)
            if value is None:
                role=classify_activity(item);index=counters.get(role,0);choices=anchors.get(role,["14:00"]);label=choices[min(index,len(choices)-1)];counters[role]=index+1;value=_minutes(label)
            if value<=last:value=last+max(30,int(item.get("suggested_duration_minutes") or 45))
            result.append(f"{value//60%24:02d}:{value%60:02d}");last=value
        return result
    return []
