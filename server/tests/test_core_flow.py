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

def test_online_plan_reply_is_rendered_from_validated_plan_not_mismatched_llm_prose(monkeypatch):
    from app.api import chat as chat_api
    from app.core.map_catalog import stable_store_id
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    target=stable_store_id("途尚咖啡")
    monkeypatch.setattr(chat_api,"try_online_planning",lambda *_args,**_kwargs:{
        "reply":"我给你安排了五站，其中包括大众书局和米芝莲。",
        "plan_json":{"scene":"date","slots":{"time":"14:00","people":2,"want_movie":False},"store_ids":[target],"time_plan":{target:"14:00"},"reason_by_store":{target:"适合先坐下聊聊"}},
        "tool_calls":[]})
    data=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我规划约会"}).json()["data"]
    assert [item["name"] for item in data["plan"]["itinerary"]]==["途尚咖啡"]
    assert "途尚咖啡" in data["reply"] and "大众书局" not in data["reply"] and "米芝莲" not in data["reply"]
    assert "文字、方案卡片和地图路线来自同一份已校验结果" in data["reply"]

def test_llm_plan_patch_preserves_unmentioned_stops_and_adds_one_timed_activity(monkeypatch):
    from app.api import chat as chat_api
    reset_and_seed();c=TestClient(app);h,s=login_scan(c)
    with connection() as db:
        rows=db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo'").fetchall();ids={row["name"]:row["id"] for row in rows}
        restaurants=db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo' AND category='餐饮' ORDER BY queue_minutes,id LIMIT 2").fetchall()
    # Preserve a semantically valid mixed itinerary; three consecutive dessert
    # stops are intentionally rejected by the activity-diversity validator.
    base_names=["途尚咖啡","大众书局","米芝莲"]
    def fake_planner(message,*_args,**_kwargs):
        if "增加" in message:
            candidate_ids=[row["id"] for row in restaurants]
            return {"reply":"","plan_json":{"scene":"date","slots":{"time":"19:00"},"store_ids":candidate_ids,"time_plan":{store_id:"19:00" for store_id in candidate_ids},"reason_by_store":{candidate_ids[0]:"结合排队、余位与晚餐需求选出的正式入选店"}},"tool_calls":[]}
        return {"reply":"","plan_json":{"mode":"new","scene":"date","slots":{"time":"14:00","people":2,"want_movie":False},"store_ids":[ids[name] for name in base_names],"time_plan":{ids[base_names[0]]:"14:00",ids[base_names[1]]:"14:45",ids[base_names[2]]:"15:30"}},"tool_calls":[]}
    monkeypatch.setattr(chat_api,"try_online_planning",fake_planner)
    original=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我规划约会"}).json()["data"]["plan"]
    changed=c.post("/api/chat",headers=h,json={"session_id":s,"message":"在这个方案基础上增加一项活动，19:00吃饭，餐厅你来推荐"}).json()["data"]
    itinerary=changed["plan"]["itinerary"]
    assert [item["id"] for item in itinerary[:3]]==[item["id"] for item in original["itinerary"]]
    assert [item["time_label"] for item in itinerary[:3]]==["14:00","14:45","15:30"]
    assert len(itinerary)==4 and itinerary[-1]["id"]==restaurants[0]["id"] and itinerary[-1]["time_label"]=="19:00"
    assert changed["plan"]["slots"]["time"]==original["slots"]["time"]=="14:00"
    assert len({item["time_label"] for item in itinerary})==len(itinerary)
    assert "保留未被你点名修改的内容" in changed["reply"]

def test_planner_never_keeps_two_stops_at_the_same_arrival_time(monkeypatch):
    from app.api import chat as chat_api
    reset_and_seed();c=TestClient(app);h,s=login_scan(c)
    with connection() as db:rows=db.execute("SELECT id FROM stores WHERE mall_id='mall_demo' AND category='餐饮' ORDER BY id LIMIT 2").fetchall()
    store_ids=[row["id"] for row in rows]
    monkeypatch.setattr(chat_api,"try_online_planning",lambda *_args,**_kwargs:{"reply":"","plan_json":{"mode":"new","scene":"date","slots":{"time":"19:00","people":2,"want_movie":False},"store_ids":store_ids,"time_plan":{store_id:"19:00" for store_id in store_ids}},"tool_calls":[]})
    plan=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我规划晚餐"}).json()["data"]["plan"]
    assert [item["time_label"] for item in plan["itinerary"]]==["19:00","19:45"]

def test_llm_generic_patch_operations_cover_replace_move_time_people_and_remove(monkeypatch):
    from app.api import chat as chat_api
    reset_and_seed();c=TestClient(app);h,s=login_scan(c)
    with connection() as db:
        rows=db.execute("SELECT id,name FROM stores WHERE mall_id='mall_demo'").fetchall();ids={row["name"]:row["id"] for row in rows}
    first,second,replacement="途尚咖啡","满记甜品","大众书局"
    def fake_planner(message,*_args,**_kwargs):
        if "替换" in message:return {"reply":"","plan_json":{"mode":"patch","operations":[{"op":"replace","target_store_ids":[ids[first]],"replacement_store_ids":[ids[replacement]]}]},"tool_calls":[]}
        if "第一" in message:return {"reply":"","plan_json":{"mode":"patch","operations":[{"op":"move","store_ids":[ids[replacement]],"position":"first"},{"op":"set_time","store_ids":[ids[replacement]],"time":"16:00"},{"op":"update_slots","slots":{"people":4}}]},"tool_calls":[]}
        if "删掉" in message:return {"reply":"","plan_json":{"mode":"patch","operations":[{"op":"remove","store_ids":[ids[replacement]]}]},"tool_calls":[]}
        return {"reply":"","plan_json":{"mode":"new","scene":"date","slots":{"time":"14:00","people":2,"want_movie":False},"store_ids":[ids[first],ids[second]],"time_plan":{ids[first]:"14:00",ids[second]:"14:45"}},"tool_calls":[]}
    monkeypatch.setattr(chat_api,"try_online_planning",fake_planner)
    c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我规划约会"})
    replaced=c.post("/api/chat",headers=h,json={"session_id":s,"message":f"把{first}替换成{replacement}"}).json()["data"]["plan"]
    assert [item["name"] for item in replaced["itinerary"]]==[replacement,second]
    moved=c.post("/api/chat",headers=h,json={"session_id":s,"message":f"把{replacement}放第一，改到16:00，改为4个人"}).json()["data"]["plan"]
    assert moved["itinerary"][0]["name"]==replacement and moved["itinerary"][0]["time_label"]=="16:00" and moved["slots"]["people"]==4
    removed=c.post("/api/chat",headers=h,json={"session_id":s,"message":f"删掉{replacement}"}).json()["data"]["plan"]
    assert [item["name"] for item in removed["itinerary"]]==[second]

def test_conversation_can_add_reorder_remove_places_and_change_start_time():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    original=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我规划约会"}).json()["data"]["plan"]
    assert all(item["name"]!="大众书局" for item in original["itinerary"])
    added=c.post("/api/chat",headers=h,json={"session_id":s,"message":"在当前方案加上大众书局"}).json()["data"]
    assert added["source"]=="validated_plan" and any(item["name"]=="大众书局" for item in added["plan"]["itinerary"])
    ordered=c.post("/api/chat",headers=h,json={"session_id":s,"message":"把大众书局放第一站，并把开始时间改成晚上8点"}).json()["data"]
    assert ordered["plan"]["itinerary"][0]["name"]=="大众书局" and ordered["plan"]["slots"]["time"]=="晚上8点"
    removed=c.post("/api/chat",headers=h,json={"session_id":s,"message":"删掉大众书局"}).json()["data"]
    assert all(item["name"]!="大众书局" for item in removed["plan"]["itinerary"])
    shorter=c.post("/api/chat",headers=h,json={"session_id":s,"message":"这个方案少走路，尽量别绕路"}).json()["data"]
    assert shorter["plan"]["route"]["selected_strategy"]=="shortest"
    comparison=c.post("/api/chat",headers=h,json={"session_id":s,"message":"把最近两个方案放在一起比较"}).json()["data"]
    assert comparison["intent"]=="compare_plans" and "方案1" in comparison["reply"] and "方案2" in comparison["reply"]

def test_reservation_api_supports_confirmed_time_and_people_changes():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    with connection() as db: store=db.execute("SELECT id FROM stores WHERE mall_id='mall_demo' AND reservable=1 ORDER BY id LIMIT 1").fetchone()
    created=c.post("/api/reservations",headers=h,json={"session_id":s,"store_id":store["id"],"reserved_for":"今晚 19:00","people":2,"confirmed":True}).json()["data"]
    reservation_id=created["reservation_id"]
    assert c.patch(f"/api/reservations/{reservation_id}",headers=h,json={"reserved_for":"今晚 20:30","people":4}).status_code==409
    updated=c.patch(f"/api/reservations/{reservation_id}",headers=h,json={"reserved_for":"今晚 20:30","people":4,"confirmed":True})
    assert updated.status_code==200
    data=updated.json()["data"]
    assert data["reserved_for"]=="今晚 20:30" and data["people"]==4 and data["store_name"]
    people_only=c.patch(f"/api/reservations/{reservation_id}",headers=h,json={"people":5,"confirmed":True}).json()["data"]
    assert people_only["people"]==5 and people_only["reserved_for"]=="今晚 20:30"

def test_llm_can_confirm_create_change_people_and_time_then_cancel_reservation():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    offered=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我预约沃德面包，3个人，晚上7点"}).json()["data"]["plan"]
    assert offered["slots"]["people"]==3 and offered["slots"]["time"]=="晚上7点"
    done=c.post("/api/plan/confirm",headers=h,json={"plan_id":offered["plan_id"],"decision":"confirm","expected_revision":offered["revision"]})
    assert done.status_code==200
    with connection() as db:
        reservation=db.execute("""SELECT r.* FROM reservations r JOIN stores s ON s.id=r.store_id
          WHERE r.user_id='user_demo' AND s.name='沃德面包' AND r.status!='cancelled' ORDER BY r.created_at DESC LIMIT 1""").fetchone()
    changed=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我更改沃德面包预约为4个人，晚上8点"}).json()["data"]["plan"]
    assert changed["slots"]["requested_actions"]==["update_reservation"] and changed["slots"]["target_reservation_id"]==reservation["id"]
    changed_done=c.post("/api/plan/confirm",headers=h,json={"plan_id":changed["plan_id"],"decision":"confirm","expected_revision":changed["revision"]})
    assert changed_done.status_code==200
    with connection() as db:
        updated=db.execute("SELECT * FROM reservations WHERE id=?",(reservation["id"],)).fetchone()
        active_count=db.execute("SELECT COUNT(*) FROM reservations WHERE id=? AND status!='cancelled'",(reservation["id"],)).fetchone()[0]
    assert updated["people"]==4 and updated["reserved_for"]=="晚上8点" and active_count==1
    people_change=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我更改沃德面包预约为5个人"}).json()["data"]["plan"]
    people_done=c.post("/api/plan/confirm",headers=h,json={"plan_id":people_change["plan_id"],"decision":"confirm","expected_revision":people_change["revision"]})
    assert people_done.status_code==200
    with connection() as db:
        people_updated=db.execute("SELECT * FROM reservations WHERE id=?",(reservation["id"],)).fetchone()
    assert people_updated["people"]==5 and people_updated["reserved_for"]=="晚上8点"
    cancelled=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我取消沃德面包的预约"}).json()["data"]["plan"]
    assert cancelled["slots"]["requested_actions"]==["cancel_reservation"]
    cancelled_done=c.post("/api/plan/confirm",headers=h,json={"plan_id":cancelled["plan_id"],"decision":"confirm","expected_revision":cancelled["revision"]})
    assert cancelled_done.status_code==200
    with connection() as db: assert db.execute("SELECT status FROM reservations WHERE id=?",(reservation["id"],)).fetchone()[0]=="cancelled"

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
    assert data["intent"]=="movie_ticket_unavailable" and "暂时无电影院设施" in data["reply"]
    assert "plan" not in data

def test_cinema_is_only_mentioned_for_explicit_cinema_intent():
    reset_and_seed(); c=TestClient(app); h,s=login_scan(c)
    ordinary=c.post("/api/chat",headers=h,json={"session_id":s,"message":"帮我规划约会"}).json()["data"]
    assert ordinary["intent"]=="plan"
    assert ordinary["plan"]["slots"].get("want_movie") is False
    assert all(item.get("category")!="影院" for item in ordinary["plan"]["itinerary"])
    assert "电影院" not in ordinary["reply"] and "影院" not in ordinary["reply"]
    explicit=c.post("/api/chat",headers=h,json={"session_id":s,"message":"这个商场有电影院吗？"}).json()["data"]
    assert explicit["intent"]=="cinema_unavailable"
    assert explicit["reply"]=="本商城暂时无电影院设施，即将开业敬请期待。"

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
