# QD square 后端

FastAPI 统一服务，包含游客手机号登录、保留的微信登录适配、商户店铺编码登录、管理者账号登录、AI 服务码绑定私有数据源、Token 权限隔离、SQLite 私有数据源、工具注册表、千问兼容 LLM、scripted fallback、RAG、八态 Planner、五场景事务、Dijkstra 两层路线与路线动画数据、Windows TTS、经营指标和测试。

## 环境与初始化

所有 Python 命令使用 `OpenCV`：

```powershell
& 'D:\miniconda\Miniconda3\Scripts\conda.exe' run -n OpenCV python -m pip install -r server/requirements.txt
& 'D:\miniconda\Miniconda3\Scripts\conda.exe' run -n OpenCV python server/scripts/init_demo.py
& 'D:\miniconda\Miniconda3\Scripts\conda.exe' run -n OpenCV python -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
```

复制 `.env.example` 为 `.env`。千问 Key 只写 `.env`；切换 `LLM_MODE=online` 后运行 `verify_online_llm.py`。微信凭证位于微信公众平台“小程序 → 开发管理 → 开发设置”，填入后把 `WX_AUTH_MODE` 改为 `online`。

演示账号：游客/会员手机号 `11111111111 / 123456`，商户编码 `QD-S01-DEMO`，管理者 `manager / manager123`；微信兼容接口的 mock code 为 `mock-demo`。地图位于 `server/data/maps/mall_demo`，明确为 Demo。经营分析为确定性 Mock。TTS 当前为 Windows SAPI WAV。

`docs/assets/qd-ai-service-code.png` 是微信官方接口生成的开发版小程序码，场景码为 `QD-AI-DEMO`，路径为 `pages/scan/scan`。需要重新生成时运行：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' server/scripts/generate_ai_service_code.py
```

扫码后先完成游客手机号登录，再由后端将服务码映射到商场、入口节点和该商场的数据源注册表；客户端不能用请求中的 `mall_id` 覆盖二维码绑定。

## 验证

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' -m pytest server/tests -q
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' server/scripts/smoke_demo.py
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' server/scripts/load_test.py
```

Swagger：`http://127.0.0.1:8000/docs`。微信开发者工具默认可访问 localhost；真机需 LAN/HTTPS 地址并配置合法域名。课程 Demo 未连接真实支付、票务、停车硬件或室内定位。
