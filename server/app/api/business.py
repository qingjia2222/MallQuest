import json, re, uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from app.core.auth import AuthContext, require_auth
from app.core.business_data import list_coupons, list_deals, list_reservations, list_stores
from app.core.envelope import envelope
from app.core.planner import _claim
from app.core.tools import get_today_deals, query_member_points, query_parking_status, schemas
from app.db import connection, now_iso, rows_to_dicts

router=APIRouter(tags=["business"])
def mall_for(auth,session_id):
    with connection() as db: row=db.execute("SELECT mall_id FROM sessions WHERE id=? AND user_id=?",(session_id,auth.user_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="session not found")
    return row["mall_id"]
@router.get("/parking")
def parking(session_id:str,auth:AuthContext=Depends(require_auth)): return envelope(query_parking_status(mall_id=mall_for(auth,session_id)))
@router.get("/member/points")
def points(session_id:str,auth:AuthContext=Depends(require_auth)): return envelope(query_member_points(mall_id=mall_for(auth,session_id),user_id=auth.user_id))
@router.get("/deals")
def deals(session_id:str,auth:AuthContext=Depends(require_auth)):
    mall=mall_for(auth,session_id)
    return envelope(list_deals(mall,auth.user_id))
@router.get("/tools/schema")
def tools(auth:AuthContext=Depends(require_auth)): return envelope(schemas())
class ClaimBody(BaseModel): session_id:str; coupon_id:str; confirmed:bool=False
@router.post("/coupons/claim")
def claim(body:ClaimBody,auth:AuthContext=Depends(require_auth)):
    if not body.confirmed: raise HTTPException(status_code=409,detail="explicit confirmation required")
    mall=mall_for(auth,body.session_id)
    with connection() as db: result=_claim(db,auth.user_id,mall,body.coupon_id)
    return envelope(result)
@router.get("/coupons")
def coupons(session_id:str,auth:AuthContext=Depends(require_auth)):
    mall=mall_for(auth,session_id)
    return envelope(list_coupons(mall,auth.user_id))

class PurchaseBody(BaseModel): session_id:str; deal_id:str; quantity:int=1; confirmed:bool=False
@router.post("/deals/purchase")
def purchase_deal(body:PurchaseBody,auth:AuthContext=Depends(require_auth)):
    if not body.confirmed: raise HTTPException(status_code=409,detail="explicit confirmation required")
    if body.quantity < 1 or body.quantity > 20: raise HTTPException(status_code=422,detail="quantity must be between 1 and 20")
    mall=mall_for(auth,body.session_id)
    with connection() as db:
        deal=db.execute("SELECT * FROM deals WHERE id=? AND mall_id=?",(body.deal_id,mall)).fetchone()
        if not deal: raise HTTPException(status_code=404,detail="deal not found")
        updated=db.execute("UPDATE deals SET stock=stock-? WHERE id=? AND mall_id=? AND stock>=?",(body.quantity,body.deal_id,mall,body.quantity))
        if not updated.rowcount: raise HTTPException(status_code=409,detail="deal stock unavailable")
        purchase_id="dp_"+uuid.uuid4().hex[:10]
        db.execute("INSERT INTO deal_purchases VALUES(?,?,?,?,?,?,?,?)",(purchase_id,body.deal_id,auth.user_id,mall,body.quantity,deal["price"],"paid",now_iso()))
    return envelope({"purchase_id":purchase_id,"deal_id":body.deal_id,"quantity":body.quantity,"status":"paid"})

@router.get("/deals/purchases")
def purchases(auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        rows=db.execute("""SELECT p.*,d.title,s.name AS store_name FROM deal_purchases p
          JOIN deals d ON d.id=p.deal_id LEFT JOIN stores s ON s.id=d.store_id
          WHERE p.user_id=? ORDER BY p.purchased_at DESC""",(auth.user_id,)).fetchall()
    return envelope(rows_to_dicts(rows))

def _scheduled_at(value: str):
    now=datetime.now(timezone.utc).astimezone(); day=now.date()
    if "明天" in value or "明晚" in value: day+=timedelta(days=1)
    match=re.search(r"(\d{1,2})(?::|点)(\d{2})?",value or "")
    if not match: return None
    hour=int(match.group(1)); minute=int(match.group(2) or 0)
    if any(word in value for word in ("下午","晚上","今晚","明晚")) and hour<12: hour+=12
    try: return datetime.combine(day,datetime.min.time(),tzinfo=now.tzinfo).replace(hour=hour,minute=minute).astimezone(timezone.utc).isoformat()
    except ValueError: return None

class ReservationBody(BaseModel):
    session_id:str
    store_id:str
    reserved_for:str=Field(min_length=2,max_length=60)
    people:int=Field(ge=1,le=50)
    confirmed:bool=False
    notes:str=""
    scheduled_at:str|None=None
    duration_minutes:int=Field(default=60,ge=15,le=480)
@router.post("/reservations")
def reserve(body:ReservationBody,auth:AuthContext=Depends(require_auth)):
    if not body.confirmed: raise HTTPException(status_code=409,detail="explicit confirmation required")
    mall=mall_for(auth,body.session_id)
    with connection() as db:
        store=db.execute("SELECT * FROM stores WHERE id=? AND mall_id=? AND reservable=1",(body.store_id,mall)).fetchone()
        if not store: raise HTTPException(status_code=404,detail="reservable store not found")
        rid="res_"+uuid.uuid4().hex[:10]
        scheduled=body.scheduled_at or _scheduled_at(body.reserved_for)
        db.execute("""INSERT INTO reservations(id,user_id,mall_id,store_id,kind,reserved_for,people,notes,status,created_at,scheduled_at,duration_minutes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,auth.user_id,mall,body.store_id,"restaurant",body.reserved_for,body.people,body.notes,"confirmed",now_iso(),scheduled,body.duration_minutes))
    return envelope({"reservation_id":rid,"status":"confirmed","scheduled_at":scheduled,"duration_minutes":body.duration_minutes})

class ReservationUpdateBody(BaseModel):
    reserved_for:str|None=Field(default=None,min_length=2,max_length=60)
    people:int|None=Field(default=None,ge=1,le=50)
    confirmed:bool=False

    @model_validator(mode="after")
    def require_change(self):
        if self.reserved_for is None and self.people is None:
            raise ValueError("reserved_for or people is required")
        return self

@router.patch("/reservations/{reservation_id}")
def update_reservation(reservation_id:str,body:ReservationUpdateBody,auth:AuthContext=Depends(require_auth)):
    if not body.confirmed: raise HTTPException(status_code=409,detail="explicit confirmation required")
    with connection() as db:
        current=db.execute("SELECT * FROM reservations WHERE id=? AND user_id=?",(reservation_id,auth.user_id)).fetchone()
        if not current: raise HTTPException(status_code=404,detail="reservation not found")
        if current["status"]=="cancelled": raise HTTPException(status_code=409,detail="cancelled reservation cannot be changed")
        reserved_for=(body.reserved_for or current["reserved_for"]).strip(); people=body.people or current["people"]
        scheduled=_scheduled_at(reserved_for) if body.reserved_for is not None else current["scheduled_at"]
        db.execute("UPDATE reservations SET reserved_for=?,people=?,scheduled_at=? WHERE id=? AND user_id=?",(reserved_for,people,scheduled,reservation_id,auth.user_id))
        updated=db.execute("""SELECT r.*,s.name AS store_name FROM reservations r LEFT JOIN stores s ON s.id=r.store_id
          WHERE r.id=? AND r.user_id=?""",(reservation_id,auth.user_id)).fetchone()
    return envelope(dict(updated))
@router.get("/reservations")
def reservations(auth:AuthContext=Depends(require_auth)):
    return envelope(list_reservations(auth.user_id))

@router.get("/member/assets")
def assets(auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        coupons_count=db.execute("SELECT COUNT(*) FROM user_coupons WHERE user_id=?",(auth.user_id,)).fetchone()[0]
        reservations_count=db.execute("SELECT COUNT(*) FROM reservations WHERE user_id=? AND status!='cancelled'",(auth.user_id,)).fetchone()[0]
        tickets_count=db.execute("SELECT COALESCE(SUM(quantity),0) FROM user_tickets WHERE user_id=?",(auth.user_id,)).fetchone()[0]
        purchases_count=db.execute("SELECT COALESCE(SUM(quantity),0) FROM deal_purchases WHERE user_id=? AND status='paid'",(auth.user_id,)).fetchone()[0]
    return envelope({"coupons":coupons_count,"reservations":reservations_count,"tickets":tickets_count,"deal_purchases":purchases_count})
@router.delete("/reservations/{reservation_id}")
def cancel(reservation_id:str,auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        cur=db.execute("UPDATE reservations SET status='cancelled' WHERE id=? AND user_id=?",(reservation_id,auth.user_id))
        if not cur.rowcount: raise HTTPException(status_code=404,detail="reservation not found")
    return envelope({"reservation_id":reservation_id,"status":"cancelled"})
@router.get("/tickets/products")
def products(session_id:str,auth:AuthContext=Depends(require_auth)):
    mall=mall_for(auth,session_id)
    with connection() as db: rows=db.execute("SELECT * FROM ticket_products WHERE mall_id=?",(mall,)).fetchall()
    return envelope(rows_to_dicts(rows))
@router.get("/tickets/my")
def my_tickets(auth:AuthContext=Depends(require_auth)):
    with connection() as db: rows=db.execute("SELECT * FROM user_tickets WHERE user_id=?",(auth.user_id,)).fetchall()
    return envelope(rows_to_dicts(rows))
@router.get("/stores")
def stores(session_id:str,reservable_only:bool=False,keyword:str="",auth:AuthContext=Depends(require_auth)):
    mall=mall_for(auth,session_id)
    return envelope(list_stores(mall,keyword,reservable_only))
@router.get("/location")
def location(auth:AuthContext=Depends(require_auth)):
    # DEMO：用户当前位置默认为主入口（商场入口），供导航起点使用
    return envelope({"name":"主入口","floor":1,"x":1.69,"z":6.73,"source":"main_entrance"})
