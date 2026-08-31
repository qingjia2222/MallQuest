import json
from pathlib import Path
import pytest
from fastapi import HTTPException
from app.core.router import build_route, shortest_path, write_demo_maps
from app.db import reset_and_seed
def setup_module(): reset_and_seed(); write_demo_maps()
def test_same_and_cross_floor_routes_are_continuous():
    same=build_route("mall_demo",["s01","s07"]); cross=build_route("mall_demo",["s01","s09"])
    assert same["nodes"][0]["node_id"]=="f1_s01" and same["nodes"][-1]["node_id"]=="f1_s07"; assert {n["floor"] for n in cross["nodes"]}=={1,2}; assert len(cross["polyline_segments"])==len(cross["nodes"])-1
    assert [n["node_id"] for n in cross["nodes"] if n["type"]=="elevator"]==["f1_c7","f2_c7"]
    assert any(segment["transfer_instruction"]=="乘直梯前往 2F" for segment in cross["polyline_segments"])
    assert cross["vertical_mode"]=="elevator"
    assert cross["path_policy"]=="corridor_only"
    assert all(node["type"] in {"corridor","elevator","store_entrance"} for node in cross["nodes"])
    # 同层线段必须水平或垂直，入口节点也位于走廊线上；禁止斜穿店铺或公共实体。
    assert all(a["floor"]!=b["floor"] or a["x"]==b["x"] or a["y"]==b["y"] for a,b in zip(cross["nodes"],cross["nodes"][1:]))
    assert all(node["x"] in {120,320,520,720,880} or node["y"] in {320,520} for node in cross["nodes"])
def test_missing_node_fails_explicitly():
    with pytest.raises(HTTPException): shortest_path("mall_demo","missing","f1_s01")

def test_every_demo_route_edge_stays_on_corridors():
    graph_path=Path(__file__).resolve().parents[1]/"data"/"maps"/"mall_demo"/"route_graph.json"
    graph=json.loads(graph_path.read_text(encoding="utf-8"))
    nodes={node["id"]:node for node in graph["nodes"]}
    for left,right,_ in graph["edges"]:
        a,b=nodes[left],nodes[right]
        if a["floor"]!=b["floor"]:
            assert a["type"]==b["type"] and a["type"] in {"elevator","escalator"}
            if a["type"]=="elevator": assert (a["x"],a["y"])==(b["x"],b["y"])
            continue
        assert a["x"]==b["x"] or a["y"]==b["y"]
        assert all(node["type"] in {"corridor","elevator","escalator","store_entrance"} for node in (a,b))

def test_cross_floor_route_can_switch_to_escalator():
    route=build_route("mall_demo",["s01","s09"],vertical_mode="escalator")
    transfers=[n for n in route["nodes"] if n["type"]=="escalator"]
    assert [n["node_id"] for n in transfers]==["f1_escalator","f2_escalator"]
    assert any(segment["transfer_instruction"]=="乘扶梯前往 2F" for segment in route["polyline_segments"])
