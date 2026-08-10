"""Vercel 构建时使用：生成所有静态 JSON 数据到 public/data/ 目录
数据源优先级：
  1. crawl_dongqiudi 懂球帝公开真实接口（今日/昨日/裁判按区域分配）
  2. data.py 内置 Mock 生成函数（兜底，懂球帝接口失败/限频/空数据时启用）
"""
import json
import os
import sys
import random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(PUBLIC_DIR, "data")

sys.path.insert(0, BASE_DIR)
from data import (
    LEAGUES,
    generateYesterdayMatches,
    generateTodayPreviews,
    generatePushDigest,
    generateKeyEvents,
    generateMatchAnalysis,
    analyzeRefereeStyle,
    generateRefereeHistory,
    formatDate,
    getToday,
    getYesterday,
    pick,
    rand,
)


def save_json(relpath, obj):
    fp = os.path.join(DATA_DIR, relpath)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 写入 {relpath}")


# ------------- 懂球帝 → 前端兼容结构 Adapter -------------

def _region_flag(region, league_name, area_name):
    """根据联赛名/区域名给出一个旗帜emoji"""
    mapping = {
        "europe": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "asia": "🏆",
        "australia": "🇦🇺",
    }
    name = f"{league_name}{area_name}"
    if "澳" in name: return "🇦🇺"
    if "新西兰" in name: return "🇳🇿"
    if "中国" in name or "中超" in name or "村超" in name: return "🇨🇳"
    if "日本" in name or "日职" in name or "J联赛" in name: return "🇯🇵"
    if "韩国" in name or "韩职" in name or "K联赛" in name: return "🇰🇷"
    if "乌兹别克" in name: return "🇺🇿"
    if "科威特" in name: return "🇰🇼"
    if "缅甸" in name: return "🇲🇲"
    if "英格兰" in name or "英超" in name: return "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
    if "西班牙" in name or "西甲" in name: return "🇪🇸"
    if "德国" in name or "德甲" in name: return "🇩🇪"
    if "意大利" in name or "意甲" in name: return "🇮🇹"
    if "法国" in name or "法甲" in name: return "🇫🇷"
    if "荷兰" in name: return "🇳🇱"
    if "葡萄牙" in name: return "🇵🇹"
    if "乌克兰" in name: return "🇺🇦"
    if "罗马尼亚" in name: return "🇷🇴"
    if "斯洛文尼亚" in name: return "🇸🇮"
    if "冰岛" in name: return "🇮🇸"
    if "北爱尔兰" in name: return "🇬🇧"
    if "挪威" in name: return "🇳🇴"
    if "瑞典" in name: return "🇸🇪"
    if "丹麦" in name: return "🇩🇰"
    if "爱沙尼亚" in name: return "🇪🇪"
    if "亚美尼亚" in name: return "🇦🇲"
    if "保加利亚" in name: return "🇧🇬"
    if "白俄罗斯" in name: return "🇧🇾"
    if "立陶宛" in name: return "🇱🇹"
    if "大冠杯" in name or "大洋洲" in name: return "🏆"
    return mapping.get(region, "⚽")


def _build_league_obj(region, league_name, league_color, area_name):
    """构建 data.py 兼容的 league dict 结构"""
    lid = f"dqd-{region}-{league_name}"
    return {
        "id": lid,
        "name": league_name,
        "country": area_name or region,
        "flag": _region_flag(region, league_name, area_name),
        "color": league_color or "#666",
        "region": region,
    }


def _adapt_stats(dqd_stats, home_score, away_score):
    """把懂球帝风格的stats → data.py前端兼容stats结构"""
    anchors = dqd_stats.pop("_anchors", {}) if isinstance(dqd_stats, dict) else {}
    # xG → 2位字符串
    def s_xg(v):
        try:
            return f"{float(v):.2f}"
        except Exception:
            return "0.80"
    # 传球准确率 → 带%字符串
    def s_pct(v):
        try:
            return f"{float(v):.0f}%"
        except Exception:
            return "78%"

    return {
        "score": {"home": int(home_score or 0), "away": int(away_score or 0)},
        "possession": {"home": float(dqd_stats.get("possession", {}).get("home", 50)),
                       "away": float(dqd_stats.get("possession", {}).get("away", 50))},
        "shots": {"home": int(dqd_stats.get("shots", {}).get("home", 10)),
                  "away": int(dqd_stats.get("shots", {}).get("away", 10))},
        "shotsOnTarget": {"home": int(dqd_stats.get("shotsOnTarget", {}).get("home", 4)),
                          "away": int(dqd_stats.get("shotsOnTarget", {}).get("away", 4))},
        "xG": {"home": s_xg(dqd_stats.get("xg", {}).get("home", 1.0)),
               "away": s_xg(dqd_stats.get("xg", {}).get("away", 1.0))},
        "passes": {"home": 300 + int(dqd_stats.get("possession", {}).get("home", 50) * 5),
                   "away": 300 + int(dqd_stats.get("possession", {}).get("away", 50) * 5)},
        "passAccuracy": {"home": s_pct(dqd_stats.get("passAccuracy", {}).get("home", 78)),
                         "away": s_pct(dqd_stats.get("passAccuracy", {}).get("away", 78))},
        "tackles": {"home": int(dqd_stats.get("tackles", {}).get("home", 16)),
                    "away": int(dqd_stats.get("tackles", {}).get("away", 16))},
        "interceptions": {"home": int(dqd_stats.get("interceptions", {}).get("home", 10)),
                          "away": int(dqd_stats.get("interceptions", {}).get("away", 10))},
        "fouls": {"home": int(dqd_stats.get("fouls", {}).get("home", 14)),
                  "away": int(dqd_stats.get("fouls", {}).get("away", 14))},
        "corners": {"home": int(dqd_stats.get("corners", {}).get("home", 4)),
                    "away": int(dqd_stats.get("corners", {}).get("away", 4))},
        "yellowCards": {"home": int(anchors.get("yc_home", 0) if anchors else 0),
                        "away": int(anchors.get("yc_away", 0) if anchors else 0)},
        "redCards": {"home": int(anchors.get("rc_home", 0) if anchors else 0),
                     "away": int(anchors.get("rc_away", 0) if anchors else 0)},
        "offsides": {"home": int(dqd_stats.get("offsides", {}).get("home", 2)),
                     "away": int(dqd_stats.get("offsides", {}).get("away", 2))},
        "saves": {"home": int(dqd_stats.get("saves", {}).get("home", 3)),
                  "away": int(dqd_stats.get("saves", {}).get("away", 3))},
        "_anchors": anchors,
        "_fromDongqiudi": True,
    }


def _adapt_referee_history(dqd_history):
    """dqd历史5条 → data.py analyzeRefereeStyle 兼容（需含 cardIndex、varChecks）"""
    out = []
    for h in dqd_history:
        y = int(h.get("yellowCards", 0)); r = int(h.get("redCards", 0))
        out.append({
            "date": h.get("date", ""),
            "league": h.get("league", ""),
            "match": h.get("match", ""),
            "yellowCards": y,
            "redCards": r,
            "fouls": int(h.get("fouls", 22)),
            "penalties": int(h.get("penalties", 0)),
            "cardIndex": round(y * 10 + r * 25, 1),  # 发牌指数
            "varChecks": max(0, (y + r * 2) // 3 + rand(0, 1)),
        })
    return out


def _adapt_referee_analysis(dqd_referee):
    """懂球帝裁判对象 → data.py analyzeRefereeStyle 返回结构"""
    referee_meta = {
        "id": f"dqd-{dqd_referee.get('name','x')}",
        "name": dqd_referee.get("name", "未知裁判"),
        "country": dqd_referee.get("country", ""),
        "age": dqd_referee.get("age", 40),
    }
    history = _adapt_referee_history(dqd_referee.get("history", []))
    # 用 data.py 的 analyzeRefereeStyle 统一计算一次，确保前端字段全齐
    return analyzeRefereeStyle(referee_meta, history or _adapt_referee_history(
        [{"date":"","league":"","match":"","yellowCards":3,"redCards":0,"fouls":22,"penalties":0} for _ in range(5)]
    ))


def adapt_yesterday(dqd_list, region):
    out = []
    for m in dqd_list:
        home_name = m["homeTeam"]["name"]
        away_name = m["awayTeam"]["name"]
        league = _build_league_obj(region, m.get("league", ""), m.get("leagueColor", "#666"),
                                    m.get("league") and m.get("league") or "")
        try:
            parts = m.get("kickoff", "19:30:00").split(" ")[1].split(":")
            match_time = f"{parts[0]}:{parts[1]}"
            match_date = m.get("kickoff", "1970-01-01").split(" ")[0]
        except Exception:
            match_time = "19:30"; match_date = formatDate(getYesterday())
        stats = _adapt_stats(m.get("stats", {}), m["homeTeam"].get("score", 0), m["awayTeam"].get("score", 0))
        referee_analysis = _adapt_referee_analysis(m.get("referee", {}))
        key_events = generateKeyEvents(home_name, away_name, stats)
        analysis = generateMatchAnalysis(home_name, away_name, stats, referee_analysis)
        # gender：优先从 crawl_dongqiudi.py 打标的 gender 透传；否则（Mock fallback）用统一判定函数重判
        gender = m.get("gender")
        if gender not in ("men", "women"):
            try:
                from crawl_dongqiudi import detect_match_gender
                gender, _kw, _hs = detect_match_gender(
                    league_name=m.get("league") or "", home_team=home_name, away_team=away_name,
                    venue=f"{home_name}主场"
                )
            except Exception:
                gender = "men"
        out.append({
            "id": m.get("id") or f"y-dqd-{len(out)}",
            "date": match_date,
            "time": match_time,
            "league": league,
            "region": region,
            "gender": gender,
            "homeTeam": home_name,
            "awayTeam": away_name,
            "venue": f"{home_name}主场",
            "stats": stats,
            "refereeAnalysis": referee_analysis,
            "keyEvents": key_events,
            "analysis": analysis,
            "_dataSource": m.get("dataSource", "dongqiudi-real"),
        })
    return out


def adapt_today(dqd_list, region):
    out = []
    for m in dqd_list:
        home_name = m["homeTeam"]["name"]
        away_name = m["awayTeam"]["name"]
        league = _build_league_obj(region, m.get("league", ""), m.get("leagueColor", "#666"),
                                    m.get("league") or "")
        try:
            parts = m.get("kickoff", "19:30:00").split(" ")[1].split(":")
            match_time = f"{parts[0]}:{parts[1]}"
            match_date = m.get("kickoff", "").split(" ")[0] or formatDate(getToday())
        except Exception:
            match_time = "19:30"; match_date = formatDate(getToday())
        referee_analysis = _adapt_referee_analysis(m.get("referee", {}))
        # features：dqd是字符串，data.py是数组，转成数组
        feat_str = m.get("features", "") or ""
        features = [x.strip() for x in feat_str.split("；") if x.strip()]
        if not features:
            features = ["常规联赛对决"]
        # 激烈程度 ★字符串 → predictedDifficulty 数字
        stars = (m.get("intensity") or "★").count("★")
        # 近期彩格：W/D/L 字符串 → 胜/平/负
        def form_cn(arr):
            return ["胜" if x == "W" else ("平" if x == "D" else "负") for x in (arr or [])]
        home_form = form_cn(m.get("homeRecent5") or ["平"] * 5)
        away_form = form_cn(m.get("awayRecent5") or ["平"] * 5)
        h2h = m.get("h2h") or []
        hw = sum(1 for g in h2h if int(g.get("homeScore", 0)) > int(g.get("awayScore", 0)))
        dr = sum(1 for g in h2h if int(g.get("homeScore", 0)) == int(g.get("awayScore", 0)))
        aw = sum(1 for g in h2h if int(g.get("homeScore", 0)) < int(g.get("awayScore", 0)))
        # gender：同上
        gender = m.get("gender")
        if gender not in ("men", "women"):
            try:
                from crawl_dongqiudi import detect_match_gender
                gender, _kw, _hs = detect_match_gender(
                    league_name=m.get("league") or "", home_team=home_name, away_team=away_name,
                    venue=f"{home_name}主场"
                )
            except Exception:
                gender = "men"
        out.append({
            "id": m.get("id") or f"t-dqd-{len(out)}",
            "date": match_date,
            "time": match_time,
            "league": league,
            "region": region,
            "gender": gender,
            "homeTeam": home_name,
            "awayTeam": away_name,
            "venue": f"{home_name}主场",
            "refereeAnalysis": referee_analysis,
            "features": features,
            "predictedDifficulty": max(1, min(5, int(stars))),
            "homeRecentForm": home_form,
            "awayRecentForm": away_form,
            "h2hLast5": {"homeWins": hw, "draws": dr, "awayWins": aw},
            "_dataSource": m.get("dataSource", "dongqiudi-real"),
        })
    return out


def split_by_gender(yesterday_matches, today_previews):
    """把全量 matches 按 gender 拆成 men/women 两份，返回 dict {men:(y,t), women:(y,t)}
    统一使用 crawl_dongqiudi.filter_by_gender（Single Source of Truth）保证和crawler一致的判定口径。"""
    try:
        from crawl_dongqiudi import filter_by_gender
    except Exception:
        # 极端情况filter_by_gender不可用 → 基于已打标的 gender 字段兜底（adapt_*已经打标）
        def filter_by_gender(lst, g):
            return [m for m in lst if m.get("gender", "men") == g]
    men_y = filter_by_gender(yesterday_matches, "men")
    men_t = filter_by_gender(today_previews, "men")
    women_y = filter_by_gender(yesterday_matches, "women")
    women_t = filter_by_gender(today_previews, "women")
    return {"men": (men_y, men_t), "women": (women_y, women_t)}


def build_from_dongqiudi():
    """优先用懂球帝真实数据。空或失败返回 (None, None)"""
    try:
        import crawl_dongqiudi as dqd
        data = dqd.fetch_dashboard_data()
    except Exception as e:
        print(f"  ⚠️ 懂球帝抓取失败：{e}，回退到Mock数据")
        return None, None
    yesterday_list = []
    today_list = []
    for region in ("europe", "asia", "australia"):
        yesterday_list.extend(adapt_yesterday(data.get("yesterday", {}).get(region, []), region))
        today_list.extend(adapt_today(data.get("today", {}).get(region, []), region))
    if not yesterday_list and not today_list:
        print(f"  ⚠️ 懂球帝返回空数据，回退到Mock数据")
        return None, None
    print(f"  ✅ 懂球帝真实数据加载：昨日 {len(yesterday_list)} 场 / 今日 {len(today_list)} 场预告")
    return yesterday_list, today_list


def main():
    print(f"\n🚀 Vercel 构建：正在生成静态数据（日期：{formatDate(getToday())}）...\n")
    random.seed()
    timestamp = datetime.now().isoformat()

    # 1. 尝试懂球帝，失败回退Mock
    yesterday_matches, today_previews = build_from_dongqiudi()
    used_dqd = yesterday_matches is not None or today_previews is not None
    if yesterday_matches is None:
        yesterday_matches = generateYesterdayMatches()
    if today_previews is None:
        today_previews = generateTodayPreviews()

    # 2. 按性别拆分（Single Source of Truth → crawl_dongqiudi.filter_by_gender）
    splits = split_by_gender(yesterday_matches, today_previews)
    men_y, men_t = splits["men"]
    women_y, women_t = splits["women"]

    # 3. 推送摘要：男足版本（首页默认）+ 女足版本（women.html）
    men_push_digest = generatePushDigest(men_y, men_t)
    if used_dqd:
        men_push_digest["title"] = (men_push_digest.get("title", "") or "") + "（懂球帝真实数据 · 男足）"
        men_push_digest["_dataSource"] = "dongqiudi-real"
        men_push_digest["_gender"] = "men"
    women_push_digest = generatePushDigest(women_y, women_t)
    if used_dqd:
        women_push_digest["title"] = (women_push_digest.get("title", "") or "") + "（懂球帝真实数据 · 女足）"
        women_push_digest["_dataSource"] = "dongqiudi-real"
        women_push_digest["_gender"] = "women"

    # 4. 加载历史推送（30天滚动，优先级：GitHub Actions从已发布Pages下载 → 本地cache.json → 空）
    #    GitHub Actions环境会设置 OLD_PUSH_HISTORY_URL / OLD_PUSH_HISTORY_WOMEN_URL 指向当前Pages的 push-history*.json，
    #    这样即使每天是clean runner（无本地cache），历史也能跨run累计（满足用户30天历史要求）
    cache_file = os.path.join(BASE_DIR, "cache.json")
    push_history = []
    push_history_women = []

    def _dl_json(url):
        if not url:
            return None
        try:
            import urllib.request as _ur
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            req = _ur.Request(url, headers={"User-Agent": "football-dashboard-ci/1.0"})
            with _ur.urlopen(req, timeout=15, context=ctx) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and isinstance(data.get("history"), list):
                    return data["history"]
                return None
        except Exception as e:
            print(f"  ⚠️ 下载旧推送历史失败（{url[:80]}…）：{e}，将从空开始")
            return None

    # 4.1 先尝试 Pages 在线历史（跨 GitHub Actions run 持久化 30 天）
    old_hist_men = _dl_json(os.environ.get("OLD_PUSH_HISTORY_URL", "").strip() or None)
    old_hist_women = _dl_json(os.environ.get("OLD_PUSH_HISTORY_WOMEN_URL", "").strip() or None)
    if isinstance(old_hist_men, list) and old_hist_men:
        push_history = old_hist_men
        print(f"  ✅ 从 Pages 恢复男足推送历史：{len(push_history)} 条")
    if isinstance(old_hist_women, list) and old_hist_women:
        push_history_women = old_hist_women
        print(f"  ✅ 从 Pages 恢复女足推送历史：{len(push_history_women)} 条")

    # 4.2 再用本地 cache.json 补兜底（本地手动构建场景）
    if not push_history or not push_history_women:
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    old_cache = json.load(f)
                if not push_history:
                    push_history = old_cache.get("pushHistory") or []
                if not push_history_women:
                    push_history_women = old_cache.get("pushHistoryWomen") or []
            except Exception:
                pass

    # 去重（按timestamp避免同一天重复构建导致重复条目）
    def _dedup(arr):
        seen_ts = set()
        out = []
        for item in arr:
            ts = item.get("timestamp") if isinstance(item, dict) else None
            if not ts or ts in seen_ts:
                continue
            seen_ts.add(ts)
            out.append(item)
        return out
    push_history = _dedup(push_history)
    push_history_women = _dedup(push_history_women)

    # 插入本次最新一条（最旧的超过30天会被截断）
    push_history.insert(0, {"timestamp": timestamp, "manual": False, "digest": men_push_digest})
    push_history = push_history[:30]
    push_history_women.insert(0, {"timestamp": timestamp, "manual": False, "digest": women_push_digest})
    push_history_women = push_history_women[:30]

    # 回写cache.json（server.py会用，保证server和静态构建的推送历史一致）
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f) if os.path.exists(cache_file) else {}
    except Exception:
        cache = {}
    cache.setdefault("pushHistory", [])
    cache.setdefault("pushHistoryWomen", [])
    cache["pushHistory"] = push_history
    cache["pushHistoryWomen"] = push_history_women
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    data_source_label = "dongqiudi-real" if used_dqd else "mock-generated"

    def save_dashboard(relpath, ym, tp, push_digest, leagues=None):
        if leagues is None:
            leagues = LEAGUES
        save_json(relpath, {
            "lastUpdate": timestamp,
            "generatedAt": datetime.now().isoformat(),
            "dataSource": data_source_label,
            "leagues": leagues,
            "yesterdayMatches": ym,
            "todayPreviews": tp,
            "pushDigest": push_digest,
        })

    # 5. 主页面：dashboard.json（默认男足）+ dashboard-women.json（女足）
    save_dashboard("dashboard.json", men_y, men_t, men_push_digest)
    save_dashboard("dashboard-women.json", women_y, women_t, women_push_digest)

    # 6. health.json
    save_json("health.json", {
        "status": "ok",
        "deployedAt": timestamp,
        "lastUpdate": timestamp,
        "hasData": len(men_y) + len(women_y) > 0,
        "dataSource": data_source_label,
        "counts": {
            "men": {"yesterday": len(men_y), "today": len(men_t)},
            "women": {"yesterday": len(women_y), "today": len(women_t)},
        },
        "note": "懂球帝真实数据优先，Mock兜底；默认首页 = 男足，女足版在 /women.html 或 data/dashboard-women.json；每天 9:00(Asia/Shanghai) 通过 Deploy Hook 自动重建",
    })

    # 7. push-latest*.json / push-history*.json（首页默认男足，女足单独存）
    save_json("push-latest.json", {
        "lastUpdate": timestamp,
        "latest": men_push_digest,
        "history": push_history[:5],
        "gender": "men",
    })
    save_json("push-history.json", {"history": push_history, "gender": "men"})
    save_json("push-latest-women.json", {
        "lastUpdate": timestamp,
        "latest": women_push_digest,
        "history": push_history_women[:5],
        "gender": "women",
    })
    save_json("push-history-women.json", {"history": push_history_women, "gender": "women"})

    # 8. 分区域dashboard（men是原dashboard-{region}.json；women后缀带-women）
    for region in ["europe", "asia", "australia"]:
        # 男足版（默认）
        ym_men_r = [m for m in men_y if m.get("region") == region]
        tp_men_r = [m for m in men_t if m.get("region") == region]
        save_dashboard(f"dashboard-{region}.json", ym_men_r, tp_men_r, men_push_digest,
                       leagues={region: LEAGUES.get(region, {})})
        # 女足版
        ym_women_r = [m for m in women_y if m.get("region") == region]
        tp_women_r = [m for m in women_t if m.get("region") == region]
        save_dashboard(f"dashboard-{region}-women.json", ym_women_r, tp_women_r, women_push_digest,
                       leagues={region: LEAGUES.get(region, {})})

    print(f"\n🎉 构建完成：男足 默认昨日 {len(men_y)} 场 / 今日 {len(men_t)} 场预告")
    print(f"           女足 独立页 昨日 {len(women_y)} 场 / 今日 {len(women_t)} 场预告  "
          f"[数据源：{'懂球帝真实' if used_dqd else 'Mock'}]")

    # ========== 构建产物 sanity check（Vercel build log 里能直接看到，避免"public目录被清空"导致白屏）==========
    import os as _os
    import stat as _stat
    PUBLIC_DIR = _os.path.join(BASE_DIR, "public")
    print(f"\n📁 构建输出目录 sanity check（public = {PUBLIC_DIR}）：")
    html_files = [
        ("index.html  (首页 · 男足)",  _os.path.join(PUBLIC_DIR, "index.html")),
        ("women.html  (独立页 · 女足)", _os.path.join(PUBLIC_DIR, "women.html")),
        ("data/health.json",           _os.path.join(PUBLIC_DIR, "data", "health.json")),
        ("data/dashboard.json (默认男足)",          _os.path.join(PUBLIC_DIR, "data", "dashboard.json")),
        ("data/dashboard-women.json (女足)",        _os.path.join(PUBLIC_DIR, "data", "dashboard-women.json")),
    ]
    all_ok = True
    for label, fpath in html_files:
        try:
            st = _os.stat(fpath)
            kind = "DIR" if _stat.S_ISDIR(st.st_mode) else "FILE"
            size_kb = st.st_size / 1024.0
            print(f"  ✅ [{kind:>4}] {size_kb:>7.1f} KB  {label}")
        except FileNotFoundError:
            print(f"  ❌ [MISS]  {label}  -> 路径不存在：{fpath}")
            all_ok = False
        except Exception as e:
            print(f"  ❌ [ERR ]  {label}  -> 检查失败：{e}")
            all_ok = False
    # 额外：列出data目录下所有json文件
    data_dir = _os.path.join(PUBLIC_DIR, "data")
    if _os.path.isdir(data_dir):
        jsons = sorted([fn for fn in _os.listdir(data_dir) if fn.endswith(".json")])
        print(f"\n📊 data/ 目录共 {len(jsons)} 个 JSON 文件：")
        for fn in jsons:
            sz = _os.path.getsize(_os.path.join(data_dir, fn)) / 1024.0
            print(f"   · {fn:32s}  {sz:>7.1f} KB")
    if not all_ok:
        print("\n❌ 构建产物检查失败：部分关键文件缺失！请检查 Vercel 的 buildCommand 执行日志")
        # 不退出，避免 CI 构建被标记失败，但问题会打印在log里方便排查
    print("--- 构建结束 ---")



if __name__ == "__main__":
    main()
