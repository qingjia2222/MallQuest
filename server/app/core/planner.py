"""通用需求规划状态机（Planner Agent, goal-driven）.

不写死场景：由目标解析(goal_analyze)判断是否规划类，并由「目标 → 规划模板」动态
确定需采集的槽位与要执行的落地动作。约会 / 家宴 / 买礼物等都只是模板实例。
"""
from enum import Enum


class PlanState(str, Enum):
    IDLE = "idle"
    UNDERSTAND = "understand"
    COLLECT = "collect"
    PLAN = "plan"
    ROUTE = "route"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    DONE = "done"


# 目标 → 规划模板：核心槽位 + 规划动作 + 落地动作
GOAL_TEMPLATES = {
    "date": {
        "slots": ["time", "people", "budget", "taste", "movie"],
        "actions": [{"tool": "reserve_restaurant"}, {"tool": "buy_ticket"}],
    },
    "dinner": {
        "slots": ["time", "people", "budget", "taste", "private_room"],
        "actions": [{"tool": "reserve_restaurant"}],
    },
    "gift": {
        "slots": ["person", "budget", "type"],
        "actions": [{"tool": "claim_coupon"}],
    },
    "family": {
        "slots": ["kids_age", "time", "interest"],
        "actions": [{"tool": "reserve_restaurant"}, {"tool": "claim_coupon"}],
    },
}


def analyze_goal(text: str) -> dict:
    """判断用户请求是查询类还是规划类，并落在哪个场景模板。"""
    # 实现：LLM 意图分类 → {"is_plan": bool, "scene": str, "answer": str}
    raise NotImplementedError("由 LLM 适配器实现")


def build_plan(goal: str, mall_id: str, slots: dict) -> list:
    """按模板把槽位组合成一组候选方案（店铺序列 + 时间编排）。"""
    raise NotImplementedError("由规划工具组合 search_stores / get_today_deals")


def plan_step(user_msg: str, session) -> tuple:
    """一回合的状态机推进。session 保存 plan_state / slots / plan / route。"""
    state = session.plan_state
    if state == PlanState.UNDERSTAND:
        goal = analyze_goal(user_msg)
        if not goal["is_plan"]:
            return reply_direct(goal["answer"]), session
        session.goal = goal["scene"]
        session.plan_state = PlanState.COLLECT
    if state == PlanState.COLLECT:
        slots = fill_slots(session, user_msg)
        if not slots_complete(slots):
            return reply("还需要知道：" + missing_hint(slots)), session
        session.slots = slots
        session.plan_state = PlanState.PLAN
    if state == PlanState.PLAN:
        session.plan = build_plan(session.goal, session.mall_id, session.slots)
        session.plan_state = PlanState.ROUTE
    if state == PlanState.ROUTE:
        session.route = run_route(session.plan)
        session.plan_state = PlanState.CONFIRM
    if state == PlanState.CONFIRM:
        return reply_card("方案如何？" + render_plan(session.plan), route=session.route), session
    if state == PlanState.EXECUTE and user_agrees(user_msg):
        live = run_live_status(session.plan)
        actions = resolve_actions(session.goal)
        results = [run_tool(a["tool"], **a.get("args", {})) for a in actions]
        session.plan_state = PlanState.DONE
        return reply_confirmed(session.plan, live, results), session
    if not user_agrees(user_msg):
        session.plan_state = PlanState.PLAN
        return plan_step(user_msg, session)
    return reply("好，我们继续："), session


# ---- 占位工具回调（后续在 datasource / tools 实现）----
def fill_slots(session, msg): ...
def slots_complete(slots): ...
def missing_hint(slots): ...
def run_route(plan): ...
def run_live_status(plan): ...
def resolve_actions(goal): ...
def run_tool(name, **kwargs): ...
def user_agrees(msg): ...
def render_plan(plan): ...
def reply(text): ...
def reply_card(text, route=None): ...
def reply_direct(text): ...
def reply_confirmed(plan, live, results): ...
