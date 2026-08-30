"""工具注册表与 Function Calling。

每个工具以统一 JSON Schema 声明，供大模型按需调用；callback 指向真实的私有数据源处理函数。
"""
from app.datasource import stores, parking, points, deals, reservations, status, tickets

TOOLS = [
    {
        "name": "search_stores",
        "description": "按分类或关键词在商场内搜索店铺",
        "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]},
        "callback": stores.search,
    },
    {
        "name": "goal_analyze",
        "description": "理解目标，判断是否规划类，预测场景与需采集槽位",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        "callback": None,  # 由 llm 编排器实现
    },
    {
        "name": "plan_goal",
        "description": "按场景模板生成规划方案",
        "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}},
        "callback": None,
    },
    {
        "name": "generate_route",
        "description": "把方案店铺坐标连成地图路线，返回节点与线段",
        "parameters": {"type": "object", "properties": {"plan": {"type": "array"}}},
        "callback": None,
    },
    {
        "name": "confirm_plan",
        "description": "记录用户确认结果，驱动状态迁移",
        "parameters": {"type": "object", "properties": {"decision": {"type": "string"}}},
        "callback": None,
    },
    {
        "name": "live_store_status",
        "description": "批量实时获取方案内店铺排队/余位/营业状态",
        "parameters": {"type": "object", "properties": {"store_ids": {"type": "array"}}},
        "callback": status.live_batch,
    },
    {
        "name": "reserve_restaurant",
        "description": "创建餐厅预约",
        "parameters": {"type": "object", "properties": {"store": {"type": "string"}, "time": {"type": "string"}, "seats": {"type": "integer"}}},
        "callback": reservations.create,
    },
    {
        "name": "claim_coupon",
        "description": "领取优惠券",
        "parameters": {"type": "object", "properties": {"coupon_id": {"type": "string"}}},
        "callback": deals.claim_coupon,
    },
]


def run_tool(name: str, **kwargs):
    tool = next(t for t in TOOLS if t["name"] == name)
    if tool["callback"] is None:
        raise NotImplementedError(f"tool {name} callback 未接线")
    return tool["callback"](**kwargs)


def schemas() -> list:
    return TOOLS
