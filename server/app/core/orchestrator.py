import json, logging
from pathlib import Path
from app.config import settings
from app.core.metrics import metrics
from app.core.text import plain_text
from app.core.tools import run_tool, schemas

log=logging.getLogger("mall-assistant.orchestrator")
PROMPTS=Path(__file__).resolve().parents[1]/"prompts"

def _client():
    from openai import OpenAI
    return OpenAI(base_url=settings.llm_base_url,api_key=settings.llm_api_key,timeout=settings.llm_timeout_seconds)

def _tools_for(available_kinds):
    kinds=set(available_kinds)
    available=[t for t in schemas() if t.get("kind") in kinds]
    return [{"type":"function","function":{"name":t["name"],"description":t["description"],"parameters":t["parameters"]}} for t in available]

def _online_enabled(): return settings.llm_mode=="online" and bool(settings.llm_api_key)

def _run_tool_loop(system_prompt,user_message,context,available_kinds=("read",),max_iter=6,collect=None):
    client=_client()
    messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_message}]
    tools=_tools_for(available_kinds); observations=[]
    for _ in range(max_iter):
        completion=client.chat.completions.create(model=settings.llm_model,messages=messages,tools=tools,tool_choice="auto"); msg=completion.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            metrics.increment("llm_online_count")
            reply=msg.content or "已完成查询。"
            result={"reply":reply if collect else plain_text(reply),"tool_calls":observations,"degraded":False,"mode":"online"}
            return collect(result) if collect else result
        for call in msg.tool_calls:
            args=json.loads(call.function.arguments or "{}"); result=run_tool(call.function.name,context,args)
            observations.append({"name":call.function.name,"arguments":args,"result":result})
            messages.append({"role":"tool","tool_call_id":call.id,"content":json.dumps(result,ensure_ascii=False)})
    raise RuntimeError("LLM tool loop exceeded %d iterations"%max_iter)

def run_online_tool_loop(user_message,context):
    system=(PROMPTS/"system.md").read_text(encoding="utf-8")+"\n"+(PROMPTS/"tool_router.md").read_text(encoding="utf-8")
    return _run_tool_loop(system,user_message,context,("read",))

def try_online(user_message,context):
    if not _online_enabled(): return None
    try: return run_online_tool_loop(user_message,context)
    except Exception as exc:
        log.exception("online_orchestration_failed error_type=%s",type(exc).__name__); metrics.increment("llm_fallback_count"); return None

# ===== 规划智能体：真正调用大模型设计时间地点 + 实时查排队 + 出结构化方案 =====
PLAN_JSON_HEADER="### PLAN_JSON"

def _extract_plan_json(text):
    if not text: return None
    idx=text.find(PLAN_JSON_HEADER)
    seg=text[idx+len(PLAN_JSON_HEADER):] if idx>=0 else text
    start=seg.find("{")
    if start<0: return None
    depth=0; end=-1
    for i in range(start,len(seg)):
        if seg[i]=="{": depth+=1
        elif seg[i]=="}":
            depth-=1
            if depth==0: end=i+1; break
    if end<0: return None
    try: return json.loads(seg[start:end])
    except Exception as exc:
        log.warning("plan_json_parse_failed error=%s",type(exc).__name__); return None

def run_planning_tool_loop(user_message,context,scene):
    system=(PROMPTS/"system.md").read_text(encoding="utf-8")+"\n"+(PROMPTS/"planning.md").read_text(encoding="utf-8")
    def collect(result):
        raw=result["reply"]
        idx=raw.find(PLAN_JSON_HEADER)
        if idx>=0: result["reply"]=raw[:idx].rstrip()
        result["plan_json"]=_extract_plan_json(raw); result["scene"]=scene
        return result
    return _run_tool_loop(system,user_message,context,("read",),max_iter=8,collect=collect)

def try_online_planning(user_message,context,scene):
    if not _online_enabled(): return None
    try: return run_planning_tool_loop(user_message,context,scene)
    except Exception as exc:
        log.exception("online_planning_failed error_type=%s",type(exc).__name__); metrics.increment("llm_fallback_count"); return None
