# 老师问答

## 为什么 LLM 不是摆设？
在线模式由千问完成意图/槽位和 Function Calling 选择；后端执行工具后再回填。scripted 是可明确识别的离线兜底，不冒充在线模型。

## LLM 与规则系统如何分工？
LLM 理解、规划、解释和选工具；规则/后端负责身份、数据事实、SQL、确认门和事务写入。

## Function Calling 如何访问私有数据？
工具注册表提供 JSON Schema；调用时后端剥离模型传来的权限字段，再从认证会话注入 mall/user/session，callback 参数化查询 SQLite。

## “一码一所”如何实现？
扫码绑定 session.mall_id，registry 和每条业务 SQL 都以该值过滤；`mall_demo` 与 `mall_alt` 自动测试证明不串数据。

## 为什么显式状态机？
长任务可持久化、刷新可恢复，并能保证 CONFIRM 之前没有事务写入。一次 Prompt 无法可靠表达权限边界和中间状态。

## 写操作为何确认？
预约、券、票会改变数据库。只有明确 decision=confirm 且计划状态为 CONFIRM，后端才进入 EXECUTE。

## RAG 与结构化查询为何分开？
积分规则是文档条款，适合带来源检索；车位、库存、积分余额是实时结构化事实，必须直接查表。

## 地图路线真实吗？
算法和路网是真实 Dijkstra，实现同层/跨层与电梯换乘；底图和坐标是课程 Demo 仿真，不声称真实室内定位。

## 五场景如何复用？
共享一个状态机和执行器；模板仅声明 required slots、store sequence 和 actions，不复制五套流程。

## 在线模型挂掉怎么办？
记录失败类型和 fallback 计数，显式返回 degraded=true，再走 scripted；不吞异常、不伪称在线成功。

## 双端如何共享？
统一 Token/user_id/session_id 和 SQLite。开发 mock 中 Web 与微信映射到同一 `user_demo`。

## code2session 做什么？
小程序 `wx.login()` 得到临时 code，后端携 AppID/AppSecret 换取 openid/session_key；session_key 不返回前端、不写日志。

## TTS 如何实现？
课程 Demo 通过 Windows SAPI 生成 WAV，接口返回可播放 URL；若系统语音不可用会明确标记 emergency fallback。

## 安全与压测？
覆盖无 Token、跨用户、跨商场、确认绕过、SQL 注入和 Prompt 注入；scripted 下以 16 并发跑 120 个混合只读请求并如实记录 p95。

## 商业上线还缺什么？
真实商场/票务/停车 API、正式微信主体与 HTTPS、真实地图标定和室内定位、生产密钥管理、审计、限流、高可用数据库与合规评估。
