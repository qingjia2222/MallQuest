# QD square 后端

FastAPI 统一服务，包含双登录、Token、SQLite 私有数据源、工具注册表、千问兼容 LLM、scripted fallback、RAG、八态 Planner、五场景事务、Dijkstra 两层路线、Windows TTS、指标和测试。

## 环境与初始化

所有 Python 命令使用 `OpenCV`：

```powershell
& 'D:\miniconda\Miniconda3\Scripts\conda.exe' run -n OpenCV python -m pip install -r server/requirements.txt
& 'D:\miniconda\Miniconda3\Scripts\conda.exe' run -n OpenCV python server/scripts/init_demo.py
& 'D:\miniconda\Miniconda3\Scripts\conda.exe' run -n OpenCV python -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
```

复制 `.env.example` 为 `.env`。千问 Key 只写 `.env`；切换 `LLM_MODE=online` 后运行 `verify_online_llm.py`。微信凭证位于微信公众平台“小程序 → 开发管理 → 开发设置”，填入后把 `WX_AUTH_MODE` 改为 `online`。

演示账号：`demo / demo123`；微信 mock code：`mock-demo`。地图位于 `server/data/maps/mall_demo`，明确为 Demo。TTS 当前为 Windows SAPI WAV。

## 验证

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' -m pytest server/tests -q
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' server/scripts/smoke_demo.py
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' server/scripts/load_test.py
```

Swagger：`http://127.0.0.1:8000/docs`。微信开发者工具默认可访问 localhost；真机需 LAN/HTTPS 地址并配置合法域名。课程 Demo 未连接真实支付、票务、停车硬件或室内定位。
