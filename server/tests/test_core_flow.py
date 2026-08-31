from fastapi.testclient import TestClient
from app.db import connection, reset_and_seed
from app.main import app
from app.core.auth import decode_token
from app.core.text import plain_text
def setup_module(): reset_and_seed()
def login_scan(client,mall="mall_demo"):
    token=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]; h={"Authorization":f"Bearer {token}"}; session=client.post("/api/scan",headers=h,json={"mall_id":mall}).json()["data"]["session_id"]; return h,session
def test_auth_scan_envelope_queries_rag_tools_and_tts():
    c=TestClient(app); wx=c.post("/api/auth/wx-login",json={"code":"mock-demo"}); assert wx.status_code==200 and wx.json()["data"]["user_id"]=="user_demo"
    h,s=login_scan(c); parking=c.get("/api/parking",headers=h,params={"session_id":s}); assert set(parking.json())=={"code","message","request_id","timestamp","data"}; assert parking.json()["data"]["total_free"]==247
    points=c.get("/api/member/points",headers=h,params={"session_id":s}); assert points.json()["data"]["points"]==2680
    rag=c.post("/api/chat",headers=h,json={"session_id":s,"message":"积分多久过期？"}); assert rag.json()["data"]["result"]["sources"]
    assert c.get("/api/tools/schema",headers=h).json()["data"]
    tts=c.post("/api/tts",headers=h,json={"text":"欢迎来到 星河里"}); assert tts.status_code==200; assert c.get(tts.json()["data"]["audio_url"]).status_code==200
def test_mall_isolation():
    c=TestClient(app); h,s=login_scan(c,"mall_alt"); parking=c.get("/api/parking",headers=h,params={"session_id":s}).json()["data"]; assert parking["total_free"]==21; assert all(a["area"]=="地面停车区" for a in parking["areas"])

def test_visitor_phone_login_and_ai_service_qr_binding():
    reset_and_seed(); c=TestClient(app)
    login=c.post("/api/auth/phone-login",json={"phone":"11111111111","password":"123456"})
    assert login.status_code==200 and login.json()["data"]["phone_masked"]=="111****1111"
    token=login.json()["data"]["token"]; assert decode_token(token).login_channel=="phone"
    headers={"Authorization":f"Bearer {token}"}
    scanned=c.post("/api/scan",headers=headers,json={"mall_id":"mall_alt","service_code":"QD-AI-DEMO"})
    data=scanned.json()["data"]
    assert data["mall_id"]=="mall_demo" and data["entry_source"]=="ai_service_qr"
    assert data["datasource_connection"]["status"]=="connected" and len(data["datasource_connection"]["sources"])==5
    assert c.post("/api/scan",headers=headers,json={"service_code":"NOT-VALID"}).status_code==404
    assert c.post("/api/auth/phone-login",json={"phone":"111","password":"123456"}).status_code==422

def test_ai_plain_text_removes_markdown_stars():
    assert plain_text("**木棉亲子餐厅** 等候约 **10 分钟**")=="木棉亲子餐厅 等候约 10 分钟"

def test_queue_question_returns_ranked_nonempty_card():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    response=c.post("/api/chat",headers=h,json={"session_id":s,"message":"有哪些店需要排队？"})
    data=response.json()["data"]
    assert data["intent"]=="query_queue_status" and data["cards"][0]["type"]=="queue"
    rows=data["cards"][0]["data"]
    assert rows and all(row["queue_minutes"]>0 for row in rows)
    assert [row["queue_minutes"] for row in rows]==sorted((row["queue_minutes"] for row in rows),reverse=True)

def test_chinese_people_slot_reaches_confirmation():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    response=c.post("/api/chat",headers=h,json={"session_id":s,"message":"今晚7点两个人约会，人均250，想吃川菜，还想看电影。"})
    plan=response.json()["data"]["plan"]
    assert plan["state"]=="CONFIRM" and plan["slots"]["people"]==2

def test_explicit_store_reservation_uses_store_entity_and_confirmation_gate():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    response=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我预约沃德面包"})
    assert response.status_code==200
    data=response.json()["data"]
    assert data["intent"]=="plan" and data["source"]=="transaction_router"
    assert data["plan"]["state"]=="CONFIRM"
    assert [store["name"] for store in data["plan"]["itinerary"]]==["沃德面包"]
    assert data["plan"]["slots"]["requested_actions"]==["reserve_restaurant"]
    with connection() as db:
        before=db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    confirmed=c.post("/api/plan/confirm",headers=h,json={"plan_id":data["plan"]["plan_id"],"decision":"confirm","expected_revision":data["plan"]["revision"]})
    assert confirmed.status_code==200
    result=confirmed.json()["data"]
    assert any(item["tool"]=="reserve_restaurant" and item["status"]=="success" for item in result["action_results"])
    with connection() as db:
        after=db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    assert after==before+1

def test_every_reservable_store_can_be_selected_by_llm_reservation_command():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    with connection() as db:
        stores=[dict(row) for row in db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo' AND reservable=1 AND category!='服务台' ORDER BY id")]
    assert stores
    for store in stores:
        response=c.post("/api/chat",headers=h,json={"session_id":s,"message":f"帮我预约{store['name']}"})
        assert response.status_code==200,store["name"]
        plan=response.json()["data"]["plan"]
        assert plan["state"]=="CONFIRM",store["name"]
        assert [item["id"] for item in plan["itinerary"]]==[store["id"]],store["name"]
        assert plan["slots"]["requested_actions"]==["reserve_restaurant"],store["name"]

def test_movie_ticket_skill_stays_disabled_without_a_mapped_cinema():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    response=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我买电影票"})
    data=response.json()["data"]
    assert data["intent"]=="movie_ticket_unavailable" and "没有电影院" in data["reply"]
    assert "plan" not in data

def test_llm_coupon_and_deal_purchase_skills_use_confirmation_plans():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    with connection() as db:
        coupon_store=db.execute("SELECT s.name FROM coupons c JOIN stores s ON s.id=c.store_id WHERE c.mall_id='mall_demo' AND c.stock>0 LIMIT 1").fetchone()[0]
        deal_store=db.execute("SELECT s.name FROM deals d JOIN stores s ON s.id=d.store_id WHERE d.mall_id='mall_demo' AND d.stock>0 LIMIT 1").fetchone()[0]
    for message,tool in ((f"帮我领取{coupon_store}的优惠券","claim_coupon"),(f"帮我抢购{deal_store}的特惠","purchase_deal")):
        offered=c.post("/api/chat",headers=h,json={"session_id":s,"message":message}).json()["data"]
        assert offered["intent"]=="plan" and offered["plan"]["state"]=="CONFIRM"
        plan=offered["plan"]
        done=c.post("/api/plan/confirm",headers=h,json={"plan_id":plan["plan_id"],"decision":"confirm","expected_revision":plan["revision"]})
        assert done.status_code==200
        assert any(item["tool"]==tool and item["status"] in {"success","already_claimed"} for item in done.json()["data"]["action_results"])
