import json, logging
from app.config import settings
from app.core.metrics import metrics
from app.core.tools import schemas
log=logging.getLogger("mall-assistant.llm")
class LLMAdapter:
    def __init__(self): self.online=settings.llm_mode=="online" and bool(settings.llm_api_key)
    def chat(self,messages):
        if not self.online: metrics.increment("llm_scripted_count"); return {"mode":"scripted","degraded":True,"degraded_reason":"scripted fallback"}
        try:
            from openai import OpenAI
            client=OpenAI(base_url=settings.llm_base_url,api_key=settings.llm_api_key,timeout=settings.llm_timeout_seconds)
            tools=[{"type":"function","function":{"name":t["name"],"description":t["description"],"parameters":t["parameters"]}} for t in schemas()]
            response=client.chat.completions.create(model=settings.llm_model,messages=messages,tools=tools,tool_choice="auto"); msg=response.choices[0].message; metrics.increment("llm_online_count")
            return {"mode":"online","content":msg.content,"tool_calls":[{"id":c.id,"name":c.function.name,"arguments":json.loads(c.function.arguments)} for c in (msg.tool_calls or [])],"degraded":False}
        except Exception as exc:
            log.exception("online_llm_failed falling_back_to_scripted error_type=%s",type(exc).__name__); metrics.increment("llm_fallback_count"); return {"mode":"scripted","degraded":True,"degraded_reason":f"online failure: {type(exc).__name__}"}
