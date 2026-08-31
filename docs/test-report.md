# 验收测试报告

执行环境：`D:\miniconda\Miniconda3\envs\OpenCV\python.exe`，Windows 本机，2026-08-31。

## 自动化结果

- `python -m pytest -q server/tests`：20 passed，覆盖手机号鉴权、AI 服务码解析与优先绑定、无效服务码、回复星号清洗、微信兼容登录、扫码建会话、RAG 来源、私有数据隔离、中文槽位、五类规划、双策略选择、直梯/扶梯切换、走廊约束、店铺编码一致性、确认门、目的地动画、商户同步、管理看板、三角色越权阻断和注入防护。
- `server/scripts/smoke_demo.py`：连续运行 2 次均 `SMOKE DEMO PASSED`；每次 17 个请求、0 错误，五个规划场景均到达 DONE。
- `server/scripts/load_test.py`：120/120 成功、0 错误、16 并发、吞吐 264.87 req/s、平均 57.40 ms、P50 56.09 ms、P95 103.52 ms。
- Python `compileall`、Web/小程序 JavaScript 语法、全部小程序 JSON 解析均通过。
- `npm run build` 成功（65 modules transformed），小程序 25 个 JavaScript 文件逐一通过 `node --check`。
- 本地浏览器验收：三方入口、管理者驾驶舱、商户运营台、游客问路浮层及普通问答不误触发均通过，控制台 0 error。
- 测试与冒烟脚本强制使用 mock 微信和 scripted LLM，不受本地真实 `.env` 影响，也不会消耗线上额度。

## 人工联调结果

- Web 在内置浏览器完成登录、扫码会话、标准约会句、跨层路线、显式确认、预约/领券/购票写库及共享预约查询；控制台 0 error、0 warning。
- Windows SAPI 普通话在桌面会话中生成了有效 WAV；受限自动化沙箱内 COM 不可用时会明确记录 `windows_tts_failed` 并返回应急音频，接口不中断。
- 微信真实 `wx.login → code2session` 代码路径和开发版扫码路径均已接入；本轮最终小程序包的 CLI 编译仍受开发者工具“服务端口未开启”阻挡，需开启后重新编译并做录屏前视觉确认。
- 千问在线模式已用本地未提交凭证完成真实工具调用验证（`query_parking_status`，`degraded=false`）；现场仍保留 scripted 兜底，避免网络波动影响演示。

压力测试的机器实测明细见 `docs/load-test-report.md`。
