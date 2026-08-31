from fastapi.testclient import TestClient
from app.db import reset_and_seed
from app.main import app

def login_scan(client):
    token=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]
    headers={"Authorization":f"Bearer {token}"}
    session=client.post("/api/scan",headers=headers,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    return headers,session

def test_navigation_only_for_destination_intent():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    nav=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"从当前位置怎么去电影院？"})
    assert nav.status_code==200
    data=nav.json()["data"]
    assert data["intent"]=="navigation" and data["navigation"]["type"]=="route_animation"
    assert data["navigation"]["destination_store"]["id"]=="s09"
    assert data["navigation"]["nodes"] and data["navigation"]["replayable"] and data["navigation"]["dismissible"]
    ordinary=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"今天有什么优惠？"}).json()["data"]
    assert ordinary["intent"]!="navigation" and "navigation" not in ordinary

def test_merchant_update_is_visible_to_visitors():
    reset_and_seed(); client=TestClient(app); visitor,_=login_scan(client)
    login=client.post("/api/merchant/auth/store-code",json={"store_code":"QD-S01-DEMO"})
    assert login.status_code==200 and login.json()["data"]["role"]=="merchant"
    merchant={"Authorization":f"Bearer {login.json()['data']['token']}"}
    updated=client.patch("/api/merchant/store/status",headers=merchant,json={"open_status":"busy","queue_minutes":36,"seats_available":8})
    assert updated.status_code==200 and updated.json()["data"]["live_queue_minutes"]==36
    public=client.get("/api/stores/s01/public-status",headers=visitor,params={"mall_id":"mall_demo"}).json()["data"]
    assert public["open_status"]=="busy" and public["queue_minutes"]==36

def test_manager_analytics_store_code_and_map_job():
    reset_and_seed(); client=TestClient(app)
    login=client.post("/api/auth/web-login",json={"username":"manager","password":"manager123"})
    headers={"Authorization":f"Bearer {login.json()['data']['token']}"}
    analytics=client.get("/api/manager/analytics",headers=headers,params={"mall_id":"mall_demo","granularity":"month"})
    assert analytics.status_code==200 and analytics.json()["data"]["is_mock"] is True
    created=client.post("/api/manager/stores",headers=headers,json={"mall_id":"mall_demo","name":"新锐品牌店","category":"零售","floor":1,"pos_x":680,"pos_y":610})
    assert created.status_code==200 and created.json()["data"]["store_code"].startswith("QD-")
    job=client.post("/api/manager/maps",headers=headers,json={"mall_id":"mall_demo","source_name":"floor-plan.png"})
    assert job.status_code==200 and job.json()["data"]["requires_manual_review"] is True

def test_role_workspaces_do_not_leak_permissions():
    reset_and_seed(); client=TestClient(app); visitor,_=login_scan(client)
    denied=client.get("/api/manager/analytics",headers=visitor,params={"mall_id":"mall_demo"})
    assert denied.status_code==403
    merchant_login=client.post("/api/merchant/auth/store-code",json={"store_code":"QD-S01-DEMO"}).json()["data"]
    merchant={"Authorization":f"Bearer {merchant_login['token']}"}
    assert client.get("/api/manager/analytics",headers=merchant,params={"mall_id":"mall_demo"}).status_code==403
    manager_login=client.post("/api/auth/web-login",json={"username":"manager","password":"manager123"}).json()["data"]
    manager={"Authorization":f"Bearer {manager_login['token']}"}
    assert client.get("/api/merchant/store",headers=manager).status_code==403
