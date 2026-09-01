import hashlib
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.db import connection

router=APIRouter(prefix="/manager/prompts",tags=["prompt-management"])
PROMPTS_DIR=Path(__file__).resolve().parents[1]/"prompts"
PROMPT_FILES={"system":"system.md","tool_router":"tool_router.md","planning":"planning.md"}
PROMPT_TITLES={"system":"系统角色与安全边界","tool_router":"工具路由","planning":"场景规划智能体"}

def _manager(auth:AuthContext):
    with connection() as db:
        row=db.execute("SELECT 1 FROM manager_access WHERE user_id=? AND mall_id='mall_demo'",(auth.user_id,)).fetchone()
    if not row: raise HTTPException(status_code=403,detail="mall manager role required")

def _path(name):
    filename=PROMPT_FILES.get(name)
    if not filename: raise HTTPException(status_code=404,detail="prompt not found")
    return PROMPTS_DIR/filename

def _revision(content): return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def _payload(name):
    path=_path(name); content=path.read_text(encoding="utf-8")
    return {"name":name,"title":PROMPT_TITLES[name],"filename":path.name,"content":content,"revision":_revision(content),"updated_at":datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()}

class PromptUpdate(BaseModel):
    content:str=Field(min_length=20,max_length=30000)
    expected_revision:str|None=None

class PromptRestore(BaseModel): expected_revision:str

@router.get("")
def list_prompts(auth:AuthContext=Depends(require_auth)):
    _manager(auth)
    return envelope([{key:value for key,value in _payload(name).items() if key!="content"} for name in PROMPT_FILES])

@router.get("/{name}")
def get_prompt(name:str,auth:AuthContext=Depends(require_auth)):
    _manager(auth); return envelope(_payload(name))

@router.put("/{name}")
def update_prompt(name:str,body:PromptUpdate,auth:AuthContext=Depends(require_auth)):
    _manager(auth); path=_path(name); current=path.read_text(encoding="utf-8"); current_revision=_revision(current)
    if body.expected_revision and body.expected_revision!=current_revision:
        raise HTTPException(status_code=409,detail="提示词已被其他管理员更新，请刷新后再保存")
    content=body.content.strip()+"\n"
    if content==current: return envelope(_payload(name))
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir=PROMPTS_DIR/"backups"/name; backup_dir.mkdir(parents=True,exist_ok=True)
    (backup_dir/f"{stamp}-{current_revision}.md").write_text(current,encoding="utf-8")
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(content,encoding="utf-8"); temporary.replace(path)
    return envelope(_payload(name))

@router.post("/{name}/restore-latest")
def restore_latest_prompt(name:str,body:PromptRestore,auth:AuthContext=Depends(require_auth)):
    _manager(auth); _path(name)
    backup_dir=PROMPTS_DIR/"backups"/name
    versions=sorted(backup_dir.glob("*.md"),reverse=True) if backup_dir.exists() else []
    if not versions: raise HTTPException(status_code=404,detail="没有可恢复的历史版本")
    return update_prompt(name,PromptUpdate(content=versions[0].read_text(encoding="utf-8"),expected_revision=body.expected_revision),auth)
