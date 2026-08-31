import json, logging
from pathlib import Path
from app.config import settings
from app.core.metrics import metrics
from app.core.tools import run_tool, schemas
from app.core.text import plain_text

log=logging.getLogger("mall-assistant.orchestrator")
PROMPTS=Path(__file__).resolve().parents[1]/"prompts"
def run_online_tool_loop(user_message,context):
    from openai import OpenAI
    client=OpenAI(base_url=settings.llm_base_url,api_key=settings.llm_api_key,timeout=settings.llm_timeout_seconds)
    messages=[{"role":"system","content":(PROMPTS/"system.md").read_text(encoding="utf-8")+"\n"+(PROMPTS/"tool_router.md").read_text(encoding="utf-8")},{"role":"user","content":user_message}]
    available=[t for t in schemas() if t["kind"]=="read"]
    tools=[{"type":"function","function":{"name":t["name"],"description":t["description"],"parameters":t["parameters"]}} for t in available]; observations=[]
    for _ in range(6):
        completion=client.chat.completions.create(model=settings.llm_model,messages=messages,tools=tools,tool_choice="auto"); msg=completion.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            metrics.increment("llm_online_count"); return {"reply":plain_text(msg.content or "已完成查询。"),"tool_calls":observations,"degraded":False,"mode":"online"}
        for call in msg.tool_calls:
            args=json.loads(call.function.arguments or "{}"); result=run_tool(call.function.name,context,args); observations.append({"name":call.function.name,"arguments":args,"result":result}); messages.append({"role":"tool","tool_call_id":call.id,"content":json.dumps(result,ensure_ascii=False)})
    raise RuntimeError("LLM tool loop exceeded 6 iterations")

def try_online(user_message,context):
    if settings.llm_mode!="online" or not settings.llm_api_key: return None
    try: return run_online_tool_loop(user_message,context)
    except Exception as exc:
        log.exception("online_orchestration_failed error_type=%s",type(exc).__name__); metrics.increment("llm_fallback_count"); return None
