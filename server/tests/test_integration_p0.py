import json

from fastapi.testclient import TestClient

from app.db import connection, database_health, reset_and_seed
from app.main import app


def login_scan(client):
    token=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]
    headers={"Authorization":f"Bearer {token}"}
    session=client.post("/api/scan",headers=headers,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    return headers,session


def test_conversation_history_is_persisted_for_the_next_llm_turn():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    client.post("/api/chat",headers=headers,json={"session_id":session,"message":"我喜欢安静一点"})
    client.post("/api/chat",headers=headers,json={"session_id":session,"message":"再推荐一家店"})
    with connection() as db: row=db.execute("SELECT context_json FROM sessions WHERE id=?",(session,)).fetchone()
    history=json.loads(row["context_json"])["conversation_history"]
    assert [item["role"] for item in history[-4:]]==["user","assistant","user","assistant"]
    assert history[-4]["content"]=="我喜欢安静一点"


def test_coupon_purchase_and_member_assets_share_sqlite_truth():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    coupons=client.get("/api/coupons",headers=headers,params={"session_id":session}).json()["data"]
    client.post("/api/coupons/claim",headers=headers,json={"session_id":session,"coupon_id":coupons[0]["id"],"confirmed":True})
    deal=client.get("/api/deals",headers=headers,params={"session_id":session}).json()["data"][0]
    bought=client.post("/api/deals/purchase",headers=headers,json={"session_id":session,"deal_id":deal["id"],"quantity":1,"confirmed":True})
    assert bought.status_code==200
    assets=client.get("/api/member/assets",headers=headers).json()["data"]
    assert assets["coupons"]==1 and assets["deal_purchases"]==1
    assert client.get("/api/deals",headers=headers,params={"session_id":session}).json()["data"][0]["purchased_quantity"]==1


def test_plan_edit_rebuilds_route_and_movie_enters_confirmation_snapshot():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    made=client.post("/api/plan/goal",headers=headers,json={"session_id":session,"scene":"date","slots":{"time":"今晚7点","people":2,"budget_per_person":250,"cuisine":"川菜","want_movie":True}}).json()["data"]
    itinerary=list(reversed(made["itinerary"])); edited=[{"id":store["id"],"time_label":f"{19+index:02d}:00"} for index,store in enumerate(itinerary)]
    patched=client.patch(f"/api/plan/{made['plan_id']}",headers=headers,json={"itinerary":edited,"vertical_mode":"elevator"}).json()["data"]
    assert [store["id"] for store in patched["itinerary"]]==[item["id"] for item in edited]
    assert [store["time_label"] for store in patched["itinerary"]]==[item["time_label"] for item in edited]
    assert patched["route"]["nodes"] and patched["route"]["path_policy"]=="corridor_only"
    cinema=next((store for store in patched["itinerary"] if store["category"]=="影院"),None)
    modifications={"selected_movie":"星际穿越(重映)"} if cinema else {}
    done=client.post("/api/plan/confirm",headers=headers,json={"plan_id":made["plan_id"],"decision":"confirm","modifications":modifications}).json()["data"]
    assert done["confirmation_snapshot"] and done["confirmation_snapshot"]["itinerary"]
    if cinema: assert done["confirmation_snapshot"]["selected_movie"]=="星际穿越(重映)"


def test_done_or_stale_plan_can_be_copied_to_editable_draft_with_all_waypoints():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    made=client.post("/api/plan/goal",headers=headers,json={"session_id":session,"scene":"date","slots":{"time":"今晚7点","people":2,"want_movie":True}}).json()["data"]
    done=client.post("/api/plan/confirm",headers=headers,json={"plan_id":made["plan_id"],"decision":"confirm"}).json()["data"]
    payload={"session_id":session,"source_plan_id":done["plan_id"],"scene":done["scene"],"slots":done["slots"],"itinerary":done["itinerary"],"vertical_mode":"elevator"}
    copied=client.post("/api/plan/editable-copy",headers=headers,json=payload).json()["data"]
    assert copied["plan_id"]!=done["plan_id"] and copied["state"]=="CONFIRM"
    assert [item["id"] for item in copied["itinerary"]]==[item["id"] for item in done["itinerary"]]
    with connection() as db:
        route_nodes={row["route_node"] for row in db.execute("SELECT route_node FROM stores WHERE id IN (%s)" % ",".join("?" for _ in copied["itinerary"]),tuple(item["id"] for item in copied["itinerary"])).fetchall()}
    assert route_nodes.issubset({node["node_id"] for node in copied["route"]["nodes"]})
    stale={**payload,"source_plan_id":"plan_removed_by_demo_reset"}
    recovered=client.post("/api/plan/editable-copy",headers=headers,json=stale).json()["data"]
    assert recovered["state"]=="CONFIRM" and len(recovered["itinerary"])==len(done["itinerary"])


def test_plan_revision_rejects_stale_edits_and_confirm_is_idempotent():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    made=client.post("/api/plan/goal",headers=headers,json={"session_id":session,"scene":"date","slots":{"time":"今晚7点","people":2,"want_movie":True}}).json()["data"]
    assert made["revision"]==1
    itinerary=[{"id":item["id"],"time_label":item.get("time_label") or "19:00"} for item in made["itinerary"]]
    edited=client.patch(f"/api/plan/{made['plan_id']}",headers=headers,json={"itinerary":itinerary,"expected_revision":1})
    assert edited.status_code==200 and edited.json()["data"]["revision"]==2
    stale=client.patch(f"/api/plan/{made['plan_id']}",headers=headers,json={"itinerary":itinerary,"expected_revision":1})
    assert stale.status_code==409
    done=client.post("/api/plan/confirm",headers=headers,json={"plan_id":made["plan_id"],"decision":"confirm","expected_revision":2})
    assert done.status_code==200 and done.json()["data"]["state"]=="DONE"
    with connection() as db:
        before=tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("reservations","user_tickets","user_coupons"))
    replay=client.post("/api/plan/confirm",headers=headers,json={"plan_id":made["plan_id"],"decision":"confirm","expected_revision":2})
    assert replay.status_code==200 and replay.json()["data"]["state"]=="DONE"
    with connection() as db:
        after=tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("reservations","user_tickets","user_coupons"))
    assert after==before


def test_database_readiness_covers_store_status_and_map_bindings():
    reset_and_seed()
    status=database_health()
    assert status["ok"] is True
    assert status["integrity"]=="ok"
    assert status["stores"]==status["store_statuses"]==status["map_bindings"]
