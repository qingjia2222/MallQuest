import json, uuid
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.datasource.registry import registry
from app.db import connection, now_iso
from app.core.router import MAP_ROOT, write_demo_maps

router=APIRouter(tags=["scan"])
class ScanBody(BaseModel): mall_id:str="mall_demo"; session_id:str|None=None
@router.post("/scan")
def scan(body:ScanBody,auth:AuthContext=Depends(require_auth)):
    mall=registry.get(body.mall_id); session_id=body.session_id or "sess_"+uuid.uuid4().hex[:12]
    with connection() as db: db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?,?,?)",(session_id,auth.user_id,body.mall_id,None,"{}",None,"IDLE","{}",now_iso()))
    if body.mall_id=="mall_demo": write_demo_maps()
    manifest_path=MAP_ROOT/body.mall_id/"map_manifest.json"; manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    return envelope({"session_id":session_id,"mall_id":body.mall_id,"mall_name":mall.name,"connected":True,"map_manifest":manifest})
