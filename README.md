# MallQuest · 星河里 AI 私域服务助手

课程选题 21 的可运行双端 Demo：微信小程序与 Web 共用 FastAPI、SQLite 私有数据、千问兼容 LLM、RAG、多步 Planner、室内路线、确认后事务和普通话 TTS。小程序和 Web 均提供游客/会员、商户、商场管理者三个独立入口，登录后只进入本角色工作区。

## 快速演示

```powershell
.\run_demo.ps1
```

随后打开 Web `http://127.0.0.1:5173`，或在微信开发者工具导入 `app/`。游客/会员手机号联调用 `11111111111 / 123456`，Web 也保留 `demo / demo123`；商户演示编码 `QD-S01-DEMO`；管理者演示账号 `manager / manager123`。真实凭证只放未提交的 `server/.env`，自动测试会强制使用 scripted，不消耗线上额度。

主要文档：`docs/api-contract.md`、`docs/demo-script.md`、`docs/test-report.md`、`docs/teacher-qa.md`、`server/README.md`。当前以甲组最新 3D 场景和实际 69 家店铺目录为准，SQLite 是店铺状态、计划、预约、领券、抢购和票务的运行期唯一事实源。问路时会自动弹出走廊约束的红点路线动画，并可切换直梯或扶梯；普通攻略问答不会触发路线。
