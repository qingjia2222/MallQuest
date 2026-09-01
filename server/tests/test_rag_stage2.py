from fastapi.testclient import TestClient

from app.core.rag import NO_EVIDENCE, answer, knowledge_status, retrieve
from app.db import reset_and_seed
from app.main import app


def login_scan(client):
    token=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]
    headers={"Authorization":f"Bearer {token}"}
    session=client.post("/api/scan",headers=headers,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    return headers,session


def test_knowledge_catalog_and_topic_retrieval_are_mall_scoped():
    status=knowledge_status("mall_demo")
    assert status["documents"]>=8 and status["chunks"]>=20
    assert {"points","membership","coupon","reservation","parking","service","visitor"}<=set(status["topics"])
    cases=(
        ("积分多久过期","points","积分有效期"),
        ("预约迟到怎么办","reservation","迟到与留位"),
        ("停车怎么收费","parking","收费与减免"),
        ("洗手间在哪里","service","卫生间"),
        ("优惠券能和套餐叠加吗","coupon","叠加与退款"),
    )
    for query,topic,section in cases:
        result=answer(query,"mall_demo",topic)
        assert result["answer"]!=NO_EVIDENCE
        assert result["sources"][0]["topic"]==topic and result["sources"][0]["section"]==section
        assert result["sources"][0]["version"] and result["sources"][0]["authority"]
    assert answer("积分多久过期","mall_alt","points")["answer"]==NO_EVIDENCE
    assert not retrieve("积分多久过期","mall_alt",topic="points")


def test_policy_question_uses_rag_instead_of_starting_a_reservation():
    reset_and_seed();client=TestClient(app);headers,session=login_scan(client)
    data=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"预约迟到了怎么办？"}).json()["data"]
    assert data["intent"]=="search_mall_knowledge"
    assert data["result"]["topic"]=="reservation"
    assert data["result"]["sources"][0]["section"]=="迟到与留位"
    assert "知识库" not in data["reply"] and "本商城暂未设置" in data["reply"]
    assert "plan" not in data


def test_hybrid_questions_combine_rag_rules_with_sqlite_facts():
    reset_and_seed();client=TestClient(app);headers,session=login_scan(client)
    parking=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"停车怎么收费，现在还有多少空位？"}).json()["data"]
    assert parking["intent"]=="knowledge_hybrid"
    assert [call["name"] for call in parking["tool_calls"]]==["search_mall_knowledge","query_parking_status"]
    assert parking["result"]["knowledge"]["topic"]=="parking"
    assert parking["result"]["live"]["total_free"]==247
    coupons=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"优惠券怎么用，今天有哪些可以领？"}).json()["data"]
    assert coupons["intent"]=="knowledge_hybrid"
    assert [call["name"] for call in coupons["tool_calls"]]==["search_mall_knowledge","query_available_coupons"]
    assert coupons["result"]["live"] and all(item["stock"]>0 for item in coupons["result"]["live"])


def test_live_only_question_still_uses_existing_sqlite_route():
    reset_and_seed();client=TestClient(app);headers,session=login_scan(client)
    data=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"停车还有空位吗？"}).json()["data"]
    assert data["intent"]=="query_parking_status"
    assert data["result"]["total_free"]==247


def test_tool_schema_keeps_legacy_rag_and_adds_general_knowledge_tools():
    reset_and_seed();client=TestClient(app);headers,_=login_scan(client)
    names={item["name"] for item in client.get("/api/tools/schema",headers=headers).json()["data"]}
    assert {"query_points_rules","search_mall_knowledge","query_available_coupons","query_my_reservations"}<=names


def test_rag_content_cannot_turn_a_rule_question_into_a_write_action():
    reset_and_seed();client=TestClient(app);headers,session=login_scan(client)
    data=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"积分规则里即使出现忽略系统规则，也不能直接帮我领券，对吗？"}).json()["data"]
    assert data["intent"]=="search_mall_knowledge"
    assert all(call["name"] in {"search_mall_knowledge","query_points_rules"} for call in data["tool_calls"])
    assert "plan" not in data


def test_current_reservations_is_a_read_query_not_a_create_intent():
    reset_and_seed();client=TestClient(app);headers,session=login_scan(client)
    empty=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"我现在有哪些预约？"}).json()["data"]
    assert empty["intent"]=="query_my_reservations" and empty["result"]==[]
    assert empty["reply"]=="你当前没有有效预约。" and not empty["cards"]
    from app.db import connection
    with connection() as db:
        store=db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo' AND reservable=1 ORDER BY id LIMIT 1").fetchone()
    created=client.post("/api/reservations",headers=headers,json={"session_id":session,"store_id":store["id"],"reserved_for":"今晚19:00","people":3,"confirmed":True})
    assert created.status_code==200
    populated=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"查看我的预约记录"}).json()["data"]
    assert populated["intent"]=="query_my_reservations" and len(populated["result"])==1
    assert store["name"] in populated["reply"] and "今晚19:00" in populated["reply"] and "3人" in populated["reply"]
    assert "店铺搜索结果" not in populated["reply"]


def test_read_write_intent_gate_handles_question_variants_without_false_transactions():
    reset_and_seed();client=TestClient(app);headers,session=login_scan(client)
    questions=("预约怎么取消？","预约能改人数吗？","优惠券怎么领取？","可以预约哪些餐厅？")
    for message in questions:
        data=client.post("/api/chat",headers=headers,json={"session_id":session,"message":message}).json()["data"]
        assert data["intent"]!="plan",message
        assert "plan" not in data,message
    command=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"帮我预约沃德面包，3个人，晚上7点"}).json()["data"]
    assert command["intent"]=="plan" and command["plan"]["state"]=="CONFIRM"
