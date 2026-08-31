import heapq, json, math
from pathlib import Path
from fastapi import HTTPException
from app.config import settings
from app.core.map_catalog import CORRIDOR_BOTTOM, CORRIDOR_TOP, CORRIDOR_X, map_catalog, stable_store_id
from app.db import connection

# Derive writable map artifacts from the configured database directory. This is
# also robust on Windows when test runners mangle a non-ASCII import path.
MAP_ROOT=Path(settings.mall_db_path).resolve().parent/"maps"
def _svg(floor,stores):
    boxes="".join(f'<rect x="{s["pos_x"]-55}" y="{s["pos_y"]-30}" width="110" height="60" rx="12" fill="#fff" stroke="#7C3AED"/><text x="{s["pos_x"]}" y="{s["pos_y"]+5}" text-anchor="middle" font-size="13" fill="#312E81">{s["name"]}</text>' for s in stores)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="760" viewBox="0 0 1000 760"><rect width="1000" height="760" fill="#F4F6FB"/><text x="40" y="50" font-size="28" fill="#4C1D95">星河里 {floor}F · DEMO MAP</text><path d="M120 320H880M120 520H880M520 120V680" stroke="#CBD5E1" stroke-width="70" fill="none" stroke-linecap="round"/><path d="M120 320H880M120 520H880M520 120V680" stroke="#fff" stroke-width="42" fill="none" stroke-linecap="round"/>{boxes}<circle cx="520" cy="520" r="25" fill="#06B6D4"/><text x="520" y="525" text-anchor="middle" fill="white" font-size="12">电梯</text></svg>'

def write_demo_maps():
    root=MAP_ROOT/"mall_demo"; root.mkdir(parents=True,exist_ok=True)
    with connection() as db: stores=[dict(r) for r in db.execute("SELECT * FROM stores WHERE mall_id='mall_demo'").fetchall()]
    nodes={}; edges=[]
    edge_keys=set()
    def node(node_id,floor,x,y,node_type="corridor",label="通道",**extra):
        nodes[node_id]={"id":node_id,"floor":floor,"x":round(x,3),"y":round(y,3),"type":node_type,"label":label,**extra}; return node_id
    def connect(a,b):
        key=tuple(sorted((a,b)))
        if a==b or key in edge_keys:return
        edge_keys.add(key); edges.append([a,b,round(math.dist((nodes[a]["x"],nodes[a]["y"]),(nodes[b]["x"],nodes[b]["y"])),3) if nodes[a]["floor"]==nodes[b]["floor"] else 12])
    def corridor_id(floor,x,y):
        x=0.0 if abs(float(x))<0.0005 else round(float(x),3); y=0.0 if abs(float(y))<0.0005 else round(float(y),3)
        token=lambda value:f"{value:.3f}".replace("-","m").replace(".","p")
        key=f"f{floor}_c_{token(x)}_{token(y)}"
        if key not in nodes: node(key,floor,x,y)
        return key
    catalog=map_catalog()
    for floor in (1,2):
        floor_stores=[s for s in stores if s["floor"]==floor]; (root/f"floor_{floor}.svg").write_text(_svg(floor,floor_stores),encoding="utf-8")
        sides={"top":set(),"right":set(),"bottom":set(),"left":set()}
        for x,y,bucket in ((-CORRIDOR_X,CORRIDOR_TOP,"top"),(CORRIDOR_X,CORRIDOR_TOP,"top"),(CORRIDOR_X,CORRIDOR_BOTTOM,"bottom"),(-CORRIDOR_X,CORRIDOR_BOTTOM,"bottom")):
            cid=corridor_id(floor,x,y); sides[bucket].add(cid); sides["left" if x<0 else "right"].add(cid)
        for entry in [item for item in catalog["businesses"] if item["floor"]==floor]:
            sid=stable_store_id(entry["name"]); door=entry["entrance"]; door_id=f"f{floor}_store_{sid}"
            node(door_id,floor,door["x"],door["z"],"store_entrance",f"{entry['name']}入口",store_id=sid)
            side=entry["side"]
            if side==0: px,py,bucket=max(-CORRIDOR_X,min(CORRIDOR_X,door["x"])),CORRIDOR_TOP,"top"
            elif side==1: px,py,bucket=CORRIDOR_X,max(CORRIDOR_TOP,min(CORRIDOR_BOTTOM,door["z"])),"right"
            elif side==2: px,py,bucket=max(-CORRIDOR_X,min(CORRIDOR_X,door["x"])),CORRIDOR_BOTTOM,"bottom"
            elif side==3: px,py,bucket=-CORRIDOR_X,max(CORRIDOR_TOP,min(CORRIDOR_BOTTOM,door["z"])),"left"
            else:
                px=CORRIDOR_X if door["x"]>0 else -CORRIDOR_X; py=CORRIDOR_BOTTOM if door["z"]>0 else CORRIDOR_TOP; bucket="bottom" if door["z"]>0 else "top"
                bend=node(f"{door_id}_bend",floor,px,door["z"]); connect(door_id,bend); door_id=bend
            port=corridor_id(floor,px,py); sides[bucket].add(port); connect(door_id,port)
            # 边带末端店门与主走廊投影可能同时改变 x/z；插入直角接入点，
            # 禁止任何对角线从店体或转角设施上切过去。
            current=nodes[door_id]
            if current["x"]!=nodes[port]["x"] and current["y"]!=nodes[port]["y"]:
                bend=node(f"{door_id}_orthogonal",floor,nodes[port]["x"],current["y"])
                # 移除刚才的对角边，再换成两条正交边。
                diagonal=tuple(sorted((door_id,port)))
                edge_keys.discard(diagonal)
                edges[:]=[edge for edge in edges if tuple(sorted((edge[0],edge[1])))!=diagonal]
                connect(door_id,bend); connect(bend,port)
        elevator_access=corridor_id(floor,0,CORRIDOR_BOTTOM); sides["bottom"].add(elevator_access)
        elevator=node(f"f{floor}_elevator",floor,0,3.2,"elevator",f"直梯 {floor}F"); connect(elevator_access,elevator)
        escalator_x=-8 if floor==1 else 8; escalator_access=corridor_id(floor,escalator_x,CORRIDOR_TOP); sides["top"].add(escalator_access)
        escalator=node(f"f{floor}_escalator",floor,escalator_x,-9.5,"escalator",f"扶梯 {floor}F"); connect(escalator_access,escalator)
        for bucket,ids in sides.items():
            ordered=sorted(ids,key=lambda item:nodes[item]["x"] if bucket in ("top","bottom") else nodes[item]["y"])
            for a,b in zip(ordered,ordered[1:]): connect(a,b)
    node("f1_entrance",1,0,21.5,"entrance","主入口（当前位置）"); entrance_port=corridor_id(1,0,CORRIDOR_BOTTOM); connect("f1_entrance",entrance_port)
    connect("f1_elevator","f2_elevator"); connect("f1_escalator","f2_escalator")
    graph={"mall_id":"mall_demo","coordinate_system":"three_world_xz","path_policy":"corridor_only","nodes":list(nodes.values()),"edges":edges,"obstacles":catalog["obstacles"]}
    (root/"route_graph.json").write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"map_manifest.json").write_text(json.dumps({"mall_id":"mall_demo","mall_name":"星河里","is_demo_map":True,"floors":[{"floor":1,"image":"floor_1.svg","width":1000,"height":760},{"floor":2,"image":"floor_2.svg","width":1000,"height":760}]},ensure_ascii=False,indent=2),encoding="utf-8")

def _graph(mall_id):
    path=MAP_ROOT/mall_id/"route_graph.json"
    if not path.exists() and mall_id=="mall_demo": write_demo_maps()
    if not path.exists(): raise HTTPException(status_code=404,detail="route graph not available")
    data=json.loads(path.read_text(encoding="utf-8")); nodes={n["id"]:n for n in data["nodes"]}; adj={n:[] for n in nodes}
    for a,b,w in data["edges"]: adj[a].append((b,w)); adj[b].append((a,w))
    return nodes,adj

def route_obstacle_collisions(mall_id,points):
    path=MAP_ROOT/mall_id/"route_graph.json"
    data=json.loads(path.read_text(encoding="utf-8")); collisions=[]
    for a,b in zip(points,points[1:]):
        if a["floor"]!=b["floor"]: continue
        for obstacle in data.get("obstacles",[]):
            if obstacle["floor"]!=a["floor"]: continue
            if obstacle.get("kind")=="vertical" and (a.get("type") in {"elevator","escalator"} or b.get("type") in {"elevator","escalator"}): continue
            left=obstacle["x"]-obstacle["width"]/2; right=obstacle["x"]+obstacle["width"]/2
            top=obstacle["z"]-obstacle["depth"]/2; bottom=obstacle["z"]+obstacle["depth"]/2
            ax,ay,bx,by=a["x"],a["y"],b["x"],b["y"]
            horizontal=abs(ay-by)<1e-6 and top<ay<bottom and max(min(ax,bx),left)<min(max(ax,bx),right)
            vertical=abs(ax-bx)<1e-6 and left<ax<right and max(min(ay,by),top)<min(max(ay,by),bottom)
            if horizontal or vertical: collisions.append({"from":a["node_id"],"to":b["node_id"],"obstacle":obstacle["id"],"label":obstacle["label"]})
    return collisions

def shortest_path(mall_id,start,end,vertical_mode="elevator"):
    nodes,adj=_graph(mall_id)
    if vertical_mode not in {"elevator","escalator","auto"}: raise HTTPException(status_code=422,detail="vertical_mode must be elevator, escalator or auto")
    if start not in nodes or end not in nodes: raise HTTPException(status_code=404,detail="route node not found")
    q=[(0,start,[])]; seen=set()
    while q:
        dist,node,path=heapq.heappop(q)
        if node in seen: continue
        seen.add(node); path=path+[node]
        if node==end: return path,dist,nodes
        for nxt,w in adj[node]:
            if nodes[node]["floor"]!=nodes[nxt]["floor"] and vertical_mode!="auto":
                if nodes[node]["type"]!=vertical_mode or nodes[nxt]["type"]!=vertical_mode: continue
            if nxt not in seen: heapq.heappush(q,(dist+w,nxt,path))
    raise HTTPException(status_code=422,detail="no route between nodes")

def _transfer_instruction(a,b):
    if a["floor"]==b["floor"]: return None
    mode="扶梯" if a["type"]=="escalator" and b["type"]=="escalator" else "直梯"
    return f"乘{mode}前往 {b['floor']}F"

def route_between_nodes(mall_id,start_node,end_node,vertical_mode="elevator"):
    path,total,nodes=shortest_path(mall_id,start_node,end_node,vertical_mode)
    points=[{"sequence":i+1,"node_id":nid,"floor":nodes[nid]["floor"],"x":nodes[nid]["x"],"y":nodes[nid]["y"],"type":nodes[nid]["type"],"label":nodes[nid]["label"]} for i,nid in enumerate(path)]
    collisions=route_obstacle_collisions(mall_id,points)
    if collisions: raise HTTPException(status_code=500,detail={"reason":"route_intersects_map_obstacle","collisions":collisions})
    segments=[{"floor":a["floor"],"from":[a["x"],a["y"]],"to":[b["x"],b["y"]],"transfer_instruction":_transfer_instruction(a,b)} for a,b in zip(points,points[1:])]
    return {"strategy":"shortest","vertical_mode":vertical_mode,"path_policy":"corridor_only","coordinate_system":"three_world_xz","obstacle_clearance_verified":True,"nodes":points,"polyline_segments":segments,"estimated_distance":round(total,1),"is_demo_map":True}

def build_route(mall_id,store_ids,vertical_mode="elevator"):
    if not store_ids: return {"nodes":[],"polyline_segments":[],"estimated_distance":0,"is_demo_map":True}
    marks=','.join('?' for _ in store_ids)
    with connection() as db: rows=db.execute(f"SELECT id,name,floor,route_node FROM stores WHERE mall_id=? AND id IN ({marks})",(mall_id,*store_ids)).fetchall()
    mapping={r["id"]:r["route_node"] for r in rows}; details={r["id"]:dict(r) for r in rows}
    if len(mapping)!=len(store_ids): raise HTTPException(status_code=400,detail="plan contains store outside current mall")
    graph_nodes,_=_graph(mall_id)
    if mall_id=="mall_demo" and ("f1_entrance" not in graph_nodes or any(node not in graph_nodes for node in mapping.values())):
        write_demo_maps()
    route_targets=(["f1_entrance"] if mall_id=="mall_demo" else [])+[mapping[store_id] for store_id in store_ids]
    all_nodes=[]; total=0; nodes={}
    for idx in range(len(route_targets)-1):
        path,dist,nodes=shortest_path(mall_id,route_targets[idx],route_targets[idx+1],vertical_mode); total+=dist; all_nodes.extend(path if idx==0 else path[1:])
    if len(route_targets)==1: nodes,_=_graph(mall_id); all_nodes=[route_targets[0]]
    points=[{"sequence":i+1,"node_id":nid,"floor":nodes[nid]["floor"],"x":nodes[nid]["x"],"y":nodes[nid]["y"],"type":nodes[nid]["type"],"label":nodes[nid]["label"]} for i,nid in enumerate(all_nodes)]
    collisions=route_obstacle_collisions(mall_id,points)
    if collisions: raise HTTPException(status_code=500,detail={"reason":"route_intersects_map_obstacle","collisions":collisions})
    segments=[{"floor":a["floor"],"from":[a["x"],a["y"]],"to":[b["x"],b["y"]],"transfer_instruction":_transfer_instruction(a,b)} for a,b in zip(points,points[1:])]
    waypoints=[{"sequence":index+1,"store_id":store_id,"name":details[store_id]["name"],"floor":details[store_id]["floor"],"node_id":mapping[store_id]} for index,store_id in enumerate(store_ids)]
    return {"strategy":"shortest","vertical_mode":vertical_mode,"path_policy":"corridor_only","coordinate_system":"three_world_xz","obstacle_clearance_verified":True,"start_node":"f1_entrance" if mall_id=="mall_demo" else route_targets[0],"waypoints":waypoints,"nodes":points,"polyline_segments":segments,"estimated_distance":round(total,1),"is_demo_map":True}
