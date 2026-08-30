# 选题 21：基于商场场景二维码的大模型私有数据源对接与私域服务助手

> 用户在商场内扫一扫「AI 服务二维码」或从网页登录，大模型即刻以对话方式动态对接商场私有数据源。
> 用户只需说出一个目标（如「我今天约会」「安排家宴」「给朋友挑礼物」），智能体会**全链路**主动规划：
> 理解目标 → 拆解任务 → 采集偏好 → 生成方案 → 绘制地图路线 → 征求确认 → 实时展示店铺状态 → 自动完成预约 / 领券 / 购票。

## 核心亮点

- **一码一所**：二维码携带 `mall_id`，自动路由到对应商场的私有数据源，一套系统服务多个商场。
- **LLM 即网关**：大模型通过 Function Calling 自主编排对私有数据源的查询与事务操作。
- **通用需求全链路规划**：`goal-driven` 的规划智能体，不写死场景，靠「目标 → 规划模板」动态确定流程。
- **人机确认闭环**：提议 → 确认 → 执行；所有写操作（预约/领券/购票）都经用户明确授权。
- **双端统一**：微信小程序 + Web 网页端共用一套后端与数据源，换端不丢会话。

## 目录结构

```
mall-copilot/
├─ app/        # 微信小程序前端（原生 WXML/WXSS/JS）
├─ web/        # Web 网页端（Vue/React SPA，与小程序同构）
├─ server/     # Python 后端（FastAPI + 大模型编排 + 私有数据源）
├─ docs/       # 文档与演示
├─ README.md
└─ .gitignore
```

## 技术栈

| 端 | 技术 |
|---|---|
| 小程序 | 原生微信小程序（WXML/WXSS/JS）|
| Web | HTML5 + Vue/React，共用后端 |
| 后端 | Python 3.11 + FastAPI，SSE 流式 |
| 大模型 | OpenAI 兼容 API（通义 Qwen / DeepSeek），离线 scripted 兜底 |
| 数据 | SQLite（开发）/ PostgreSQL（部署）|

## 快速开始

（骨架搭建中，后续补充启动脚本。）

- `server/`：`pip install -r requirements.txt` → `uvicorn app.main:app`
- `app/`：用微信开发者工具打开
- `web/`：`npm install` → `npm run dev`
