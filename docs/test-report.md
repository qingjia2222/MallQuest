# 验收测试报告

执行环境：`D:\miniconda\Miniconda3\envs\OpenCV\python.exe`，Windows 本机，2026-08-31。

## 自动化结果

- `python -m pytest -q server/tests`：8 passed，覆盖鉴权、扫码建会话、RAG 来源、私有数据隔离、中文槽位、五类规划、确认门、路线和注入防护。
- `server/scripts/smoke_demo.py`：连续运行 2 次均 `SMOKE DEMO PASSED`；每次 17 个请求、0 错误，五个规划场景均到达 DONE。
- `server/scripts/load_test.py`：120/120 成功、0 错误、16 并发、吞吐 316.01 req/s、平均 48.05 ms、P50 50.54 ms、P95 72.71 ms。
- Python `compileall`、Web/小程序 JavaScript 语法、全部小程序 JSON 解析均通过。

## 人工联调结果

- Web 在内置浏览器完成登录、扫码会话、标准约会句、跨层路线、显式确认、预约/领券/购票写库及共享预约查询；控制台 0 error、0 warning。
- Windows SAPI 普通话在桌面会话中生成了有效 WAV；受限自动化沙箱内 COM 不可用时会明确记录 `windows_tts_failed` 并返回应急音频，接口不中断。
- 当前机器未发现微信开发者工具，因此小程序已完成代码、配置和语法验收，但未声称完成开发者工具或真机视觉验收。
- 千问在线模式因未提供密钥未执行；填写 `server/.env` 后需先运行 `server/scripts/verify_online_llm.py`。

压力测试的机器实测明细见 `docs/load-test-report.md`。
