# 星河里 API 契约（冻结版）

Base URL：`http://127.0.0.1:8000`。除音频/地图文件外，响应统一为 `{code,message,request_id,timestamp,data}`。受保护接口使用 `Authorization: Bearer <token>`。

身份入口严格分离：游客/会员使用 `phone-login → AI service code scan → visitor workspace`；商户使用 `store-code → merchant workspace`；管理者使用 `web-login → manager workspace`。`wx-login` 作为真实 `code2session` 兼容适配继续保留，但不再是当前游客 UI 的登录方式。前端不在登录后提供角色切换，后端同时按 token channel 与访问关系表阻断跨角色请求。模型和用户工具参数不能覆盖后端会话中的 `user_id/mall_id/session_id`。

| 方法 | 路径 | 核心输入 | data / 卡片 |
|---|---|---|---|
| GET | `/health` | - | status、LLM/TTS 模式 |
| POST | `/api/auth/phone-login` | phone,password | visitor token,user_id,phone_masked |
| POST | `/api/auth/web-login` | username,password | token,user_id |
| POST | `/api/auth/wx-login` | code | token,user_id,wx_auth_mode |
| POST | `/api/merchant/auth/store-code` | store_code | merchant token,store_id |
| POST | `/api/scan` | service_code? 或 mall_id,session_id? | session_id,mall,entry_node,datasource_connection,map_manifest |
| POST | `/api/chat` | session_id,message | reply,intent,tool_calls,result,cards,plan?,navigation? |
| POST | `/api/navigation/resolve` | session_id,query,current_node? | route_animation |
| GET | `/api/maps/{mall_id}/scene` | Bearer | 2.5D scene + store hotspots/status |
| GET | `/api/stores/{store_id}/public-status` | mall_id | 游客可见营业/排队/优惠 |
| GET/PATCH | `/api/merchant/store[/status]` | merchant token | 本店资料与实时状态 |
| PUT | `/api/merchant/store/deals` | merchant token,title,price,stock | 发布优惠 |
| GET | `/api/manager/analytics` | manager token,granularity | 日/月/年经营分析（Mock 标识） |
| POST | `/api/manager/stores` | manager token,店铺资料 | 店铺与商户编码 |
| POST | `/api/manager/maps` | manager token,source_name | 2.5D 初稿任务、人工校准标识 |
| GET | `/api/tools/schema` | Bearer | 工具 JSON Schema |
| POST | `/api/plan/date`、`/api/plan/goal` | session_id,text/scene/slots | PlanCard、route、state |
| GET | `/api/plan/route?plan_id=` | plan_id | route nodes/polyline_segments |
| POST | `/api/plan/confirm` | plan_id,decision | DONE itinerary + action_results |
| GET | `/api/plan/live-status?plan_id=` | plan_id | queue/open/seats/ticket_stock |
| GET | `/api/parking?session_id=` | session_id | areas,total_free |
| GET | `/api/member/points?session_id=` | session_id | points,level,expires_on |
| GET | `/api/deals?session_id=` | session_id | deal[] |
| POST | `/api/coupons/claim` | session_id,coupon_id,confirmed | 领取结果 |
| POST/GET | `/api/reservations` | 写入需 confirmed | 预约结果/本人预约 |
| DELETE | `/api/reservations/{id}` | 本人预约 ID | cancelled |
| GET | `/api/tickets/products`、`/api/tickets/my` | session_id/本人 | 产品/本人票 |
| POST | `/api/tts` | text | audio_id,audio_url,mime_type,tts_mode |
| GET | `/api/audio/{audio_id}` | - | WAV 文件 |
| GET | `/api/maps/{mall_id}/{file}` | - | SVG/JSON 地图资源 |
| GET | `/api/debug/metrics` | Bearer | 课程级指标 |

卡片 `type` 冻结为：`parking`、`member`、`rag`、`deals`、`stores`、`plan`、`itinerary`、`route_animation`。路线节点固定字段：`sequence,node_id,floor,x,y,type,label`；线段固定字段：`floor,from,to,transfer_instruction`。只有目的地导航意图返回 `navigation.type=route_animation`，攻略、优惠、会员等普通问答不得携带该字段。

AI 服务二维码使用微信小程序码的 `scene` 传递服务码，例如 `QD-AI-DEMO`。后端表 `mall_service_codes` 将服务码解析为 `mall_id + entry_node`；若同时传入其他 `mall_id`，服务码映射优先。所有 AI 回复均为纯文本，服务端和双端显示层都会移除星号，避免未渲染的 Markdown 粗体符号出现在界面。
