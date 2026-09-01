import json, uuid, secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from app.core.auth import AuthContext, issue_token, require_auth
from app.core.business_data import list_stores
from app.core.envelope import envelope
from app.core.navigation import resolve_navigation
from app.core.map_catalog import map_catalog
from app.db import connection, hash_password, now_iso, rows_to_dicts

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
    query:str=""
    current_node:str|None=None
    destination_store_id:str|None=None
    vertical_mode:str|None=None

    @model_validator(mode="after")
    def require_destination(self):
        if not self.query and not self.destination_store_id: raise ValueError("query or destination_store_id is required")
        return self

@router.post("/navigation/resolve")
def navigation(body:NavigationBody,auth:AuthContext=Depends(require_auth)):
    return envelope(resolve_navigation(session_mall(auth,body.session_id),body.query,body.current_node,body.destination_store_id,body.vertical_mode))

@router.get("/maps/{mall_id}/scene")
def map_scene(mall_id:str,auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        mall=db.execute("SELECT * FROM malls WHERE id=?",(mall_id,)).fetchone()
        if not mall: raise HTTPException(status_code=404,detail="mall not found")
        job=db.execute("SELECT * FROM map_jobs WHERE mall_id=? ORDER BY created_at DESC LIMIT 1",(mall_id,)).fetchone()
        parking=db.execute("SELECT area,total,free,updated_at FROM parking WHERE mall_id=? ORDER BY area",(mall_id,)).fetchall()
    catalog=list_stores(mall_id)
    for item in catalog:
        item["shape"]={"x":item["pos_x"]-55,"y":item["pos_y"]-30,"width":110,"height":60}
    facilities=map_catalog()["facilities"] if mall_id=="mall_demo" else []
    return envelope({"mall_id":mall_id,"mall_name":mall["name"],"map_mode":job["map_mode"] if job else "demo_2_5d","status":job["status"] if job else "published","stores":catalog,"facilities":facilities,"parking":rows_to_dicts(parking)})

@router.get("/stores/{store_id}/public-status")
def public_store(store_id:str,mall_id:str=Query(...),auth:AuthContext=Depends(require_auth)):
    with connection() as db:
        row=db.execute("SELECT s.id,s.name,s.category,s.floor,s.avg_price,ss.open_status,ss.queue_minutes,ss.seats_available,sp.store_code,sp.business_hours,sp.service_tags,d.title AS deal_title,d.price AS deal_price,sd.details_json FROM stores s LEFT JOIN store_status ss ON ss.store_id=s.id LEFT JOIN store_profiles sp ON sp.store_id=s.id LEFT JOIN deals d ON d.store_id=s.id AND d.mall_id=s.mall_id AND d.stock>0 LEFT JOIN store_details sd ON sd.store_id=s.id WHERE s.id=? AND s.mall_id=? ORDER BY d.price LIMIT 1",(store_id,mall_id)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="store not found")
    data=dict(row); details=json.loads(data.pop("details_json") or "{}"); data.update({key:value for key,value in details.items() if key not in data or data[key] in (None,"")}); return envelope(data)

class StoreCodeBody(BaseModel): store_code:str; password:str
class MerchantRegisterBody(BaseModel): store_code:str; password:str

def validate_merchant_password(password:str):
    if len(password)<6 or len(password)>64: raise HTTPException(status_code=422,detail="密码长度需为6至64位")

@router.post("/merchant/auth/register")
def merchant_register(body:MerchantRegisterBody):
    code=body.store_code.strip().upper(); validate_merchant_password(body.password)
    with connection(immediate=True) as db:
        store=db.execute("SELECT s.id,s.mall_id,s.name FROM store_profiles sp JOIN stores s ON s.id=sp.store_id WHERE sp.store_code=?",(code,)).fetchone()
        if not store: raise HTTPException(status_code=404,detail="店铺编码无效，请向商场管理者确认")
        if db.execute("SELECT 1 FROM merchant_credentials WHERE store_id=?",(store["id"],)).fetchone():
            raise HTTPException(status_code=409,detail="该店铺编码已注册，请直接登录")
        user_id="merchant_"+uuid.uuid4().hex[:12]; salt=secrets.token_hex(16)
        db.execute("INSERT INTO users VALUES(?,?,?)",(user_id,store["name"]+"商户",now_iso()))
        db.execute("INSERT INTO merchant_store_access VALUES(?,?,?)",(user_id,store["mall_id"],store["id"]))
        db.execute("INSERT INTO merchant_credentials VALUES(?,?,?,?,?,?)",(store["id"],user_id,store["mall_id"],salt,hash_password(body.password,salt),now_iso()))
    return envelope({"token":issue_token(user_id,"merchant"),"user_id":user_id,"login_channel":"merchant","role":"merchant","mall_id":store["mall_id"],"store_id":store["id"],"store_name":store["name"]})

@router.post("/merchant/auth/store-code")
def merchant_login(body:StoreCodeBody):
    code=body.store_code.strip().upper()
    with connection() as db:
        row=db.execute("SELECT mc.user_id,mc.mall_id,mc.store_id,mc.salt,mc.password_hash,s.name FROM store_profiles sp JOIN merchant_credentials mc ON mc.store_id=sp.store_id JOIN stores s ON s.id=sp.store_id WHERE sp.store_code=?",(code,)).fetchone()
    if not row: raise HTTPException(status_code=401,detail="店铺编码未注册或无效")
    if hash_password(body.password,row["salt"])!=row["password_hash"]: raise HTTPException(status_code=401,detail="店铺编码或密码错误")
    return envelope({"token":issue_token(row["user_id"],"merchant"),"user_id":row["user_id"],"login_channel":"merchant","role":"merchant","mall_id":row["mall_id"],"store_id":row["store_id"],"store_name":row["name"]})

def merchant_store_data(store_id:str):
    with connection() as db:
        row=db.execute("SELECT s.*,sp.store_code,sp.manager_name,sp.employees_json,sp.business_hours,sp.service_tags,sp.contact,ss.open_status AS live_open_status,ss.queue_minutes AS live_queue_minutes,ss.seats_available AS live_seats_available FROM stores s JOIN store_profiles sp ON sp.store_id=s.id LEFT JOIN store_status ss ON ss.store_id=s.id WHERE s.id=?",(store_id,)).fetchone()
        deals=db.execute("SELECT id,title,price,stock FROM deals WHERE store_id=? ORDER BY id",(store_id,)).fetchall()
        coupons=db.execute("SELECT id,title,stock,face_value,min_spend FROM coupons WHERE store_id=? ORDER BY id",(store_id,)).fetchall()
    data=dict(row); data["employees"]=json.loads(data.pop("employees_json")); data["deals"]=rows_to_dicts(deals); data["coupons"]=rows_to_dicts(coupons); return data

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

class MerchantCouponBody(BaseModel):
    title:str=Field(min_length=1,max_length=60)
    face_value:float=Field(gt=0,le=100000)
    min_spend:float=Field(default=0,ge=0,le=1000000)
    stock:int=Field(gt=0,le=1000000)

    @model_validator(mode="after")
    def validate_voucher(self):
        self.title=self.title.strip()
        if not self.title:
            raise ValueError("代金券标题不能为空")
        if self.min_spend and self.face_value>=self.min_spend:
            raise ValueError("有门槛代金券的抵扣金额必须小于使用门槛")
        return self

@router.put("/merchant/store/coupons")
def merchant_coupon(body:MerchantCouponBody,auth:AuthContext=Depends(require_auth)):
    access=merchant_access(auth); coupon_id="cm_"+uuid.uuid4().hex[:10]
    with connection() as db:
        db.execute("""INSERT INTO coupons(id,mall_id,store_id,title,stock,face_value,min_spend)
          VALUES(?,?,?,?,?,?,?)""",(coupon_id,access["mall_id"],access["store_id"],body.title,body.stock,body.face_value,body.min_spend))
    return envelope({"coupon_id":coupon_id,"store_id":access["store_id"],"status":"published"})

@router.get("/manager/analytics")
def analytics(mall_id:str="mall_demo",granularity:str="month",auth:AuthContext=Depends(require_auth)):
    manager_mall(auth,mall_id)
    if granularity not in {"day","month","year"}: raise HTTPException(status_code=422,detail="granularity must be day, month or year")
    with connection() as db:
        series=rows_to_dicts(db.execute("SELECT label,footfall,revenue,conversion_rate FROM analytics_snapshots WHERE mall_id=? AND grain=? ORDER BY rowid",(mall_id,granularity)).fetchall())
        hotspots=rows_to_dicts(db.execute("SELECT s.id,s.name,s.floor,ss.queue_minutes,ss.open_status FROM store_status ss JOIN stores s ON s.id=ss.store_id WHERE ss.mall_id=? ORDER BY ss.queue_minutes DESC LIMIT 5",(mall_id,)).fetchall())
    if not series: raise HTTPException(status_code=404,detail="analytics not available")
    current=series[-1]
    labels={"day":"日度","month":"月度","year":"年度"}
    period_range=series[0]["label"] if len(series)==1 else f"{series[0]['label']}—{series[-1]['label']}"
    return envelope({"mall_id":mall_id,"granularity":granularity,"granularity_label":labels[granularity],"period_range":period_range,"current_label":current["label"],"is_mock":True,"current":current,"realtime":{"visitors_in_mall":3862,"entrances_per_minute":74,"occupancy_level":"舒适"},"series":series,"hotspots":hotspots})

class ManagerStoreBody(BaseModel):
    mall_id:str="mall_demo"; name:str; category:str; floor:int=Field(ge=1,le=9); pos_x:float=500; pos_y:float=500

@router.post("/manager/stores")
def create_store(body:ManagerStoreBody,auth:AuthContext=Depends(require_auth)):
    manager_mall(auth,body.mall_id)
    with connection() as db:
        row=db.execute("""SELECT s.id,s.name,s.floor,sp.store_code
          FROM stores s JOIN store_map_bindings mb ON mb.store_id=s.id
          LEFT JOIN store_profiles sp ON sp.store_id=s.id
          WHERE s.mall_id=? AND s.name=?""",(body.mall_id,body.name.strip())).fetchone()
        if not row:
            raise HTTPException(status_code=409,detail="该店名尚无 3D 地图点位，请先在地图目录中新增并校准点位后再创建编码")
        store_code=row["store_code"]
    return envelope({"store_id":row["id"],"store_code":store_code,"status":"mapped","floor":row["floor"],"map_rebuild":"not_required"})

class MapJobBody(BaseModel): mall_id:str="mall_demo"; source_name:str

@router.post("/manager/maps")
def create_map_job(body:MapJobBody,auth:AuthContext=Depends(require_auth)):
    manager_mall(auth,body.mall_id); job_id="map_"+uuid.uuid4().hex[:10]
    with connection() as db: db.execute("INSERT INTO map_jobs VALUES(?,?,?,?,?,?)",(job_id,body.mall_id,body.source_name,"generated_2_5d","draft_generated",now_iso()))
    return envelope({"job_id":job_id,"mall_id":body.mall_id,"map_mode":"generated_2_5d","status":"draft_generated","requires_manual_review":True})
