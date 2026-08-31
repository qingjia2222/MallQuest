import json, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.datasource.registry import registry
from app.db import connection, now_iso
from app.core.router import MAP_ROOT, write_demo_maps

router=APIRouter(tags=["scan"])
class ScanBody(BaseModel): mall_id:str|None="mall_demo"; service_code:str|None=None; session_id:str|None=None
@router.post("/scan")
def scan(body:ScanBody,auth:AuthContext=Depends(require_auth)):
    service_code=(body.service_code or "").strip().upper()
    entry_node="f1_c0"; entry_source="manual"
    if service_code:
        with connection() as db: qr=db.execute("SELECT * FROM mall_service_codes WHERE code=? AND active=1",(service_code,)).fetchone()
        if not qr: raise HTTPException(status_code=404,detail="AI 服务二维码无效或已停用")
        mall_id=qr["mall_id"]; entry_node=qr["entry_node"]; entry_source="ai_service_qr"
    else: mall_id=body.mall_id or "mall_demo"
    mall=registry.get(mall_id); session_id=body.session_id or "sess_"+uuid.uuid4().hex[:12]
    context={"entry_source":entry_source,"entry_node":entry_node,"service_code":service_code or None}
    with connection() as db: db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,auth.user_id,mall_id,None,"{}",None,"IDLE",json.dumps(context,ensure_ascii=False),now_iso()))
    if mall_id=="mall_demo": write_demo_maps()
    manifest_path=MAP_ROOT/mall_id/"map_manifest.json"; manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    sources=[{"type":"stores","label":"店铺与营业状态","live":True},{"type":"queue","label":"餐厅实时排队","live":True},{"type":"parking","label":"停车场余位","live":True},{"type":"members","label":"会员与积分规则","live":True},{"type":"deals","label":"今日特惠","live":True}]
    return envelope({"session_id":session_id,"mall_id":mall_id,"mall_name":mall.name,"connected":True,"entry_source":entry_source,"entry_node":entry_node,"service_code":service_code or None,"datasource_connection":{"status":"connected","is_demo":True,"sources":sources},"map_manifest":manifest})
