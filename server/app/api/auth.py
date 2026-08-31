import uuid
import re
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.core.auth import issue_token
from app.core.envelope import envelope
from app.db import connection, hash_password, now_iso

router=APIRouter(prefix="/auth",tags=["auth"])
class WebLogin(BaseModel):
    username:str|None=None; password:str|None=None; phone:str|None=None; pwd:str|None=None
class PhoneLogin(BaseModel): phone:str; password:str
class WxLogin(BaseModel): code:str

def authenticate(username:str,password:str):
    with connection() as db: row=db.execute("SELECT * FROM web_credentials WHERE username=?",(username,)).fetchone()
    if not row or hash_password(password,row["salt"])!=row["password_hash"]: raise HTTPException(status_code=401,detail="手机号或密码错误")
    return row

@router.post("/web-login")
def web_login(body:WebLogin):
    username=body.username or body.phone; password=body.password or body.pwd
    if not username or not password: raise HTTPException(status_code=422,detail="username and password are required")
    row=authenticate(username,password)
    return envelope({"token":issue_token(row["user_id"],"web"),"user_id":row["user_id"],"login_channel":"web"})

@router.post("/phone-login")
def phone_login(body:PhoneLogin):
    phone=body.phone.strip()
    if not re.fullmatch(r"1\d{10}",phone): raise HTTPException(status_code=422,detail="请输入11位手机号")
    row=authenticate(phone,body.password)
    return envelope({"token":issue_token(row["user_id"],"phone"),"user_id":row["user_id"],"login_channel":"phone","phone_masked":phone[:3]+"****"+phone[-4:]})

@router.post("/wx-login")
async def wx_login(body:WxLogin):
    if settings.wx_auth_mode=="mock": openid="mock-openid-alt" if body.code=="mock-alt" else "mock-openid-demo"
    else:
        if not settings.wx_app_id or not settings.wx_app_secret: raise HTTPException(status_code=503,detail="WX_APP_ID/WX_APP_SECRET are not configured")
        async with httpx.AsyncClient(timeout=15) as client:
            resp=await client.get("https://api.weixin.qq.com/sns/jscode2session",params={"appid":settings.wx_app_id,"secret":settings.wx_app_secret,"js_code":body.code,"grant_type":"authorization_code"})
        resp.raise_for_status(); payload=resp.json()
        if payload.get("errcode"): raise HTTPException(status_code=401,detail=f"wechat login failed: {payload.get('errmsg','unknown')}")
        openid=payload["openid"]
    with connection() as db:
        row=db.execute("SELECT user_id FROM wx_identities WHERE openid=?",(openid,)).fetchone()
        if row: user_id=row["user_id"]
        else:
            user_id="user_wx_"+uuid.uuid4().hex[:10]; db.execute("INSERT INTO users VALUES(?,?,?)",(user_id,"微信会员",now_iso())); db.execute("INSERT INTO wx_identities VALUES(?,?)",(openid,user_id)); db.execute("INSERT INTO members VALUES(?,?,?,?,?)",(user_id,"mall_demo",0,"普卡","2027-12-31"))
    return envelope({"token":issue_token(user_id,"wx"),"user_id":user_id,"login_channel":"wx","wx_auth_mode":settings.wx_auth_mode})
