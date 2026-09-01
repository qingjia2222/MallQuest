from fastapi.testclient import TestClient
from app.db import reset_and_seed
from app.core.map_catalog import stable_store_id
from app.main import app

def login_scan(client):
    token=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]
    headers={"Authorization":f"Bearer {token}"}
    session=client.post("/api/scan",headers=headers,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    return headers,session

def test_navigation_only_for_destination_intent():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    nav=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"从当前位置怎么去川食公馆？"})
    assert nav.status_code==200
    data=nav.json()["data"]
    assert data["intent"]=="navigation" and data["navigation"]["type"]=="route_animation"
    assert data["navigation"]["destination_store"]["id"]==stable_store_id("川食公馆")
    assert data["navigation"]["nodes"] and data["navigation"]["replayable"] and data["navigation"]["dismissible"]
    assert data["navigation"]["vertical_mode"]=="elevator"
    escalator=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"从当前位置怎么走扶梯去川食公馆？"}).json()["data"]
    assert escalator["navigation"]["vertical_mode"]=="escalator"
    assert "乘扶梯前往 2F" in escalator["navigation"]["transfer_instructions"]
    ordinary=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"今天有什么优惠？"}).json()["data"]
    assert ordinary["intent"]!="navigation" and "navigation" not in ordinary

def test_merchant_update_is_visible_to_visitors():
    reset_and_seed(); client=TestClient(app); visitor,_=login_scan(client)
    login=client.post("/api/merchant/auth/store-code",json={"store_code":"QD-S01-DEMO","password":"123456"})
    assert login.status_code==200 and login.json()["data"]["role"]=="merchant"
    merchant={"Authorization":f"Bearer {login.json()['data']['token']}"}
    updated=client.patch("/api/merchant/store/status",headers=merchant,json={"open_status":"busy","queue_minutes":36,"seats_available":8})
    assert updated.status_code==200 and updated.json()["data"]["live_queue_minutes"]==36
    public=client.get(f"/api/stores/{stable_store_id('蜀签成都串串香')}/public-status",headers=visitor,params={"mall_id":"mall_demo"}).json()["data"]
    assert public["open_status"]=="busy" and public["queue_minutes"]==36

def test_merchant_can_publish_voucher_visible_and_claimable_by_visitor():
    reset_and_seed(); client=TestClient(app); visitor,session=login_scan(client)
    login=client.post("/api/merchant/auth/store-code",json={"store_code":"QD-S01-DEMO","password":"123456"}).json()["data"]
    merchant={"Authorization":f"Bearer {login['token']}"}
    created=client.put("/api/merchant/store/coupons",headers=merchant,json={"title":"满30减5","face_value":5,"min_spend":30,"stock":100})
    assert created.status_code==200
    coupon_id=created.json()["data"]["coupon_id"]
    workspace=client.get("/api/merchant/store",headers=merchant).json()["data"]
    assert next(c for c in workspace["coupons"] if c["id"]==coupon_id)["face_value"]==5
    coupons=client.get("/api/coupons",headers=visitor,params={"session_id":session}).json()["data"]
    published=next(c for c in coupons if c["id"]==coupon_id)
    assert published["title"]=="满30减5" and published["min_spend"]==30 and published["store_name"]=="蜀签成都串串香"
    claimed=client.post("/api/coupons/claim",headers=visitor,json={"session_id":session,"coupon_id":coupon_id,"confirmed":True})
    assert claimed.status_code==200 and claimed.json()["data"]["status"]=="success"

def test_merchant_voucher_validation_rejects_invalid_discount():
    reset_and_seed(); client=TestClient(app)
    login=client.post("/api/merchant/auth/store-code",json={"store_code":"QD-S01-DEMO","password":"123456"}).json()["data"]
    merchant={"Authorization":f"Bearer {login['token']}"}
    response=client.put("/api/merchant/store/coupons",headers=merchant,json={"title":"错误券","face_value":30,"min_spend":30,"stock":10})
    assert response.status_code==422

def test_manager_analytics_store_code_and_map_job():
    reset_and_seed(); client=TestClient(app)
    login=client.post("/api/auth/web-login",json={"username":"manager","password":"manager123"})
    headers={"Authorization":f"Bearer {login.json()['data']['token']}"}
    analytics=client.get("/api/manager/analytics",headers=headers,params={"mall_id":"mall_demo","granularity":"month"})
    assert analytics.status_code==200 and analytics.json()["data"]["is_mock"] is True
    periods={grain:client.get("/api/manager/analytics",headers=headers,params={"mall_id":"mall_demo","granularity":grain}).json()["data"] for grain in ("day","month","year")}
    assert {periods[grain]["granularity_label"] for grain in periods}=={"日度","月度","年度"}
    assert len({periods[grain]["current"]["footfall"] for grain in periods})==3
    assert all(periods[grain]["period_range"] and periods[grain]["current_label"] for grain in periods)
    rejected=client.post("/api/manager/stores",headers=headers,json={"mall_id":"mall_demo","name":"新锐品牌店","category":"零售","floor":1,"pos_x":680,"pos_y":610})
    assert rejected.status_code==409
    created=client.post("/api/manager/stores",headers=headers,json={"mall_id":"mall_demo","name":"蜀签成都串串香","category":"餐饮","floor":1,"pos_x":680,"pos_y":610})
    assert created.status_code==200 and created.json()["data"]["store_code"]=="QD-S01-DEMO"
    job=client.post("/api/manager/maps",headers=headers,json={"mall_id":"mall_demo","source_name":"floor-plan.png"})
    assert job.status_code==200 and job.json()["data"]["requires_manual_review"] is True

def test_plan_coupon_unavailable_returns_specific_customer_reason():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    offered=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"帮我领取爪财猫寿司的优惠券"})
    assert offered.status_code==200
    plan=offered.json()["data"]["plan"]
    done=client.post("/api/plan/confirm",headers=headers,json={"plan_id":plan["plan_id"],"decision":"confirm","expected_revision":plan["revision"]})
    assert done.status_code==200
    action=next(item for item in done.json()["data"]["action_results"] if item["tool"]=="claim_coupon")
    assert action["status"]=="unavailable"
    assert action["reason_code"]=="coupon_not_published"
    assert "爪财猫寿司" in action["reason"] and "没有对应优惠券" in action["reason"]

def test_party_a_map_geometry_is_merged_with_backend_store_data():
    reset_and_seed(); client=TestClient(app); headers,_=login_scan(client)
    response=client.get("/api/maps/mall_demo/scene",headers=headers)
    assert response.status_code==200
    stores=response.json()["data"]["stores"]
    facilities=response.json()["data"]["facilities"]
    assert len(stores)==43
    assert all(s["map_source"]=="party_a_mall_ring" for s in stores)
    assert not any(s["name"]=="蜀香小院" for s in stores)
    assert all("reservable" in s for s in stores) and any(int(s["reservable"]) for s in stores)
    target=next(s for s in stores if s["id"]==stable_store_id("蜀签成都串串香"))
    assert target["name"]=="蜀签成都串串香" and target["map_slot"].startswith("corner_f1")
    assert target["store_code"]=="QD-S01-DEMO"
    required={("卫生间",1),("卫生间",2),("消防兼安保",2),("有线电视",2),("服务台",1),("瀑布厅",1),("儿童乐园",2),("美食广场",2),("直梯",1),("直梯",2),("扶梯",1),("扶梯",2)}
    assert required.issubset({(item["name"],item["floor"]) for item in facilities})

def test_store_code_resolves_to_the_same_customer_store_and_llm_answer():
    reset_and_seed(); client=TestClient(app); headers,session=login_scan(client)
    stores=client.get("/api/stores",headers=headers,params={"session_id":session}).json()["data"]
    target_id=stable_store_id("蜀签成都串串香")
    assert next(s for s in stores if s["id"]==target_id)["store_code"]=="QD-S01-DEMO"
    chat=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"QD-S01-DEMO 是哪家店？"}).json()["data"]
    assert chat["result"][0]["id"]==target_id and chat["result"][0]["name"]=="蜀签成都串串香"
    assert "QD-S01-DEMO" in chat["reply"] and "蜀签成都串串香" in chat["reply"]
    nav=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"怎么去 QD-S01-DEMO？"}).json()["data"]
    assert nav["intent"]=="navigation" and nav["navigation"]["destination_store"]["id"]==target_id
    assert nav["navigation"]["path_policy"]=="corridor_only"

def test_role_workspaces_do_not_leak_permissions():
    reset_and_seed(); client=TestClient(app); visitor,_=login_scan(client)
    denied=client.get("/api/manager/analytics",headers=visitor,params={"mall_id":"mall_demo"})
    assert denied.status_code==403
    merchant_login=client.post("/api/merchant/auth/store-code",json={"store_code":"QD-S01-DEMO","password":"123456"}).json()["data"]
    merchant={"Authorization":f"Bearer {merchant_login['token']}"}
    assert client.get("/api/manager/analytics",headers=merchant,params={"mall_id":"mall_demo"}).status_code==403
    manager_login=client.post("/api/auth/web-login",json={"username":"manager","password":"manager123"}).json()["data"]
    manager={"Authorization":f"Bearer {manager_login['token']}"}
    assert client.get("/api/merchant/store",headers=manager).status_code==403

def test_manager_can_maintain_versioned_prompt_files_without_touching_business_db(tmp_path,monkeypatch):
    from app.api import prompt_admin
    for filename in prompt_admin.PROMPT_FILES.values():
        (tmp_path/filename).write_text("# 测试提示词\n这是独立目录中的可维护内容。\n",encoding="utf-8")
    monkeypatch.setattr(prompt_admin,"PROMPTS_DIR",tmp_path)
    reset_and_seed(); client=TestClient(app)
    visitor,_=login_scan(client)
    assert client.get("/api/manager/prompts",headers=visitor).status_code==403
    login=client.post("/api/auth/web-login",json={"username":"manager","password":"manager123"}).json()["data"]
    manager={"Authorization":f"Bearer {login['token']}"}
    current=client.get("/api/manager/prompts/system",headers=manager).json()["data"]
    updated=client.put("/api/manager/prompts/system",headers=manager,json={"content":"# 新系统提示词\n由管理员维护，业务事实仍由工具提供。","expected_revision":current["revision"]})
    assert updated.status_code==200 and updated.json()["data"]["revision"]!=current["revision"]
    assert list((tmp_path/"backups"/"system").glob("*.md"))
    restored=client.post("/api/manager/prompts/system/restore-latest",headers=manager,json={"expected_revision":updated.json()["data"]["revision"]})
    assert restored.status_code==200 and restored.json()["data"]["content"]==current["content"]
    conflict=client.put("/api/manager/prompts/system",headers=manager,json={"content":"# 冲突版本\n这次保存应当被拒绝以防覆盖。","expected_revision":updated.json()["data"]["revision"]})
    assert conflict.status_code==409
