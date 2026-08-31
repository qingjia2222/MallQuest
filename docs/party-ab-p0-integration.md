# 甲乙组 P0 融合说明

基准：`feat/ai-planning-v2` 的 `2cc58b44`。甲组 `store_info.json` 实际含 69 家店，文档中的 70 家不是当前代码事实。

- 甲组保留：Web 视觉、三维商场、69 家店铺详情、计划编辑交互、影院选择、首页与规划页结构。
- 乙组接管：FastAPI 鉴权与 envelope、SQLite 业务事实、千问工具调用与上下文、单一 Planner 状态机、确认门、走廊路由、直梯/扶梯、交易与会员资产。
- SQLite 表：店铺/状态/详情/地图绑定、计划/确认快照、预约、优惠券、抢购订单、票券和会员资产。
- 双端统一：Web 与小程序都调用 `/api/stores`、`/api/chat`、`/api/plan/*`、`/api/reservations`、`/api/coupons`、`/api/deals/*` 和 `/api/member/assets`。
- 计划编辑：顺序和 `time_label` 通过 `PATCH /api/plan/{plan_id}` 回写，后端校验店铺归属并重新生成 `corridor_only` 路线。
- 影院确认：影片选择随最终确认进入 `plan_snapshots`，执行结果与 Snapshot 可追溯。
- 3D 冻结：`web/src/components/Floors3D.vue` 未改动；后端与页面通过适配层接入店铺状态和路线。

验证：后端 23 项测试通过，Web production build 通过，小程序 JavaScript 语法检查通过，千问真实双轮对话返回 online 且能记住上一轮偏好。
