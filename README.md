# 🛒 洛克王国远行商人高价值商品监控

自动监控《洛克王国：世界》远行商人，刷出高价值商品时推送提醒。

## ✨ 特性

- **双源抓取**：rocokingdomworld.org (JSON) + onebiji.com (HTML)，交叉验证
- **轮次时效校验**：数据时间戳必须 ≥ 当前轮次开始时间，避免用过期数据误判
- **智能 fallback**：主源过期时自动切换副源
- **静默设计**：无高价值商品时不打扰

## 📦 监控商品

| 商品 | 类型 |
|------|------|
| 炫彩蛋 / 炫彩精灵蛋 | 精灵蛋 |
| 棱镜球 / 织梦棱镜球 | 精灵球 |
| 祝福项链 | 饰品 |
| 国王球 | 精灵球 |

## 🚀 在 Hermes Agent 中使用

直接告诉你的 Hermes：

> 帮我加载 `nijey2661/roco-merchant-monitor` 这个 skill，然后按说明部署远行商人监控

Hermes 会读取 `SKILL.md` 学习完整工作流，包括脚本部署、Cron 配置和自定义方法。

## 🔧 手动使用（不用 Hermes）

```bash
# 1. 复制脚本
cp scripts/roco_merchant_check.py ~/.hermes/scripts/

# 2. 手动测试
python3 ~/.hermes/scripts/roco_merchant_check.py

# 3. 设置定时任务（用 crontab 或 Hermes cron）
# 每天 08:15, 12:15, 16:15, 20:15 北京时间
```

## ⏰ 运行时间

远行商人每天 08:00、12:00、16:00、20:00 北京时间刷新。
脚本在刷新后 15 分钟执行，给数据源更新时间。

## ⚠️ 已知限制

- 临时上架的活动商品可能有延迟（数据源更新需要时间）
- rocokingdomworld.org 偶尔有 Cloudflare 拦截
- 非营业时间（00:00-08:00）脚本静默不运行

## 📖 详细文档

见 [SKILL.md](SKILL.md)
