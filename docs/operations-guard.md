# 星河里 Demo 运维保护

## 日常启动

只从仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_demo.ps1
```

启动器会先执行 `server/scripts/ops_guard.py`：

1. 用 SQLite 在线备份 API 备份当前 `mall.db`，不会复制未完成的半个事务；
2. 只补充缺失表、列和 Seed，不删除现有方案、券、预约、商户状态；
3. 执行数据库完整性、外键、店铺/实时状态/地图绑定数量检查；
4. 检查失败时拒绝启动，避免前端连上一个“进程活着但业务数据为空”的后端。

备份保存在 `server/data/backups/`，自动只留最近 5 份，且已由 `.gitignore` 排除。

## 修改前后的发布门禁

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' server/scripts/release_check.py
```

它会执行全量 pytest、连续两轮主演示冒烟和 Web 生产构建。pytest、冒烟、压测全部使用系统临时目录中的独立数据库；脚本还会比对运行前后的真实演示库业务指纹，若测试误改了 `mall.db` 会直接失败。

## Plan 防护规则

- 每个 Plan 返回 `revision`；Web 和小程序编辑/确认时携带 `expected_revision`。
- 两个页面同时编辑同一方案时，后提交的旧版本收到 HTTP 409，必须重新加载，不再静默覆盖新方案。
- 确认操作使用 SQLite 即时事务串行化；网络重试或重复点击同一个已完成方案会返回同一结果，不会重复领券、购票或预约。
- 已执行方案保持不可变；再次调整会复制为新的 `CONFIRM` 草稿。
- 数据库实例更新造成旧 `plan_id` 失效时，客户端使用原途经点创建新草稿，界面不展示内部恢复提示。

## 健康检查

访问 `http://127.0.0.1:8000/health`。只有同时满足以下条件才返回 `ready: true`：

- SQLite `integrity_check` 通过；
- 无外键错误；
- 核心业务表存在；
- 默认商场有店铺；
- 店铺、实时状态、地图绑定数量一致。

不要只看端口是否打开。若返回 503，查看响应中的 `database.issues`，后端也会在启动日志中打印失败原因。

## 故障处置

1. 先停止后端，保留现场，不要删除 `mall.db`。
2. 运行 `ops_guard.py --no-backup` 获取确切一致性错误。
3. 若只是旧进程占端口，重新运行 `run_demo.ps1`，它会关闭本项目遗留的 Python/Node 监听器。
4. 若数据文件确实损坏，先复制当前文件留证，再从 `server/data/backups/` 选择最近一份备份恢复；恢复属于覆盖操作，必须人工确认，脚本不会自动覆盖业务数据。
5. 恢复后运行 `release_check.py`，通过后再让 Web 和小程序重新登录/扫码。

禁止用 `reset_and_seed()`、删除 `mall.db` 或直接运行破坏性 SQL 处理普通联调故障。
