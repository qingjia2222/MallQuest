import pytest
from fastapi import HTTPException
from app.core.router import build_route, shortest_path, write_demo_maps
from app.db import reset_and_seed
def setup_module(): reset_and_seed(); write_demo_maps()
def test_same_and_cross_floor_routes_are_continuous():
    same=build_route("mall_demo",["s01","s07"]); cross=build_route("mall_demo",["s01","s09"])
    assert same["nodes"][0]["node_id"]=="f1_s01" and same["nodes"][-1]["node_id"]=="f1_s07"; assert {n["floor"] for n in cross["nodes"]}=={1,2}; assert len(cross["polyline_segments"])==len(cross["nodes"])-1
def test_missing_node_fails_explicitly():
    with pytest.raises(HTTPException): shortest_path("mall_demo","missing","f1_s01")
