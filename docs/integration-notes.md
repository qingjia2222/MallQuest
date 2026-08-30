# 双端集成说明

- Web 与微信开发者工具默认访问 `http://127.0.0.1:8000`；真机必须把 `apiBase` 改为电脑局域网地址或 HTTPS 域名。
- 小程序开发阶段 `project.config.json` 已关闭 URL 校验，仅用于开发者工具。提交审核/真机正式环境必须在微信公众平台配置合法 request/downloadFile 域名。
- Web 和微信 mock 账号都映射到 `user_demo`，因此预约、券、票和计划能跨端查看。
- 前端只负责 Envelope 解包、Token header、卡片与路线渲染。业务事实、权限、确认门均在后端。
- 地图当前为 QD square 两层 Demo SVG；未来替换真实地图时保留 1000×760 坐标系或同步更新 `route_graph.json`，接口无需改变。
- `WX_APP_ID` 在微信公众平台“小程序后台 → 开发 → 开发管理 → 开发设置”查看；`WX_APP_SECRET` 在同页生成或重置，只放 `server/.env`。没有这两项时保留 `WX_AUTH_MODE=mock`。
- 当前机器未检测到微信开发者工具。安装后导入 `app/`，本地录屏优先用开发者工具；最终发布前再用真机检查网络、权限、性能和机型适配。
