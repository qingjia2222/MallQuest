import json, uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.auth import AuthContext, issue_token, require_auth
from app.core.envelope import envelope
from app.core.navigation import resolve_navigation
from app.core.router import write_demo_maps
from app.db import connection, now_iso, rows_to_dicts

router=APIRouter(tags=["commercial-expansion"])

def session_mall(auth:AuthContext,session_id:str):
    with connection() as db: row=db.execute("SELECT mall_id FROM sessions WHERE id=? AND user_id=?",(session_id,auth.user_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="session not found")
    return row["mall_id"]

def merchant_access(auth:AuthContext):
    if auth.login_channel!="merchant": raise HTTPException(status_code=403,detail="merchant role required")
    with connection() as db: row=db.execute("SELECT * FROM merchant_store_access WHERE user_id=?",(auth.user_id,)).fetchone()
    if not row: raise HTTPException(status_code=403,detail="merchant store access not found")
    return dict(row)

def manager_mall(auth:AuthContext,mall_id:str="mall_demo"):
    with connection() as db: row=db.execute("SELECT 1 FROM manager_access WHERE user_id=? AND mall_id=?",(auth.user_id,mall_id)).fetchone()
    if not row: raise HTTPException(status_code=403,detail="mall manager role required")
    return mall_id

class NavigationBody(BaseModel):
    session_id:str
    query:str
    current_node:str|None=None

@router.post("/navigation/resolve")
def navigation(body:NavigationBody,auth:AuthContext=Depends(require_auth)):
    return envelope(resolve_navigation(session_mall(auth,body.session_id),body.query,body.current_node))

@router.get("/maps/{mall_id}/scene")
def map_scene(mall_id:str,auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        mall=db.execute("SELECT * FROM malls WHERE id=?",(mall_id,)).fetchone()
        if not mall: raise HTTPException(status_code=404,detail="mall not found")
        job=db.execute("SELECT * FROM map_jobs WHERE mall_id=? ORDER BY created_at DESC LIMIT 1",(mall_id,)).fetchone()
        stores=db.execute("""SELECT s.id,s.name,s.category,s.floor,s.pos_x,s.pos_y,
            ss.open_status,ss.queue_minutes,ss.seats_available,sp.business_hours,sp.service_tags,
            mb.source_key AS map_slot,mb.source_label AS map_label,mb.map_x,mb.map_z,
            mb.map_width,mb.map_depth,mb.source AS map_source
            FROM stores s
            LEFT JOIN store_status ss ON ss.store_id=s.id
            LEFT JOIN store_profiles sp ON sp.store_id=s.id
            LEFT JOIN store_map_bindings mb ON mb.store_id=s.id AND mb.mall_id=s.mall_id
            WHERE s.mall_id=? ORDER BY s.floor,s.id""",(mall_id,)).fetchall()
    return envelope({"mall_id":mall_id,"mall_name":mall["name"],"map_mode":job["map_mode"] if job else "demo_2_5d","status":job["status"] if job else "published","stores":[{**dict(row),"shape":{"x":row["pos_x"]-55,"y":row["pos_y"]-30,"width":110,"height":60}} for row in stores]})

@router.get("/stores/{store_id}/public-status")
def public_store(store_id:str,mall_id:str=Query(...),auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        row=db.execute("SELECT s.id,s.name,s.category,s.floor,s.avg_price,ss.open_status,ss.queue_minutes,ss.seats_available,sp.business_hours,sp.service_tags,d.title AS deal_title,d.price AS deal_price FROM stores s LEFT JOIN store_status ss ON ss.store_id=s.id LEFT JOIN store_profiles sp ON sp.store_id=s.id LEFT JOIN deals d ON d.store_id=s.id AND d.mall_id=s.mall_id AND d.stock>0 WHERE s.id=? AND s.mall_id=? ORDER BY d.price LIMIT 1",(store_id,mall_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="store not found")
    return envelope(dict(row))

class StoreCodeBody(BaseModel): store_code:str

@router.post("/merchant/auth/store-code")
def merchant_login(body:StoreCodeBody):
    code=body.store_code.strip().upper()
    with connection() as db:
        row=db.execute("SELECT msa.user_id,msa.mall_id,msa.store_id,s.name FROM store_profiles sp JOIN merchant_store_access msa ON msa.store_id=sp.store_id JOIN stores s ON s.id=sp.store_id WHERE sp.store_code=?",(code,)).fetchone()
    if not row: raise HTTPException(status_code=401,detail="店铺编码无效")
    return envelope({"token":issue_token(row["user_id"],"merchant"),"role":"merchant","mall_id":row["mall_id"],"store_id":row["store_id"],"store_name":row["name"]})

def merchant_store_data(store_id:str):
    with connection() as db:
        row=db.execute("SELECT s.*,sp.store_code,sp.manager_name,sp.employees_json,sp.business_hours,sp.service_tags,sp.contact,ss.open_status AS live_open_status,ss.queue_minutes AS live_queue_minutes,ss.seats_available AS live_seats_available FROM stores s JOIN store_profiles sp ON sp.store_id=s.id LEFT JOIN store_status ss ON ss.store_id=s.id WHERE s.id=?",(store_id,)).fetchone()
        deals=db.execute("SELECT id,title,price,stock FROM deals WHERE store_id=? ORDER BY id",(store_id,)).fetchall()
    data=dict(row); data["employees"]=json.loads(data.pop("employees_json")); data["deals"]=rows_to_dicts(deals); return data

@router.get("/merchant/store")
def merchant_store(auth:AuthContext=Depends(require_auth)):
    access=merchant_access(auth); return envelope(merchant_store_data(access["store_id"]))

class StoreStatusBody(BaseModel):
    open_status:str
    queue_minutes:int=Field(ge=0,le=240)
    seats_available:int=Field(ge=0,le=500)

@router.patch("/merchant/store/status")
def merchant_status(body:StoreStatusBody,auth:AuthContext=Depends(require_auth)):
    if body.open_status not in {"open","busy","closed"}: raise HTTPException(status_code=422,detail="open_status must be open, busy or closed")
    access=merchant_access(auth)
    with connection() as db:
        db.execute("UPDATE store_status SET open_status=?,queue_minutes=?,seats_available=?,updated_at=? WHERE store_id=? AND mall_id=?",(body.open_status,body.queue_minutes,body.seats_available,now_iso(),access["store_id"],access["mall_id"]))
        db.execute("UPDATE stores SET open_status=?,queue_minutes=?,seats_available=? WHERE id=? AND mall_id=?",(body.open_status,body.queue_minutes,body.seats_available,access["store_id"],access["mall_id"]))
    return envelope(merchant_store_data(access["store_id"]))

class MerchantDealBody(BaseModel): title:str; price:float=Field(gt=0); stock:int=Field(ge=0)

@router.put("/merchant/store/deals")
def merchant_deal(body:MerchantDealBody,auth:AuthContext=Depends(require_auth)):
    access=merchant_access(auth); deal_id="dm_"+uuid.uuid4().hex[:10]
    with connection() as db: db.execute("INSERT INTO deals VALUES(?,?,?,?,?,?)",(deal_id,access["mall_id"],access["store_id"],body.title,body.price,body.stock))
    return envelope({"deal_id":deal_id,"store_id":access["store_id"],"status":"published"})

@router.get("/manager/analytics")
def analytics(mall_id:str="mall_demo",granularity:str="month",auth:AuthContext=Depends(require_auth)):
    manager_mall(auth,mall_id)
    if granularity not in {"day","month","year"}: raise HTTPException(status_code=422,detail="granularity must be day, month or year")
    with connection() as db:
        series=rows_to_dicts(db.execute("SELECT label,footfall,revenue,conversion_rate FROM analytics_snapshots WHERE mall_id=? AND grain=? ORDER BY rowid",(mall_id,granularity)).fetchall())
        hotspots=rows_to_dicts(db.execute("SELECT s.id,s.name,s.floor,ss.queue_minutes,ss.open_status FROM store_status ss JOIN stores s ON s.id=ss.store_id WHERE ss.mall_id=? ORDER BY ss.queue_minutes DESC LIMIT 5",(mall_id,)).fetchall())
    if not series: raise HTTPException(status_code=404,detail="analytics not available")
    current=series[-1]
    return envelope({"mall_id":mall_id,"granularity":granularity,"is_mock":True,"current":current,"realtime":{"visitors_in_mall":3862,"entrances_per_minute":74,"occupancy_level":"舒适"},"series":series,"hotspots":hotspots})

class ManagerStoreBody(BaseModel):
    mall_id:str="mall_demo"; name:str; category:str; floor:int=Field(ge=1,le=9); pos_x:float=500; pos_y:float=500

@router.post("/manager/stores")
def create_store(body:ManagerStoreBody,auth:AuthContext=Depends(require_auth)):
    manager_mall(auth,body.mall_id); store_id="s"+uuid.uuid4().hex[:6]; store_code=f"QD-{store_id.upper()}-{uuid.uuid4().hex[:4].upper()}"; merchant_user="merchant_"+uuid.uuid4().hex[:8]; now=now_iso()
    with connection() as db:
        db.execute("INSERT INTO users VALUES(?,?,?)",(merchant_user,f"{body.name}商户",now))
        db.execute("INSERT INTO stores VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(store_id,body.mall_id,body.name,body.category,body.floor,body.pos_x,body.pos_y,f"f{body.floor}_{store_id}",0,"closed",0,0,0,"新入驻"))
        db.execute("INSERT INTO store_status VALUES(?,?,?,?,?,?,?)",(store_id,body.mall_id,"closed",0,0,0,now))
        db.execute("INSERT INTO store_profiles VALUES(?,?,?,?,?,?,?,?)",(store_id,store_code,"待填写","[]","待填写","待填写","待填写",now))
        db.execute("INSERT INTO merchant_store_access VALUES(?,?,?)",(merchant_user,body.mall_id,store_id))
    if body.mall_id=="mall_demo": write_demo_maps()
    return envelope({"store_id":store_id,"store_code":store_code,"merchant_user_id":merchant_user,"status":"created","map_rebuild":"completed"})

class MapJobBody(BaseModel): mall_id:str="mall_demo"; source_name:str

@router.post("/manager/maps")
def create_map_job(body:MapJobBody,auth:AuthContext=Depends(require_auth)):
    manager_mall(auth,body.mall_id); job_id="map_"+uuid.uuid4().hex[:10]
    with connection() as db: db.execute("INSERT INTO map_jobs VALUES(?,?,?,?,?,?)",(job_id,body.mall_id,body.source_name,"generated_2_5d","draft_generated",now_iso()))
    return envelope({"job_id":job_id,"mall_id":body.mall_id,"map_mode":"generated_2_5d","status":"draft_generated","requires_manual_review":True})
