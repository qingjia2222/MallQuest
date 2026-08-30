# MallQuest · QD square AI 私域服务助手

课程选题 21 的可运行双端 Demo：微信小程序与 Web 共用 FastAPI、SQLite 私有数据、千问兼容 LLM、RAG、多步 Planner、室内路线、确认后事务和普通话 TTS。

## 快速演示

```powershell
.\run_demo.ps1
```

随后打开 Web `http://127.0.0.1:5173`，或在微信开发者工具导入 `app/`。演示账号 `demo / demo123`；当前微信使用 mock 登录并与 Web 共享 `user_demo`。

主要文档：`docs/api-contract.md`、`docs/demo-script.md`、`docs/test-report.md`、`docs/teacher-qa.md`、`server/README.md`。地图明确为两层 QD square Demo 仿真图；在线千问和真实微信登录需在未提交的 `server/.env` 中补凭证。
