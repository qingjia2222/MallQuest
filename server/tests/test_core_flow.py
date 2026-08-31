from fastapi.testclient import TestClient
from app.db import reset_and_seed
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
    tts=c.post("/api/tts",headers=h,json={"text":"欢迎来到 QD square"}); assert tts.status_code==200; assert c.get(tts.json()["data"]["audio_url"]).status_code==200
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
