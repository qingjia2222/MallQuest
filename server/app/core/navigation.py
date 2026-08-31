import re
from fastapi import HTTPException
from app.core.router import route_between_nodes
from app.db import connection

NAVIGATION_PATTERNS=(r"怎么去",r"如何去",r"带我去",r"导航(?:到|去)",r"路线(?:到|去)",r"怎么走",r"从.+到")
ALIASES={"电影院":"影院","电影":"影院","儿童乐园":"儿童乐园","服务台":"服务台","洗手间":"服务台","吃川菜":"川菜","咖啡店":"咖啡","奶茶店":"奶茶"}

def is_navigation_intent(text:str) -> bool:
    return any(re.search(pattern,text) for pattern in NAVIGATION_PATTERNS)

def _destination(mall_id:str,query:str):
    normalized=query
    for alias,target in ALIASES.items():
        if alias in normalized: normalized+=f" {target}"
    with connection() as db:
        stores=[dict(row) for row in db.execute("SELECT * FROM stores WHERE mall_id=?",(mall_id,)).fetchall()]
    exact=[store for store in stores if store["name"] in query]
    if exact: return exact[0]
    scored=[]
    for store in stores:
        terms=[store["category"],*filter(None,store["tags"].split(","))]
        score=sum(len(term) for term in terms if term and term in normalized)
        if score: scored.append((score,store))
    if not scored: raise HTTPException(status_code=404,detail="没有在当前商场找到你要去的店铺，请说出更完整的店名")
    return max(scored,key=lambda item:item[0])[1]

def resolve_navigation(mall_id:str,query:str,current_node:str|None=None):
    if not is_navigation_intent(query): raise HTTPException(status_code=422,detail="message is not a navigation request")
    store=_destination(mall_id,query); start=current_node or "f1_c0"
    route=route_between_nodes(mall_id,start,store["route_node"])
    floors=list(dict.fromkeys(node["floor"] for node in route["nodes"]))
    transfers=[segment["transfer_instruction"] for segment in route["polyline_segments"] if segment["transfer_instruction"]]
    with connection() as db:
        status=db.execute("SELECT open_status,queue_minutes,seats_available,updated_at FROM store_status WHERE store_id=? AND mall_id=?",(store["id"],mall_id)).fetchone()
    destination={"id":store["id"],"name":store["name"],"category":store["category"],"floor":store["floor"],"open_status":status["open_status"] if status else store["open_status"],"queue_minutes":status["queue_minutes"] if status else store["queue_minutes"],"seats_available":status["seats_available"] if status else store["seats_available"]}
    return {"type":"route_animation","mall_id":mall_id,"start_node":start,"start_label":"您当前所在位置","destination_store":destination,"floors":floors,"nodes":route["nodes"],"polyline_segments":route["polyline_segments"],"transfer_instructions":transfers,"estimated_distance":route["estimated_distance"],"map_mode":"demo_2_5d","replayable":True,"dismissible":True}
