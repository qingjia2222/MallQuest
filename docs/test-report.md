# 验收测试报告

执行环境：`D:\miniconda\Miniconda3\envs\OpenCV\python.exe`，Windows 本机，2026-08-31。

## 自动化结果

- `python -m pytest -q server/tests`：12 passed，覆盖鉴权、扫码建会话、RAG 来源、私有数据隔离、中文槽位、五类规划、确认门、路线、目的地动画、商户同步、管理看板、三角色越权阻断和注入防护。
- `server/scripts/smoke_demo.py`：连续运行 2 次均 `SMOKE DEMO PASSED`；每次 17 个请求、0 错误，五个规划场景均到达 DONE。
- `server/scripts/load_test.py`：120/120 成功、0 错误、16 并发、吞吐 319.58 req/s、平均 47.21 ms、P50 49.41 ms、P95 74.72 ms。
- Python `compileall`、Web/小程序 JavaScript 语法、全部小程序 JSON 解析均通过。
- 甲方 Vue/Vite 前端依赖审计 0 vulnerabilities，`npm run build` 成功（57 modules transformed）。
- 本地浏览器验收：三方入口、管理者驾驶舱、商户运营台、游客问路浮层及普通问答不误触发均通过，控制台 0 error。
- 测试与冒烟脚本强制使用 mock 微信和 scripted LLM，不受本地真实 `.env` 影响，也不会消耗线上额度。

## 人工联调结果

- Web 在内置浏览器完成登录、扫码会话、标准约会句、跨层路线、显式确认、预约/领券/购票写库及共享预约查询；控制台 0 error、0 warning。
- Windows SAPI 普通话在桌面会话中生成了有效 WAV；受限自动化沙箱内 COM 不可用时会明确记录 `windows_tts_failed` 并返回应急音频，接口不中断。
- 微信开发者工具已安装并完成真实 `wx.login → code2session` 联调；本轮新三入口/路线动画页面仍需在开发者工具重新编译后做录屏前视觉确认。
- 千问在线模式已用本地未提交凭证完成连通验证；现场仍保留 scripted 兜底，避免网络波动影响演示。

压力测试的机器实测明细见 `docs/load-test-report.md`。
