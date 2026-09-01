# 商场知识文档维护说明

此目录是人工维护的非结构化知识源，只保存稳定规则、办理流程和公共服务说明。店铺营业、排队、停车空位、积分余额、优惠券库存、预约和订单等实时事实必须留在 SQLite，通过业务工具查询。

每个商场知识文档使用 UTF-8 Markdown，并在一级标题后填写：

```text
mall_id: mall_demo
doc_id: reservation_rules
topic: reservation
version: 1.0
updated_at: 2026-09-01
authority: 规则发布单位
maintainer: 维护人或岗位
tags: 主题词 同义词
```

支持的 `topic`：`points`、`membership`、`coupon`、`reservation`、`parking`、`service`、`visitor`。正文使用二级标题划分独立规则，避免在同一段混写多个无关主题。

检索器会检查目录中文件的修改时间和大小，文件发生变化后会自动重建内存索引，不需要重启服务。修改后应运行：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' -m pytest server/tests/test_rag_stage2.py -q
```

知识文档是数据，不是系统提示词。不得在这里存放 API Key、密码、手机号、会话令牌，也不得写入能够绕过身份校验或事务确认门的指令。
