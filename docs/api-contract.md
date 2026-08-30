# QD square API 契约（冻结版）

Base URL：`http://127.0.0.1:8000`。除音频/地图文件外，响应统一为 `{code,message,request_id,timestamp,data}`。受保护接口使用 `Authorization: Bearer <token>`。

身份链：`web-login|wx-login → token/user_id → scan(mall_id) → session_id`。模型和用户工具参数不能覆盖后端会话中的 `user_id/mall_id/session_id`。

| 方法 | 路径 | 核心输入 | data / 卡片 |
|---|---|---|---|
| GET | `/health` | - | status、LLM/TTS 模式 |
| POST | `/api/auth/web-login` | username,password | token,user_id |
| POST | `/api/auth/wx-login` | code | token,user_id,wx_auth_mode |
| POST | `/api/scan` | mall_id,session_id? | session_id,mall,map_manifest |
| POST | `/api/chat` | session_id,message | reply,intent,tool_calls,result,cards,plan? |
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

卡片 `type` 冻结为：`parking`、`member`、`rag`、`deals`、`stores`、`plan`、`itinerary`。路线节点固定字段：`sequence,node_id,floor,x,y,type,label`；线段固定字段：`floor,from,to,transfer_instruction`。
