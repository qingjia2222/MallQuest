import sys
from pathlib import Path
SERVER=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(SERVER))
from app.config import settings
from app.core.llm import LLMAdapter
if __name__=="__main__":
    if not settings.llm_api_key or settings.llm_mode!="online": raise SystemExit("Set LLM_MODE=online and LLM_API_KEY in server/.env first")
    result=LLMAdapter().chat([{"role":"user","content":"查询 QD square 停车位，请选择合适工具。"}]); print(result)
    if result.get("degraded"): raise SystemExit(1)
