"""方案 → 地图路线构建。"""
from typing import List


def build_route(plan: list, mall_id: str) -> dict:
    """把方案逐站店铺坐标连成路线，返回节点与线段。"""
    nodes = []
    for i, stop in enumerate(plan, start=1):
        nodes.append({
            "seq": i,
            "store_id": stop["store_id"],
            "name": stop["name"],
            "pos_x": stop["pos_x"],
            "pos_y": stop["pos_y"],
            "floor": stop.get("floor", 1),
        })
    segments = [
        {"from": nodes[i]["store_id"], "to": nodes[i + 1]["store_id"], "floor": nodes[i]["floor"]}
        for i in range(len(nodes) - 1)
    ]
    return {"nodes": nodes, "segments": segments}
