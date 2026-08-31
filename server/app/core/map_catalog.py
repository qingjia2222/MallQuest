import hashlib
import json
from functools import lru_cache
from pathlib import Path


WEB_STORE_ROOT=Path(__file__).resolve().parents[3]/"web"/"src"/"store"
W=58.0
EDGE=8.0
INNER=W/2-EDGE
CORRIDOR_X=18.0
CORRIDOR_TOP=-15.0
CORRIDOR_BOTTOM=12.0


def stable_store_id(name: str) -> str:
    return "map_"+hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


@lru_cache(maxsize=1)
def map_catalog() -> dict:
    ring=json.loads((WEB_STORE_ROOT/"mall_ring.json").read_text(encoding="utf-8"))
    info=json.loads((WEB_STORE_ROOT/"store_info.json").read_text(encoding="utf-8"))
    businesses=[]; facilities=[]; obstacles=[]
    edged=W/2-EDGE/2; arm_len=EDGE+4; gap=0.6; span=W-2*arm_len-2*gap
    for floor in (1,2):
        for side in range(4):
            items=[item for item in ring["stores"] if int(item["floor"])==floor and int(item["side"])==side]
            per=len(items) or 1; block_width=span/per-0.5
            for index,item in enumerate(items):
                if floor==1 and side==2 and index==per//2:
                    continue
                along=side in (0,2); offset=0 if per==1 else (index/(per-1)-0.5)*(span-block_width)
                x,z=(offset,-edged) if side==0 else (edged,-offset) if side==1 else (offset,edged) if side==2 else (-edged,offset)
                width,depth=(block_width,EDGE-0.4) if along else (EDGE-0.4,block_width)
                entrance={"x":x,"z":-INNER,"floor":floor} if side==0 else {"x":INNER,"z":z,"floor":floor} if side==1 else {"x":x,"z":INNER,"floor":floor} if side==2 else {"x":-INNER,"z":z,"floor":floor}
                details=info.get(item["name"],{}); is_facility=item.get("fac")=="true" or details.get("category")=="服务设施" or any(word in item["name"] for word in ("卫生间","服务台","信息台"))
                entry={"name":item["name"],"floor":floor,"side":side,"source_key":f"ring_f{floor}_s{side}_{item.get('sid',index)}","x":round(x,3),"z":round(z,3),"width":round(width,3),"depth":round(depth,3),"entrance":entrance,"details":details,"kind":"facility" if is_facility else "business"}
                (facilities if is_facility else businesses).append(entry)
                obstacles.append({"id":entry["source_key"],"label":entry["name"],"floor":floor,"kind":entry["kind"],"x":entry["x"],"z":entry["z"],"width":entry["width"],"depth":entry["depth"]})
    arm=EDGE-0.4
    for floor_key,names in ring.get("corners",{}).items():
        floor=int(str(floor_key).replace("F",""))
        for index,(sx,sz) in enumerate(((-1,-1),(1,-1),(1,1),(-1,1))):
            name=names[index]; details=info.get(name,{})
            x,z=sx*edged,sz*edged; entrance={"x":sx*INNER,"z":sz*INNER,"floor":floor}
            is_facility=details.get("category")=="服务设施"
            entry={"name":name,"floor":floor,"side":4+index,"source_key":f"corner_f{floor}_{index}","x":round(x,3),"z":round(z,3),"width":arm_len,"depth":arm_len,"entrance":entrance,"details":details,"kind":"facility" if is_facility else "business"}
            (facilities if is_facility else businesses).append(entry)
            obstacles.extend([
                {"id":entry["source_key"]+"_x","label":name,"floor":floor,"kind":entry["kind"],"x":round(sx*(W/2-arm_len/2),3),"z":round(z,3),"width":arm_len,"depth":arm},
                {"id":entry["source_key"]+"_z","label":name,"floor":floor,"kind":entry["kind"],"x":round(x,3),"z":round(sz*(W/2-arm_len/2),3),"width":arm,"depth":arm_len},
            ])
    central=[
        ("service_desk_f1","服务台",1,-9,-1,11,8,"facility"),("waterfall_hall_f1","瀑布厅",1,9,-1,11,8,"landmark"),
        ("children_area_f2","儿童乐园",2,-9,-1,11,8,"facility"),("food_court_f2","美食广场",2,9,-1,11,8,"facility"),
        ("elevator_f1","直梯",1,0,0,6,6,"vertical"),("elevator_f2","直梯",2,0,0,6,6,"vertical"),
        ("escalator_f1","扶梯",1,-8,-9.5,5,3,"vertical"),("escalator_f2","扶梯",2,8,-9.5,5,3,"vertical"),
    ]
    for oid,label,floor,x,z,width,depth,kind in central:
        facilities.append({"name":label,"floor":floor,"source_key":oid,"x":x,"z":z,"width":width,"depth":depth,"kind":kind})
        obstacles.append({"id":oid,"label":label,"floor":floor,"kind":kind,"x":x,"z":z,"width":width,"depth":depth})
    return {"businesses":businesses,"facilities":facilities,"obstacles":obstacles,"visual_shop_blocks":len(businesses)+len([item for item in facilities if item.get("source_key","").startswith(("ring_","corner_"))]),"business_store_count":len(businesses)}
