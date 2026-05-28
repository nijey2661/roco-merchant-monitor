---
name: roco-merchant-monitor
description: >
  Use when the user wants to monitor Roco Kingdom (洛克王国：世界) Traveling Merchant (远行商人)
  for high-value items and get notified when they appear. Supports dual-source data fetching,
  freshness validation, and automatic alerts via cron. Triggers: "洛克王国远行商人",
  "远行商人监控", "商人提醒", "roco merchant", "洛克王国提醒".
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gaming, monitoring, cron, notification, roco-kingdom]
    related_skills: []
---

# 洛克王国远行商人高价值商品监控

## Overview

自动监控《洛克王国：世界》远行商人的商品刷新，在出现高价值商品（炫彩蛋、棱镜球、祝福项链、国王球）时推送提醒，无则静默。

**数据链路：**
- **主源：** rocokingdomworld.org `/api/merchant/live`（实时 JSON API，有 `fetchedAt` 时间戳）
- **副源：** onebiji.com（HTML 实时渲染页面，无时间戳但数据通常更新较快）
- 两源交叉验证，不一致时以最新/最可信的为准
- ⚠️ 同一网站还有 `/data/merchant.json`（静态缓存，更新极慢），**不要用这个**

## When to Use

- 用户玩《洛克王国：世界》，想蹲远行商人的稀有商品
- 需要定时自动检查并在高价值商品出现时收到提醒
- 想了解远行商人当前卖什么

## Quick Start

### 1. 部署监控脚本

将脚本放到 `~/.hermes/scripts/roco_merchant_check.py`，内容见 [scripts/roco_merchant_check.py](scripts/roco_merchant_check.py)。

### 2. 创建定时任务

远行商人每天 08:00、12:00、16:00、20:00 北京时间刷新商品，建议在刷新后 15 分钟执行（给数据源更新时间）。**注意：Hermes cron 表达式按部署机器/调度器本地时区解释，不一定是 UTC。先确认 `date` 输出的时区，再写 cron 表达式：**

- 如果机器是北京时间 / `Asia/Shanghai`：用 `15 8,12,16,20 * * *`
- 只有当调度器明确使用 UTC 时，才用 `15 0,4,8,12 * * *`

```
cronjob create:
  name: 洛克王国远行商人高价值监控
  schedule: "15 8,12,16,20 * * *"   # 北京时间机器：08:15/12:15/16:15/20:15
  script: roco_merchant_check.py
  no_agent: true
  deliver: origin
```

验证创建后一定要看 `next_run_at`，确认下一次运行时间落在预期的北京时间轮次后。例如现在是 19:00，北京时间机器上 `next_run_at` 应该是当天 20:15；如果显示次日 00:15，说明时区/表达式写错了。

### 3. 自定义高价值商品

编辑脚本中的 `HIGH_VALUE_KEYWORDS` 列表：

```python
HIGH_VALUE_KEYWORDS = [
    "炫彩蛋", "炫彩精灵蛋",
    "棱镜球", "织梦棱镜球",
    "祝福项链",
    "国王球",
    # 添加更多...
    # "暗星球", "网兜球",
]
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Cron 触发 (每轮刷新后 15 分钟)                    │
│  08:15 / 12:15 / 16:15 / 20:15 北京时间           │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
  ┌───────────────┐        ┌───────────────┐
  │ 主源 (JSON)    │        │ 副源 (HTML)    │
  │ rocokingdom-   │        │ onebiji.com   │
  │ world.org      │        │               │
  │ 有 fetchedAt   │        │ 无时间戳       │
  └───────┬───────┘        └───────┬───────┘
          │                        │
          └────────┬───────────────┘
                   ▼
        ┌─────────────────┐
        │ 轮次时效校验      │
        │ fetchedAt >=     │
        │ 本轮开始时间？    │
        └────────┬────────┘
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
  两源一致    主源新鲜     主源过期
  → 用主源   → 用主源    → 用副源
                 │
                 ▼
        ┌─────────────────┐
        │ 高价值商品检测    │
        └────────┬────────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
      命中             未命中
   🎁 推送提醒      🔇 静默
```

## Key Design Decisions

### 为什么刷新后 15 分钟而不是 5 分钟？

数据源（尤其是 rocokingdomworld.org）可能有 5-15 分钟的更新延迟。实测中主源曾出现 8 小时未更新的情况。15 分钟的延迟能覆盖大多数正常更新场景。

### 为什么需要轮次时效校验？

不能只看"数据有多新"。例如 12:15 执行时，数据可能是 11:29 抓取的——虽然只过了 46 分钟，但它是上一轮的数据，商品已经换了。所以要判断 `fetchedAt >= 本轮开始时间`。

### 两源不一致怎么办？

- **都新鲜且一致** → 用主源（信息更全，有价格/限购）
- **主源过期** → 自动 fallback 到副源（实时 HTML 页面）
- **两源不一致** → 以更新时间更新的为准，并在输出中标注差异

## Common Pitfalls

1. **用错了主源 URL。** rocokingdomworld.org 有两个端点：
   - `/api/merchant/live` — **实时 API**，浏览器 JS 优先请求这个，数据最新
   - `/data/merchant.json` — 静态缓存，更新极慢（实测曾 8 小时不更新）
   - **必须用 `/api/merchant/live`**，否则拿到的是过期数据

2. **onebiji.com 的价格格式不只纯数字。** 血脉秘药的价格是 `16w洛克贝`（w=万），不是 `160000洛克贝`。正则必须支持 `\d+w?` 而非仅 `\d+`。

3. **onebiji.com 的函数名有变体。** 商品数据在 `show_dialog(...)` 和 `show_dialog_new(...)` 两种 onclick 中，正则要用 `show_dialog(?:_new)?`。

4. **`no_agent: true` 的 cron job 会把 stdout 原样推送给用户。** 脚本设计原则：只有高价值商品命中时才输出，其他情况（包括两源不一致但无高价值）一律静默。否则用户会收到大量无用通知。

5. **两源不一致 ≠ 一定有问题。** onebiji HTML 解析可能漏抓商品（如价格格式不匹配），不代表游戏里有惊喜商品。不要因为两源不一致就输出警告——只有高价值命中才通知。

6. **跨午夜轮次不能用 `hour=24`。** Python `datetime.replace(hour=24)` 会抛 `ValueError: hour must be in 0..23`，导致 20:00-24:00 这类最后一轮在晚上执行失败。轮次结束为 24:00 时，应表示为“次日 00:00”：`(now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)`。

7. **不要默认把 Hermes cron 当成 UTC。** cron 表达式通常按调度器/机器本地时区解释。在北京时间部署中，`15 0,4,8,12 * * *` 实际是 00:15/04:15/08:15/12:15，不会跑 20:15。创建或更新后必须检查 `next_run_at`。

7. **确认 Hermes cron 的时区，不要盲目按 UTC 换算。** 在当前部署里，cron 表达式按本机 `Asia/Shanghai/+0800` 解释。远行商人 08:15/12:15/16:15/20:15 北京时间应写成 `15 8,12,16,20 * * *`，不是 `15 0,4,8,12 * * *`。如果迁移到其他机器，先用 `date` / cron `next_run_at` 验证调度时区，再决定是否换算。

## Limitations

| ✅ 能做到 | ❌ 做不到 |
|-----------|-----------|
| 检测预设排期中的高价值商品 | 100% 捕获运营临时上架的商品 |
| 验证数据是否属于当前轮次 | 访问游戏内部 API |
| 双源交叉验证减少误判 | 比数据源更快发现变化 |
| 数据过期时发出警告 | 强制数据源更新 |

**临时上架商品：** 5月22日的祝福项链、炫彩蛋是运营临时加入的。这类商品不在预设排期中，但只要数据源及时更新（通常在商品上架后几分钟到半小时内），脚本就能抓到。

## Data Sources

详见 [references/data-sources.md](references/data-sources.md) — 包含两个数据源的 API 详情、返回格式、解析方法和实测踩坑记录。

## Troubleshooting

### "⚠️ 数据可能未刷新"
- 数据源还没更新本轮数据
- 等几分钟后手动运行脚本确认
- 如果经常发生，考虑将 cron 时间从 +15min 调到 +20min 或 +30min

### "⚠️ 两个数据源都抓取失败"
- 检查网络连接
- 数据源可能临时不可用，稍后重试
- rocokingdomworld.org 偶尔会有 Cloudflare 验证拦截

### 想监控更多商品
编辑 `HIGH_VALUE_KEYWORDS`，支持模糊匹配（`"棱镜"` 会匹配 `"织梦棱镜球"`）。

## Cron Job Management

```bash
# 查看任务状态
hermes cron list

# 手动触发一次测试
hermes cron run <job_id>

# 暂停（比如活动结束不需要了）
hermes cron pause <job_id>

# 恢复
hermes cron resume <job_id>

# 删除
hermes cron remove <job_id>
```

## Verification Checklist

- [ ] 脚本已放到 `~/.hermes/scripts/roco_merchant_check.py`
- [ ] 晚上第 4 轮（20:00-24:00）手动运行脚本确认不会因 `hour=24` 报错
- [ ] Cron 任务已创建，schedule 为 `15 8,12,16,20 * * *`（当前部署按北京时间解释；迁移环境时先验证时区）
- [ ] Cron 任务已创建，schedule 为 `15 8,12,16,20 * * *`（北京时间机器）或已按实际调度器时区换算
- [ ] 创建/更新后已检查 `next_run_at`，确认下一次运行是预期的 08:15/12:15/16:15/20:15 北京时间
- [ ] `HIGH_VALUE_KEYWORDS` 已按需自定义
- [ ] 首次运行后确认消息推送正常
