# 决策记录

1. 甲方 GitHub 仅有初始化骨架，因此补齐最低可联调双端；保持请求层与页面分离，未来可替换视觉组件。
2. 后端采用 FastAPI + 标准库 sqlite3，避免为课程 Demo 引入 ORM 迁移和中间件集群。
3. 主商场内部 ID 固定 `mall_demo`、展示名暂定 `QD square`；隔离测试商场为 `mall_alt`。
4. 在线模型采用千问 OpenAI-compatible 地址，Key 只写本地 `server/.env`；默认 scripted 保证离线演示。
5. 微信真实 `code2session` 代码保留；凭证缺失期间使用 `WX_AUTH_MODE=mock`。
6. 无真实楼层图，生成两层明确标注 Demo 的 SVG 与可解释路网，路线使用 Dijkstra。
7. TTS 首选 Windows SAPI 中文语音；不可用时返回明确标识的 WAV emergency fallback，不伪装在线 TTS。
8. 录屏优先微信开发者工具，避免 HTTPS/合法域名和手机网络引入现场不稳定因素。
