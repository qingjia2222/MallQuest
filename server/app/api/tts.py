from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.core.auth import AuthContext, require_auth
from app.core.envelope import envelope
from app.core.router import MAP_ROOT
from app.core.tts import AUDIO_DIR, synthesize
router=APIRouter(tags=["tts"])
class TTSBody(BaseModel): text:str
@router.post("/tts")
def tts(body:TTSBody,auth:AuthContext=Depends(require_auth)): return envelope(synthesize(body.text))
@router.get("/audio/{audio_id}")
def audio(audio_id:str):
    if not audio_id.isalnum(): raise HTTPException(status_code=400,detail="invalid audio id")
    path=AUDIO_DIR/f"{audio_id}.wav"
    if not path.exists(): raise HTTPException(status_code=404,detail="audio not found")
    return FileResponse(path,media_type="audio/wav")
@router.get("/maps/{mall_id}/{filename}")
def map_file(mall_id:str,filename:str):
    if not mall_id.replace("_","").isalnum() or Path(filename).name!=filename: raise HTTPException(status_code=400,detail="invalid map path")
    path=MAP_ROOT/mall_id/filename
    if not path.exists(): raise HTTPException(status_code=404,detail="map file not found")
    return FileResponse(path)
