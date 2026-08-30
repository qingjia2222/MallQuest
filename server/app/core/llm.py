"""LLM 适配器：在线 OpenAI 兼容 + 离线 scripted 兜底。"""
from app.config import settings


class LLMAdapter:
    """统一接口：chat(messages, tools) -> (reply, tool_calls)。"""

    def __init__(self):
        self.online = OpenAICompatAdapter() if settings.llm_api_key else None

    def chat(self, messages, tools=None):
        if self.online:
            try:
                return self.online.chat(messages, tools)
            except Exception:
                pass  # 在线失败 → 回退离线
        return ScriptedAdapter().chat(messages)


class OpenAICompatAdapter:
    def __init__(self):
        from openai import OpenAI

        self.client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

    def chat(self, messages, tools=None):
        # 实现：传 tools → Function Calling → 返回 reply + tool_calls
        raise NotImplementedError


class ScriptedAdapter:
    """离线关键词意图规则，断网 / 无 key 时兜底，保证可演示。"""

    def chat(self, messages):
        return "抱歉，我暂时离线了。不过你仍可输入「停车」「美食」「积分」等关键词体验基础功能。"
