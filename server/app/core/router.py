import heapq, json, math
from pathlib import Path
from fastapi import HTTPException
from app.db import connection

MAP_ROOT=Path(__file__).resolve().parents[2]/"data"/"maps"
def _svg(floor,stores):
    boxes="".join(f'<rect x="{s["pos_x"]-55}" y="{s["pos_y"]-30}" width="110" height="60" rx="12" fill="#fff" stroke="#7C3AED"/><text x="{s["pos_x"]}" y="{s["pos_y"]+5}" text-anchor="middle" font-size="13" fill="#312E81">{s["name"]}</text>' for s in stores)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="760" viewBox="0 0 1000 760"><rect width="1000" height="760" fill="#F4F6FB"/><text x="40" y="50" font-size="28" fill="#4C1D95">星河里 {floor}F · DEMO MAP</text><path d="M120 320H880M120 520H880M520 120V680" stroke="#CBD5E1" stroke-width="70" fill="none" stroke-linecap="round"/><path d="M120 320H880M120 520H880M520 120V680" stroke="#fff" stroke-width="42" fill="none" stroke-linecap="round"/>{boxes}<circle cx="520" cy="520" r="25" fill="#06B6D4"/><text x="520" y="525" text-anchor="middle" fill="white" font-size="12">电梯</text></svg>'

def write_demo_maps():
    root=MAP_ROOT/"mall_demo"; root.mkdir(parents=True,exist_ok=True)
    with connection() as db: stores=[dict(r) for r in db.execute("SELECT * FROM stores WHERE mall_id='mall_demo'").fetchall()]
    nodes={}; edges=[]
    for floor in (1,2):
        floor_stores=[s for s in stores if s["floor"]==floor]; (root/f"floor_{floor}.svg").write_text(_svg(floor,floor_stores),encoding="utf-8")
        corridor=[(120,320),(320,320),(520,320),(720,320),(880,320),(120,520),(320,520),(520,520),(720,520),(880,520)]
        corridor_edges=[(0,1),(1,2),(2,3),(3,4),(5,6),(6,7),(7,8),(8,9),(0,5),(1,6),(2,7),(3,8),(4,9)]
        for i,(x,y) in enumerate(corridor): nodes[f"f{floor}_c{i}"]={"id":f"f{floor}_c{i}","floor":floor,"x":x,"y":y,"type":"corridor","label":"通道"}
        for a,b in corridor_edges: edges.append([f"f{floor}_c{a}",f"f{floor}_c{b}",math.dist(corridor[a],corridor[b])])
        for s in floor_stores:
            # 店铺 route_node 表示临近走廊上的“店铺入口”，而非店铺内部中心。
            # 将入口正交投影到最近走廊边，并只沿该边连接，保证动画不穿越任何实体区域。
            projections=[]
            for a,b in corridor_edges:
                ax,ay=corridor[a]; bx,by=corridor[b]
                dx,dy=bx-ax,by-ay; denom=dx*dx+dy*dy
                t=max(0.0,min(1.0,((s["pos_x"]-ax)*dx+(s["pos_y"]-ay)*dy)/denom))
                px,py=ax+t*dx,ay+t*dy
                projections.append((math.dist((s["pos_x"],s["pos_y"]),(px,py)),a,b,px,py))
            _,a,b,px,py=min(projections,key=lambda item:item[0])
            nid=s["route_node"]
            nodes[nid]={"id":nid,"floor":floor,"x":px,"y":py,"type":"store_entrance","label":f"{s['name']}入口","store_id":s["id"]}
            edges.append([nid,f"f{floor}_c{a}",math.dist((px,py),corridor[a])])
            edges.append([nid,f"f{floor}_c{b}",math.dist((px,py),corridor[b])])
    # 直梯与扶梯是两套独立换层边。扶梯上下口错位，3D 红点会沿斜坡移动；直梯保持垂直。
    edges.append(["f1_c7","f2_c7",35]); nodes["f1_c7"].update(type="elevator",label="直梯 1F"); nodes["f2_c7"].update(type="elevator",label="直梯 2F")
    nodes["f1_escalator"]={"id":"f1_escalator","floor":1,"x":720,"y":320,"type":"escalator","label":"扶梯 1F"}
    nodes["f2_escalator"]={"id":"f2_escalator","floor":2,"x":520,"y":320,"type":"escalator","label":"扶梯 2F"}
    edges.extend([["f1_c3","f1_escalator",0],["f2_c2","f2_escalator",0],["f1_escalator","f2_escalator",42]])
    (root/"route_graph.json").write_text(json.dumps({"mall_id":"mall_demo","nodes":list(nodes.values()),"edges":edges},ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"map_manifest.json").write_text(json.dumps({"mall_id":"mall_demo","mall_name":"星河里","is_demo_map":True,"floors":[{"floor":1,"image":"floor_1.svg","width":1000,"height":760},{"floor":2,"image":"floor_2.svg","width":1000,"height":760}]},ensure_ascii=False,indent=2),encoding="utf-8")

def _graph(mall_id):
    path=MAP_ROOT/mall_id/"route_graph.json"
    if not path.exists() and mall_id=="mall_demo": write_demo_maps()
    if not path.exists(): raise HTTPException(status_code=404,detail="route graph not available")
    data=json.loads(path.read_text(encoding="utf-8")); nodes={n["id"]:n for n in data["nodes"]}; adj={n:[] for n in nodes}
    for a,b,w in data["edges"]: adj[a].append((b,w)); adj[b].append((a,w))
    return nodes,adj

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
    segments=[{"floor":a["floor"],"from":[a["x"],a["y"]],"to":[b["x"],b["y"]],"transfer_instruction":_transfer_instruction(a,b)} for a,b in zip(points,points[1:])]
    return {"strategy":"shortest","vertical_mode":vertical_mode,"path_policy":"corridor_only","nodes":points,"polyline_segments":segments,"estimated_distance":round(total,1),"is_demo_map":True}

def build_route(mall_id,store_ids,vertical_mode="elevator"):
    if not store_ids: return {"nodes":[],"polyline_segments":[],"estimated_distance":0,"is_demo_map":True}
    marks=','.join('?' for _ in store_ids)
    with connection() as db: rows=db.execute(f"SELECT id,route_node FROM stores WHERE mall_id=? AND id IN ({marks})",(mall_id,*store_ids)).fetchall()
    mapping={r["id"]:r["route_node"] for r in rows}
    if len(mapping)!=len(store_ids): raise HTTPException(status_code=400,detail="plan contains store outside current mall")
    all_nodes=[]; total=0; nodes={}
    for idx in range(len(store_ids)-1):
        path,dist,nodes=shortest_path(mall_id,mapping[store_ids[idx]],mapping[store_ids[idx+1]],vertical_mode); total+=dist; all_nodes.extend(path if idx==0 else path[1:])
    if len(store_ids)==1: nodes,_=_graph(mall_id); all_nodes=[mapping[store_ids[0]]]
    points=[{"sequence":i+1,"node_id":nid,"floor":nodes[nid]["floor"],"x":nodes[nid]["x"],"y":nodes[nid]["y"],"type":nodes[nid]["type"],"label":nodes[nid]["label"]} for i,nid in enumerate(all_nodes)]
    segments=[{"floor":a["floor"],"from":[a["x"],a["y"]],"to":[b["x"],b["y"]],"transfer_instruction":_transfer_instruction(a,b)} for a,b in zip(points,points[1:])]
    return {"strategy":"shortest","vertical_mode":vertical_mode,"path_policy":"corridor_only","nodes":points,"polyline_segments":segments,"estimated_distance":round(total,1),"is_demo_map":True}
