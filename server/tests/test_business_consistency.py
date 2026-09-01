from fastapi.testclient import TestClient

from app.core.tools import run_tool
from app.db import reset_and_seed
from app.main import app


def login_scan(client):
    token=client.post("/api/auth/web-login",json={"username":"demo","password":"demo123"}).json()["data"]["token"]
    headers={"Authorization":f"Bearer {token}"}
    session=client.post("/api/scan",headers=headers,json={"mall_id":"mall_demo"}).json()["data"]["session_id"]
    return headers,session,"u_demo"


def test_reservable_store_ui_api_tool_and_chat_share_exact_ids():
    reset_and_seed(); client=TestClient(app); headers,session,user_id=login_scan(client)
    api_rows=client.get("/api/stores",headers=headers,params={"session_id":session,"reservable_only":True}).json()["data"]
    tool_rows=run_tool("query_reservable_stores",{"mall_id":"mall_demo","user_id":user_id,"session_id":session},{})
    assert [row["id"] for row in api_rows]==[row["id"] for row in tool_rows]
    assert api_rows and all(int(row["reservable"])==1 for row in api_rows)
    for message in ("有哪些店铺可以预约？","都有什么餐厅支持预约？","我能预订哪家店？"):
        data=client.post("/api/chat",headers=headers,json={"session_id":session,"message":message}).json()["data"]
        assert data["intent"]=="query_reservable_stores",message
        assert [row["id"] for row in data["result"]]==[row["id"] for row in api_rows]
        assert f"当前共有{len(api_rows)}家店铺开放预约" in data["reply"]


def test_reservable_capability_and_my_reservation_orders_never_cross():
    reset_and_seed(); client=TestClient(app); headers,session,_=login_scan(client)
    available=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"哪些店可以预约"}).json()["data"]
    mine=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"我现在有哪些预约"}).json()["data"]
    assert available["intent"]=="query_reservable_stores" and available["result"]
    assert mine["intent"]=="query_my_reservations" and mine["result"]==[]


def test_available_coupon_deal_parking_and_points_queries_match_public_apis():
    reset_and_seed(); client=TestClient(app); headers,session,_=login_scan(client)
    cases=(
        ("现在有哪些优惠券可以领？","query_available_coupons","/api/coupons",lambda rows:[r for r in rows if r["stock"]>0]),
        ("今天有什么优惠套餐？","get_today_deals","/api/deals",lambda rows:[r for r in rows if r["stock"]>0]),
    )
    for message,intent,path,available in cases:
        page=client.get(path,headers=headers,params={"session_id":session}).json()["data"]
        chat=client.post("/api/chat",headers=headers,json={"session_id":session,"message":message}).json()["data"]
        assert chat["intent"]==intent
        assert [r["id"] for r in chat["result"]]==[r["id"] for r in available(page)]
    parking=client.get("/api/parking",headers=headers,params={"session_id":session}).json()["data"]
    parking_chat=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"停车场现在还有多少空位？"}).json()["data"]
    assert parking_chat["result"]==parking
    points=client.get("/api/member/points",headers=headers,params={"session_id":session}).json()["data"]
    points_chat=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"我现在有多少积分？"}).json()["data"]
    assert points_chat["result"]==points


def test_map_home_catalog_and_chat_use_same_store_status_snapshot():
    reset_and_seed(); client=TestClient(app); headers,session,_=login_scan(client)
    stores=client.get("/api/stores",headers=headers,params={"session_id":session}).json()["data"]
    scene=client.get("/api/maps/mall_demo/scene",headers=headers).json()["data"]["stores"]
    by_id={row["id"]:row for row in stores}; scene_by_id={row["id"]:row for row in scene}
    assert set(by_id)==set(scene_by_id)
    for store_id,row in by_id.items():
        mapped=scene_by_id[store_id]
        assert (mapped["reservable"],mapped["open_status"],mapped["queue_minutes"],mapped["seats_available"])==(row["reservable"],row["open_status"],row["queue_minutes"],row["seats_available"])
    chat=client.post("/api/chat",headers=headers,json={"session_id":session,"message":"商场都有什么店铺？"}).json()["data"]
    assert chat["intent"]=="search_stores"
    assert [row["id"] for row in chat["result"]]==[row["id"] for row in stores]
