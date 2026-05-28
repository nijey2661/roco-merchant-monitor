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
- **主源：** rocokingdomworld.org（JSON，有 `fetchedAt` 时间戳，可精确校验时效）
- **副源：** onebiji.com（HTML 实时渲染页面，无时间戳但数据通常更新较快）
- 两源交叉验证，不一致时以最新/最可信的为准

## When to Use

- 用户玩《洛克王国：世界》，想蹲远行商人的稀有商品
- 需要定时自动检查并在高价值商品出现时收到提醒
- 想了解远行商人当前卖什么

## Quick Start

### 1. 部署监控脚本

将脚本放到 `~/.hermes/scripts/roco_merchant_check.py`，内容见 [scripts/roco_merchant_check.py](scripts/roco_merchant_check.py)。

### 2. 创建定时任务

远行商人每天 08:00、12:00、16:00、20:00 北京时间刷新商品，建议在刷新后 15 分钟执行（给数据源更新时间）：

```
cronjob create:
  name: 洛克王国远行商人高价值监控
  schedule: "15 0,4,8,12 * * *"   # UTC 时间，对应北京时间 08:15/12:15/16:15/20:15
  script: roco_merchant_check.py
  no_agent: true
  deliver: origin
```

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
- [ ] 手动运行脚本确认无报错
- [ ] Cron 任务已创建，schedule 为 `15 0,4,8,12 * * *`
- [ ] `no_agent: true`（纯脚本执行，不消耗 token）
- [ ] `HIGH_VALUE_KEYWORDS` 已按需自定义
- [ ] 首次运行后确认消息推送正常
