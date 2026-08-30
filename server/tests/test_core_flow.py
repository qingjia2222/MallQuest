from fastapi.testclient import TestClient
from app.db import reset_and_seed
from app.main import app
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

def test_chinese_people_slot_reaches_confirmation():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    response=c.post("/api/chat",headers=h,json={"session_id":s,"message":"今晚7点两个人约会，人均250，想吃川菜，还想看电影。"})
    plan=response.json()["data"]["plan"]
    assert plan["state"]=="CONFIRM" and plan["slots"]["people"]==2
