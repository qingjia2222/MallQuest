import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
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
def deals(session_id:str,auth:AuthContext=Depends(require_auth)): return envelope(get_today_deals(mall_id=mall_for(auth,session_id)))
@router.get("/tools/schema")
def tools(auth:AuthContext=Depends(require_auth)): return envelope(schemas())
class ClaimBody(BaseModel): session_id:str; coupon_id:str; confirmed:bool=False
@router.post("/coupons/claim")
def claim(body:ClaimBody,auth:AuthContext=Depends(require_auth)):
    if not body.confirmed: raise HTTPException(status_code=409,detail="explicit confirmation required")
    mall=mall_for(auth,body.session_id)
    with connection() as db: result=_claim(db,auth.user_id,mall,body.coupon_id)
    return envelope(result)
class ReservationBody(BaseModel): session_id:str; store_id:str; reserved_for:str; people:int; confirmed:bool=False; notes:str=""
@router.post("/reservations")
def reserve(body:ReservationBody,auth:AuthContext=Depends(require_auth)):
    if not body.confirmed: raise HTTPException(status_code=409,detail="explicit confirmation required")
    mall=mall_for(auth,body.session_id)
    with connection() as db:
        store=db.execute("SELECT * FROM stores WHERE id=? AND mall_id=? AND reservable=1",(body.store_id,mall)).fetchone()
        if not store: raise HTTPException(status_code=404,detail="reservable store not found")
        rid="res_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)",(rid,auth.user_id,mall,body.store_id,"restaurant",body.reserved_for,body.people,body.notes,"confirmed",now_iso()))
    return envelope({"reservation_id":rid,"status":"confirmed"})
@router.get("/reservations")
def reservations(auth:AuthContext=Depends(require_auth)):
    with connection() as db: rows=db.execute("SELECT r.*,s.name AS store_name FROM reservations r LEFT JOIN stores s ON s.id=r.store_id AND s.mall_id=r.mall_id WHERE r.user_id=? ORDER BY r.created_at DESC",(auth.user_id,)).fetchall()
    return envelope(rows_to_dicts(rows))
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
def stores(session_id:str,auth:AuthContext=Depends(require_auth)):
    mall=mall_for(auth,session_id)
    with connection() as db: rows=db.execute("""SELECT s.*,sp.store_code,sp.business_hours,sp.service_tags
        FROM stores s LEFT JOIN store_profiles sp ON sp.store_id=s.id
        WHERE s.mall_id=? ORDER BY s.floor,s.id""",(mall,)).fetchall()
    return envelope(rows_to_dicts(rows))
