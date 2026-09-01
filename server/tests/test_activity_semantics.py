from fastapi.testclient import TestClient

from app.main import app
from app.core.activity_semantics import ACTIVITY_ROLES, classify_activity, semantic_errors
from app.core.planner import create_plan
from app.core.router import build_route
from app.db import connection, reset_and_seed


def _session():
    with connection() as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",("semantic_session","user_demo","mall_demo",None,"{}",None,"IDLE","{}","now"))


def test_full_day_plan_is_varied_and_uses_plannable_poi():
    reset_and_seed();_session()
    plan=create_plan("user_demo","mall_demo","semantic_session","帮我规划一整天的约会","date",{"time":"上午10点","people":2,"duration":8,"full_day":True})
    roles=[classify_activity(item) for item in plan["itinerary"]]
    assert not semantic_errors(plan["itinerary"],plan["slots"])
    assert "正餐" in roles and len(set(roles))>=3
    assert any(item.get("location_kind")=="poi" for item in plan["itinerary"])
    assert plan["route"]["semantic_validation"]["valid"] is True


def test_all_locations_have_declared_activity_role():
    reset_and_seed();_session()
    plan=create_plan("user_demo","mall_demo","semantic_session","帮我规划一整天","date",{"duration":8,"full_day":True})
    assert all(item.get("activity_role") in ACTIVITY_ROLES for item in plan["itinerary"])


def test_poi_participates_in_corridor_graph_route():
    reset_and_seed()
    with connection() as db: store_id=db.execute("SELECT id FROM stores WHERE mall_id='mall_demo' AND floor=2 ORDER BY id LIMIT 1").fetchone()[0]
    route=build_route("mall_demo",[store_id,"poi_waterfall_hall_f1"],vertical_mode="escalator")
    assert route["vertical_mode"]=="escalator"
    assert any(node["type"]=="escalator" for node in route["nodes"])
    assert route["waypoints"][-1]["location_kind"]=="poi"


def test_navigation_mode_switch_bypasses_natural_language_intent_parser():
    reset_and_seed();client=TestClient(app)
    login=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]
    headers={"Authorization":f"Bearer {login['token']}"}
    session=client.post("/api/scan",headers=headers,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    with connection() as db: store_id=db.execute("SELECT id FROM stores WHERE mall_id='mall_demo' AND floor=2 ORDER BY id LIMIT 1").fetchone()[0]
    response=client.post("/api/navigation/resolve",headers=headers,json={"session_id":session,"destination_store_id":store_id,"vertical_mode":"escalator","current_node":"f1_entrance"})
    assert response.status_code==200
    route=response.json()["data"]
    assert route["vertical_mode"]=="escalator" and any(node["type"]=="escalator" for node in route["nodes"])
