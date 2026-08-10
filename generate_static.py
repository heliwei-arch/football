"""Vercel 构建时使用：生成所有静态 JSON 数据到 public/data/ 目录
这样前端就可以直接 fetch /data/*.json，不需要动态后端 API。
"""
import json
import os
import sys
import random
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(PUBLIC_DIR, "data")

sys.path.insert(0, BASE_DIR)
from data import (
    LEAGUES,
    generateYesterdayMatches,
    generateTodayPreviews,
    generatePushDigest,
    formatDate,
    getToday,
)


def save_json(relpath, obj):
    fp = os.path.join(DATA_DIR, relpath)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 写入 {relpath}")


def main():
    print(f"\n🚀 Vercel 构建：正在生成静态数据（日期：{formatDate(getToday())}）...\n")
    random.seed()
    timestamp = datetime.now().isoformat()

    yesterday_matches = generateYesterdayMatches()
    today_previews = generateTodayPreviews()
    push_digest = generatePushDigest(yesterday_matches, today_previews)

    # 加载历史推送
    push_history = []
    cache_file = os.path.join(BASE_DIR, "cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                old_cache = json.load(f)
            push_history = old_cache.get("pushHistory") or []
        except Exception:
            pass

    # 插入本次推送记录
    push_history.insert(0, {
        "timestamp": timestamp,
        "manual": False,
        "digest": push_digest,
    })
    push_history = push_history[:30]

    # 1. dashboard.json = /api/dashboard 全量数据（支持按region过滤在前端做）
    dashboard = {
        "lastUpdate": timestamp,
        "generatedAt": datetime.now().isoformat(),
        "leagues": LEAGUES,
        "yesterdayMatches": yesterday_matches,
        "todayPreviews": today_previews,
        "pushDigest": push_digest,
    }
    save_json("dashboard.json", dashboard)

    # 2. health.json
    save_json("health.json", {
        "status": "ok",
        "deployedAt": timestamp,
        "lastUpdate": timestamp,
        "hasData": len(yesterday_matches) > 0,
        "note": "Vercel 静态部署版，每天 9:00(Asia/Shanghai) 通过 Deploy Hook 自动重建",
    })

    # 3. push-latest.json
    save_json("push-latest.json", {
        "lastUpdate": timestamp,
        "latest": push_digest,
        "history": push_history[:5],
    })

    # 4. push-history.json
    save_json("push-history.json", {"history": push_history})

    # 5. 分区域的dashboard（可选，加速前端切换）
    for region in ["europe", "asia", "australia"]:
        ym = [m for m in yesterday_matches if m.get("region") == region]
        tp = [m for m in today_previews if m.get("region") == region]
        save_json(f"dashboard-{region}.json", {
            "lastUpdate": timestamp,
            "generatedAt": datetime.now().isoformat(),
            "leagues": {region: LEAGUES[region]},
            "yesterdayMatches": ym,
            "todayPreviews": tp,
            "pushDigest": push_digest,
        })

    print(f"\n🎉 构建完成：昨日 {len(yesterday_matches)} 场 / 今日 {len(today_previews)} 场预告\n")


if __name__ == "__main__":
    main()
