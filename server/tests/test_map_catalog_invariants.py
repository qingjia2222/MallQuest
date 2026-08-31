from app.core.map_catalog import map_catalog, stable_store_id
from app.core.planner import DEFAULT_SLOTS, create_plan
from app.core.router import route_obstacle_collisions, route_between_nodes, write_demo_maps
from app.db import connection, database_health, reset_and_seed


def test_map_is_the_single_store_and_route_source_for_all_scenarios():
    reset_and_seed()
    write_demo_maps()
    catalog=map_catalog()
    expected={stable_store_id(item["name"]):item for item in catalog["businesses"]}
    with connection() as db:
        actual={row["id"]:row["name"] for row in db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo'")}
        bindings={row["store_id"] for row in db.execute("SELECT store_id FROM store_map_bindings WHERE mall_id='mall_demo'")}
        statuses={row["store_id"] for row in db.execute("SELECT store_id FROM store_status WHERE mall_id='mall_demo'")}
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",("catalog_audit","user_demo","mall_demo",None,"{}",None,"IDLE","{}","now"))
    assert len(expected)==43 and actual.keys()==expected.keys()==bindings==statuses
    assert "蜀香小院" not in actual.values()
    assert database_health()["ok"] is True

    for scene in ("date","banquet","gift","family_day","business"):
        plan=create_plan("user_demo","mall_demo","catalog_audit",scene,scene,DEFAULT_SLOTS[scene])
        itinerary_ids=[item["id"] for item in plan["itinerary"]]
        waypoint_ids=[item["store_id"] for item in plan["route"]["waypoints"]]
        assert itinerary_ids and itinerary_ids==waypoint_ids
        assert set(itinerary_ids)<=set(expected)
        assert plan["route"]["vertical_mode"]=="elevator"
        assert route_obstacle_collisions("mall_demo",plan["route"]["nodes"])==[]

    for store_id,item in expected.items():
        route=route_between_nodes("mall_demo","f1_entrance",f"f{item['floor']}_store_{store_id}")
        assert route_obstacle_collisions("mall_demo",route["nodes"])==[]
