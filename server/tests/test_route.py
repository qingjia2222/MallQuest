import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.map_catalog import map_catalog, stable_store_id
from app.core.router import build_route, route_obstacle_collisions, shortest_path, write_demo_maps
from app.db import reset_and_seed


def setup_module():
    reset_and_seed()
    write_demo_maps()


def test_map_catalog_and_routes_share_exact_store_nodes():
    first=stable_store_id("蜀签成都串串香")
    same_target=stable_store_id("世界茶饮")
    cross_target=stable_store_id("川食公馆")
    same=build_route("mall_demo",[first,same_target])
    cross=build_route("mall_demo",[first,cross_target])
    assert same["nodes"][0]["node_id"]=="f1_entrance"
    assert same["nodes"][-1]["node_id"]==f"f1_store_{same_target}"
    assert [item["store_id"] for item in same["waypoints"]]==[first,same_target]
    assert {node["floor"] for node in cross["nodes"]}=={1,2}
    assert [node["node_id"] for node in cross["nodes"] if node["type"]=="elevator"]==["f1_elevator","f2_elevator"]
    assert any(segment["transfer_instruction"]=="乘直梯前往 2F" for segment in cross["polyline_segments"])
    assert cross["coordinate_system"]=="three_world_xz"
    assert cross["path_policy"]=="corridor_only" and cross["obstacle_clearance_verified"] is True
    assert route_obstacle_collisions("mall_demo",cross["nodes"])==[]
    assert all(a["floor"]!=b["floor"] or a["x"]==b["x"] or a["y"]==b["y"] for a,b in zip(cross["nodes"],cross["nodes"][1:]))


def test_missing_node_fails_explicitly():
    with pytest.raises(HTTPException):
        shortest_path("mall_demo","missing",f"f1_store_{stable_store_id('蜀签成都串串香')}")


def test_every_graph_edge_is_orthogonal_and_obstacle_safe():
    graph_path=Path(__file__).resolve().parents[1]/"data"/"maps"/"mall_demo"/"route_graph.json"
    graph=json.loads(graph_path.read_text(encoding="utf-8"))
    nodes={node["id"]:node for node in graph["nodes"]}
    assert graph["path_policy"]=="corridor_only"
    assert map_catalog()["business_store_count"]==43
    for left,right,_ in graph["edges"]:
        a,b=nodes[left],nodes[right]
        if a["floor"]!=b["floor"]:
            assert a["type"]==b["type"] and a["type"] in {"elevator","escalator"}
            continue
        assert a["x"]==b["x"] or a["y"]==b["y"]


def test_cross_floor_route_can_explicitly_switch_to_escalator():
    route=build_route("mall_demo",[stable_store_id("蜀签成都串串香"),stable_store_id("川食公馆")],vertical_mode="escalator")
    assert [node["node_id"] for node in route["nodes"] if node["type"]=="escalator"]==["f1_escalator","f2_escalator"]
    assert any(segment["transfer_instruction"]=="乘扶梯前往 2F" for segment in route["polyline_segments"])
    assert route_obstacle_collisions("mall_demo",route["nodes"])==[]
