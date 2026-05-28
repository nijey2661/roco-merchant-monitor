#!/usr/bin/env python3
"""
洛克王国远行商人高价值商品监控 v4
- 双源抓取，以最新为准
- 轮次时效校验：数据时间戳必须 >= 当前轮次开始时间
- 高价值商品命中推送，无则静默
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# === 配置 ===
PRIMARY_URL = "https://rocokingdomworld.org/api/merchant/live"
SECONDARY_URL = "https://www.onebiji.com/hykb_tools/comm/lkwgmerchant/preview.php?id=1&immgj=0"
BJT = timezone(timedelta(hours=8))

HIGH_VALUE_KEYWORDS = [
    "炫彩蛋", "炫彩精灵蛋",
    "棱镜球", "织梦棱镜球",
    "祝福项链",
    "国王球",
]

# 轮次定义：(轮次号, 开始时, 结束时)
ROUNDS = [
    (1, 8, 12),
    (2, 12, 16),
    (3, 16, 20),
    (4, 20, 24),
]


def fetch_url(url, headers=None, timeout=20):
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_current_round_info():
    """返回 (轮次号, 轮次开始时间datetime, 轮次结束时间datetime) 或 None"""
    now = datetime.now(BJT)
    h = now.hour
    for round_num, start_h, end_h in ROUNDS:
        if start_h <= h < end_h:
            round_start = now.replace(hour=start_h, minute=0, second=0, microsecond=0)
            round_end = now.replace(hour=end_h, minute=0, second=0, microsecond=0)
            return round_num, round_start, round_end
    return None


def check_high_value(items):
    hits = []
    for item in items:
        name = item.get("name", "")
        for kw in HIGH_VALUE_KEYWORDS:
            if kw in name:
                hits.append(item)
                break
    return hits


def format_item(item):
    name = item.get("name", "未知")
    price = item.get("price", "?")
    limit = item.get("limit", "?")
    cat = item.get("category", "")
    parts = [f"  • {name}"]
    if cat:
        parts.append(f"（{cat}）")
    if price != "?":
        parts.append(f"— {price} 洛克贝")
    if limit != "?":
        parts.append(f"，限购 {limit}")
    return "".join(parts)


# ========== 数据源 1: rocokingdomworld.org ==========

def fetch_primary(round_start):
    """
    返回 (items, is_current_round, freshness_desc, error)
    is_current_round: 数据是否属于当前轮次（fetchedAt >= round_start）
    """
    try:
        raw = fetch_url(PRIMARY_URL)
        data = json.loads(raw)
    except Exception as e:
        return [], False, "", str(e)

    # 解析 fetchedAt
    fetched_at = data.get("fetchedAt", "")
    is_current = False
    freshness_desc = "未知"
    if fetched_at:
        try:
            fetched_dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            fetched_bjt = fetched_dt.astimezone(BJT)
            age_sec = int((datetime.now(BJT) - fetched_bjt).total_seconds())
            freshness_desc = f"{fetched_bjt.strftime('%H:%M')}（{age_sec // 60}分钟前）"

            # 关键判断：数据抓取时间是否 >= 当前轮次开始时间
            is_current = fetched_bjt >= round_start
        except Exception:
            pass

    # 获取当前轮次商品
    round_num = get_current_round_info()[0]
    rounds = data.get("rounds", {})
    items = rounds.get(str(round_num), rounds.get(round_num, []))
    items = items + data.get("items", [])

    # 去重
    seen = set()
    unique = []
    for item in items:
        n = item.get("name", "")
        if n not in seen:
            seen.add(n)
            unique.append(item)

    return unique, is_current, freshness_desc, None


# ========== 数据源 2: onebiji.com ==========

def fetch_secondary():
    """返回 (items, error) — HTML 实时页面，无时间戳，抓到即认为是当前数据"""
    try:
        html = fetch_url(SECONDARY_URL, {"Referer": "https://www.onebiji.com/"})
    except Exception as e:
        return [], str(e)

    items = []

    # 方法1: show_dialog / show_dialog_new 中的商品数据
    dialogs = re.findall(
        r"show_dialog(?:_new)?\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]",
        html
    )
    for name, category, desc in dialogs:
        if any(k in name for k in ['球', '蛋', '矿', '粉', '石', '果', '药', '链', '珠', '玉', '璃']):
            items.append({"name": name, "category": category})

    # 方法2: "·商品名 NNN洛克贝" 或 "·商品名 NNw洛克贝"（w=万）
    name_price = re.findall(r'·\s*([^\s<·]+?)\s+(\d+w?)洛克贝', html)
    for name, price in name_price:
        name = name.strip()
        if name and len(name) < 20:
            if not any(i["name"] == name for i in items):
                items.append({"name": name, "price": price})

    # 去重
    seen = set()
    unique = []
    for item in items:
        if item["name"] not in seen:
            seen.add(item["name"])
            unique.append(item)

    return unique, None


# ========== 主逻辑 ==========

def main():
    now = datetime.now(BJT)
    round_info = get_current_round_info()
    if round_info is None:
        return  # 非营业时间，静默

    current_round, round_start, round_end = round_info
    round_label = {1: "08:00-12:00", 2: "12:00-16:00", 3: "16:00-20:00", 4: "20:00-24:00"}

    # === 抓取两个源 ===
    primary_items, primary_is_current, primary_fresh_desc, primary_err = fetch_primary(round_start)
    secondary_items, secondary_err = fetch_secondary()

    # 两个都失败
    if primary_err and secondary_err:
        print(f"⚠️ 两个数据源都抓取失败，请手动检查游戏。")
        return

    # === 判断数据时效 ===
    # 主源：有 fetchedAt，可以精确判断是否属于当前轮次
    # 副源：HTML 实时页面，抓到即用，无法判断服务端缓存是否过期
    # 但如果我们同时有主源的 fetchedAt，可以间接推断副源是否也可能过期

    primary_names = sorted([i["name"] for i in primary_items])
    secondary_names = sorted([i["name"] for i in secondary_items])
    sources_agree = (primary_names == secondary_names)

    # === 选择权威源 ===
    if sources_agree and primary_items:
        # 两源一致 → 用主源（信息更全）
        best_items = primary_items
        best_label = "双源一致"
        data_is_current = primary_is_current  # 以主源时间为准
    elif primary_err:
        # 主源失败 → 用副源，但无法验证时效
        best_items = secondary_items
        best_label = "仅副源（onebiji）"
        data_is_current = True  # 副源是实时页面，假设当前（无法精确验证）
    elif secondary_err:
        # 副源失败 → 用主源
        best_items = primary_items
        best_label = f"仅主源（数据来自 {primary_fresh_desc}）"
        data_is_current = primary_is_current
    elif primary_is_current:
        # 主源属于当前轮次 → 用主源
        best_items = primary_items
        best_label = f"主源（数据来自 {primary_fresh_desc}）"
        data_is_current = True
    else:
        # 主源过期 → 用副源（实时页面更可能有新数据）
        best_items = secondary_items
        best_label = f"副源（主源数据来自 {primary_fresh_desc}，属于上一轮）"
        data_is_current = True  # 副源抓到就用

    # === 高价值检测 ===
    hits = check_high_value(best_items)

    if hits:
        print(f"🎁 洛克王国远行商人刷出高价值商品！")
        print(f"⏰ {now.strftime('%H:%M')} 第{current_round}轮（{round_label.get(current_round, '')}）")
        print(f"📡 {best_label}")
        print()
        for item in hits:
            print(format_item(item))
        print()
        print("快上线购买！")

        # 两源不一致时补充说明
        if not sources_agree and not primary_err and not secondary_err:
            other = secondary_names if best_items == primary_items else primary_names
            diff = set(other) - set(primary_names if best_items == primary_items else secondary_names)
            if diff:
                print(f"\n⚠️ 另一源还显示: {', '.join(diff)}（未确认）")
        return

    # 无高价值商品
    if not data_is_current:
        # 数据可能不是当前轮次的，提醒用户
        print(f"⚠️ 第{current_round}轮数据可能未刷新")
        print(f"⏰ {now.strftime('%H:%M')}（{round_label.get(current_round, '')}）")
        print(f"📡 {best_label}")
        if best_items:
            print(f"当前显示: {', '.join(primary_names if best_items == primary_items else secondary_names)}")
        print("建议稍后再查或手动确认。")
        return

    # 两源不一致但都无高价值 → 告知差异
    if not sources_agree and not primary_err and not secondary_err:
        print(f"ℹ️ 第{current_round}轮两源商品不一致，但均无高价值物品。")
        print(f"  主源: {', '.join(primary_names) if primary_names else '无'}")
        print(f"  副源: {', '.join(secondary_names) if secondary_names else '无'}")

    # 正常静默（两源一致，无高价值，数据属于当前轮次）


if __name__ == "__main__":
    main()
