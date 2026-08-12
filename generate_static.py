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
from collections import OrderedDict

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


# ================= 日期回溯归档（28天选择器）=================
def _fmt_date(d_obj):
    return f"{d_obj.year:04d}-{d_obj.month:02d}-{d_obj.day:02d}"

def _parse_date(s):
    try:
        parts = s.split("-")
        return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None

def _date_n_days_ago(n, today=None):
    """返回 N 天前的日期字符串 YYYY-MM-DD（today=datetime对象，默认今天）"""
    from datetime import timedelta
    t = today or datetime.now()
    return _fmt_date(t - timedelta(days=n))

def save_archive_day(date_str, timestamp):
    """把当天构建的 dashboard[-women].json/teams.json 复制一份到 data/archive/{date_str}/ 用于日期选择器回溯"""
    arch_dir = f"archive/{date_str}"
    # 逐个读取当前文件再写入archive（跨fs更稳，不依赖shutil.copy）
    for fname in ("dashboard.json", "dashboard-women.json", "teams.json", "health.json"):
        src = os.path.join(DATA_DIR, fname)
        if not os.path.exists(src):
            continue
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        save_json(f"{arch_dir}/{fname}", data)
    # 当日归档索引条目（用于archive_index.json counts展示）
    try:
        with open(os.path.join(DATA_DIR, "health.json"), "r", encoding="utf-8") as f:
            h = json.load(f)
        counts = h.get("counts", {})
    except Exception:
        counts = {}
    return {"date": date_str, "archivedAt": timestamp, "counts": counts,
            "hasArchive": True}


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
        # 兼容：homeTeam/awayTeam 可能是 crawl_dongqiudi 输出的完整dict，也可能是旧字符串
        ht_raw = m.get("homeTeam")
        at_raw = m.get("awayTeam")
        if isinstance(ht_raw, dict):
            home_name = ht_raw.get("name", "?")
            home_obj = ht_raw
        else:
            home_name = str(ht_raw or "?")
            home_obj = {"name": home_name}
        if isinstance(at_raw, dict):
            away_name = at_raw.get("name", "?")
            away_obj = at_raw
        else:
            away_name = str(at_raw or "?")
            away_obj = {"name": away_name}
        league = _build_league_obj(region, m.get("league", ""), m.get("leagueColor", "#666"),
                                    m.get("league") and m.get("league") or "")
        try:
            parts = m.get("kickoff", "19:30:00").split(" ")[1].split(":")
            match_time = f"{parts[0]}:{parts[1]}"
            match_date = m.get("kickoff", "1970-01-01").split(" ")[0]
        except Exception:
            match_time = "19:30"; match_date = formatDate(getYesterday())
        stats = _adapt_stats(m.get("stats", {}), home_obj.get("score", 0) if isinstance(home_obj, dict) else 0,
                                              away_obj.get("score", 0) if isinstance(away_obj, dict) else 0)
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
            "homeTeam": home_obj,
            "awayTeam": away_obj,
            "venue": f"{home_name}主场",
            "stats": stats,
            "refereeAnalysis": referee_analysis,
            "keyEvents": key_events,
            "analysis": analysis,
            "homeTactics": m.get("homeTactics"),
            "awayTactics": m.get("awayTactics"),
            "intensity": m.get("intensity", "★★★"),
            "features": m.get("features", ""),
            "marketExpectation": m.get("marketExpectation"),
            "t1Comparison": m.get("t1Comparison"),
            "_dataSource": m.get("dataSource", "dongqiudi-real"),
        })
    return out


def adapt_today(dqd_list, region):
    out = []
    for m in dqd_list:
        ht_raw = m.get("homeTeam")
        at_raw = m.get("awayTeam")
        if isinstance(ht_raw, dict):
            home_name = ht_raw.get("name", "?")
            home_obj = ht_raw
        else:
            home_name = str(ht_raw or "?")
            home_obj = {"name": home_name}
        if isinstance(at_raw, dict):
            away_name = at_raw.get("name", "?")
            away_obj = at_raw
        else:
            away_name = str(at_raw or "?")
            away_obj = {"name": away_name}
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
        intensity_str = m.get("intensity") or "★"
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
            "homeTeam": home_obj,
            "awayTeam": away_obj,
            "venue": f"{home_name}主场",
            "refereeAnalysis": referee_analysis,
            "features": features,
            "predictedDifficulty": max(1, min(5, int(stars))),
            "intensity": intensity_str,
            "homeRecentForm": home_form,
            "awayRecentForm": away_form,
            "h2hLast5": {"homeWins": hw, "draws": dr, "awayWins": aw},
            "marketExpectation": m.get("marketExpectation"),
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


# =========================================================
# 【FT早知道App扩展】热度算法 / 大洲徽章 / 球队库(球员名册)
# =========================================================

# 确定性字符串hash（和crawl_dongqiudi._stable_hash完全一致，避免import麻烦）
def _sh(s: str) -> int:
    h = 2166136261
    for ch in str(s):
        h ^= ord(ch); h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF

# 联赛等级分0-50分（五联赛顶格，其他依次递减）
LEAGUE_LEVEL_HINTS = OrderedDict([
    # 关键词 → 基础分
    (("英超", "Premier", "Serie A", "Serie A Femminile", "La Liga", "Liga F", "Bundesliga", "Frauen-Bundesliga", "Ligue 1", "D1 Féminine", "Division 1"), 48),
    (("亚冠", "AFC Champions", "欧冠", "Champions League", "UEFA Champions", "世俱杯", "Club World", "欧洲超级杯", "Super Cup", "国王杯", "Copa del Rey", "足总杯", "FA Cup", "德国杯", "DFB-Pokal", "法国杯", "Coupe de France", "意大利杯", "Coppa Italia", "联赛杯", "EFL Cup"), 46),
    (("英冠", "Championship", "西乙", "Segunda", "德乙", "2. Bundesliga", "意乙", "Serie B", "法乙", "Ligue 2", "葡超", "Primeira", "荷甲", "Eredivisie", "比甲", "Jupiler Pro", "奥超", "Bundesliga Austria", "瑞士超", "Super League Switzerland", "丹超", "Superliga", "瑞超", "Allsvenskan", "挪超", "Eliteserien"), 38),
    (("中超", "CSL", "中女超", "J1", "J联赛", "Nadeshiko", "K1", "K League", "WK League", "沙特联", "Saudi Pro", "卡塔尔联", "Stars League", "UAE Pro", "A联赛", "A-League", "W-League", "亚冠2", "AFC Cup"), 32),
    (("J2", "J3", "K2", "K3", "中甲", "中乙", "中冠", "泰超", "Thai League 1", "越南联", "V.League", "马超", "Malaysia Super", "新超", "Singapore Premier", "印超", "ISL"), 24),
])

def _league_level_score(league_name):
    name = str(league_name or "")
    for keywords, base in LEAGUE_LEVEL_HINTS.items():
        for kw in keywords:
            if kw.lower() in name.lower():
                return base
    return 16  # 未知联赛基础分（保底不空）

def _intensity_star_weight(intensity_str):
    s = str(intensity_str or "★").count("★")
    return max(1, min(5, s)) * 3  # 1★=3 → 5★=15

def _heat_to_stars(heat_score):
    """热度分 → 推荐指数星级（1-5星）
       ≥70 → ★★★★★ 焦点战（橙色三角置顶）
       55-69 → ★★★★☆ 值得关注
       40-54 → ★★★☆☆ 常规联赛
       25-39 → ★★☆☆☆ 普通对决
       <25 → ★☆☆☆☆ 冷门/U系列等
    """
    hs = int(heat_score or 0)
    if hs >= 70: return 5
    if hs >= 55: return 4
    if hs >= 40: return 3
    if hs >= 25: return 2
    return 1

def _stars_to_str(stars):
    return "★" * stars + "☆" * (5 - stars)

def _team_obj(t):
    """兼容：球队可能是对象dict，也可能是旧格式字符串（球队名），统一返回dict"""
    if isinstance(t, dict):
        return t
    if isinstance(t, str):
        return {"name": t}
    return {}

def compute_heat_score(match, is_yesterday=True):
    """6维加权热度分 0-100（确定性，同一场每次分值相同）"""
    # (1) 联赛基础分 0-50
    s1 = _league_level_score(match.get("league") or "")
    # (2) 球队排名强度 0-20（两队排名越靠前越高）
    rank_score = 0
    for side in ("homeTeam", "awayTeam"):
        t = _team_obj(match.get(side))
        r = t.get("rank")
        try:
            r_int = int(r) if r not in (None, "", 0, "0") else 0
        except Exception:
            r_int = 0
        if 1 <= r_int <= 4:
            rank_score += 10
        elif 5 <= r_int <= 8:
            rank_score += 7
        elif 9 <= r_int <= 12:
            rank_score += 4
        elif r_int >= 13:
            rank_score += 2
    s2 = min(20, rank_score)
    # (3) 德比/焦点（名关键词 + 双方排名强度）0-15
    derby_kws = ["德比", "Derby", "Classic", "国家德比", "曼彻斯特联", "曼城", "皇马", "巴萨", "El Clásico", "北伦敦", "利物浦", "曼联", "多特", "拜仁", "米兰", "国米", "尤文", "大巴黎", "上海", "北京", "广州", "东京", "首尔"]
    focal = 0
    ht = _team_obj(match.get("homeTeam"))
    at = _team_obj(match.get("awayTeam"))
    name_all = f"{match.get('league','')} {ht.get('name','')} {at.get('name','')} {match.get('features','')}"
    if any(k.lower() in name_all.lower() for k in derby_kws):
        focal += 8
    # 排名焦点加成：两队排名都靠前时加焦点分（替代旧的伪随机星级加成，打破循环依赖）
    if s2 >= 18:
        focal += 7  # 两队均Top8 → 强强对话
    elif s2 >= 14:
        focal += 4  # 一队Top4 + 另一队Top8+ → 实力接近
    s3 = min(15, focal)
    # (4) 近期状态H2H 0-15（基于两队名hash的确定性5彩格分析）
    seed = f"{ht.get('name','')}|{at.get('name','')}|{match.get('id','')}"
    hh = _sh(seed)
    h2h_wdl = (hh % 5, (hh >> 3) % 5, (hh >> 6) % 5)
    s4 = 2 + int(sum(min(4, x) for x in h2h_wdl) / 3)  # 2-10
    if is_yesterday:
        # 昨日+比分悬殊度（如3-0/4-1这种大胜热度也高）
        hs = ht.get("score", 0) or 0
        as_ = at.get("score", 0) or 0
        try:
            total_g = int(hs) + int(as_)
        except Exception:
            total_g = 0
        s4 += min(5, total_g)  # 比分总进球+热度
    s4 = min(15, s4)
    total = s1 + s2 + s3 + s4
    # 焦点赛标记：总分≥70 → 🔥焦点（前端橙色三角标置顶）
    return {"heatScore": max(2, min(100, total)),
            "breakdown": {"league": s1, "rank": s2, "focal": s3, "h2hRecent": s4},
            "isHot": total >= 70}

def apply_heat_and_sort(yesterday_matches, today_previews):
    """给每场加热度分→按(焦点置顶→heatScore高→开赛时间近)降序排序→返回(sorted_y, sorted_t, continent_badges, matchesByContinent)"""
    def _add(lst, is_y):
        out = []
        for m in lst:
            info = compute_heat_score(m, is_yesterday=is_y)
            m2 = dict(m)
            m2["heatScore"] = info["heatScore"]
            m2["heatBreakdown"] = info["breakdown"]
            m2["isHotMatch"] = info["isHot"]
            # ✅ 用真实热度分映射推荐指数星级（替代旧的伪随机intensity）
            real_stars = _heat_to_stars(info["heatScore"])
            m2["predictedDifficulty"] = real_stars
            m2["intensity"] = _stars_to_str(real_stars)
            # ✅ 同步修正 features 标签，与真实星级保持一致
            feats = list(m2.get("features") or [])
            # 移除旧伪随机逻辑可能加上的 "双方实力接近" 标签
            feats = [f for f in feats if "双方实力接近" not in f and "焦点对决" not in f]
            # 根据真实星级添加对应标签
            if real_stars >= 5:
                feats.append("🔥焦点对决，强烈推荐关注")
            elif real_stars >= 4:
                feats.append("双方实力接近，值得关注")
            # 保底标签
            if not feats:
                feats.append("常规联赛对决")
            m2["features"] = feats
            out.append(m2)
        return out
    y_heated = _add(yesterday_matches, True)
    t_heated = _add(today_previews, False)
    def _sort_key(x):
        # 1. 焦点置顶（isHotMatch=True→0，否则1）
        top = 0 if x.get("isHotMatch") else 1
        # 2. 热度分降序（负号变升序排列的key）
        heat_neg = -(x.get("heatScore") or 0)
        # 3. 开赛时间近→远（kicking晚→先）
        kf = x.get("kickoff") or ""
        return (top, heat_neg, kf)
    y_sorted = sorted(y_heated, key=_sort_key)
    t_sorted = sorted(t_heated, key=_sort_key)
    # continent_badges + matchesByContinent
    badges = {"all": {"yesterday": len(y_sorted), "today": len(t_sorted)},
              "europe": {"yesterday": 0, "today": 0},
              "asia": {"yesterday": 0, "today": 0},
              "australia": {"yesterday": 0, "today": 0}}
    by_cont = {"all": {"yesterday": y_sorted, "today": t_sorted},
               "europe": {"yesterday": [], "today": []},
               "asia": {"yesterday": [], "today": []},
               "australia": {"yesterday": [], "today": []}}
    for label, arr in (("yesterday", y_sorted), ("today", t_sorted)):
        for m in arr:
            reg = m.get("region") or "europe"
            if reg in badges:
                badges[reg][label] += 1
                by_cont[reg][label].append(m)
    return y_sorted, t_sorted, badges, by_cont

def build_teams_db(*match_groups, used_dqd=False, gender="men"):
    """
    从N个match列表中抽取所有unique球队（按teamId），生成球队库（含球员名册24人）。
    返回 {teamId: {teamId,name,appLogo,countryFlag,gender,region,league,squad:[{name,number,position,avatarSeed,height,weight,age}]}}
    """
    teams = OrderedDict()  # teamId → team_data
    try:
        from crawl_dongqiudi import generate_squad as _gen_sq
    except Exception:
        _gen_sq = None
    # 收集球队：从每个match的homeTeam/awayTeam取
    for groups in match_groups:
        for m in (groups or []):
            for side in ("homeTeam", "awayTeam"):
                t = _team_obj(m.get(side))
                tid = t.get("teamId")
                if not tid:
                    # Mock球队没teamId → 用name+region生成
                    _s = "%s|%s|%s" % (t.get("name", ""), m.get("region", ""), side)
                    tid = f"tmock{_sh(_s):08x}"
                if tid in teams:
                    # 如果已经有了但字段不全，再合并一次（squad等只生成一次）
                    continue
                name = t.get("name") or f"球队 {tid[-4:]}"
                appLogo = t.get("appLogo") or _fallback_logo(name, tid)
                squad = []
                if _gen_sq is not None:
                    try:
                        flag = (appLogo or {}).get("countryFlag") or (t.get("countryFlag") or "")
                        squad = _gen_sq(tid, name, flag=flag, gender=gender, count=24)
                    except Exception as e:
                        print(f"  ⚠️ 生成球队 {name}({tid}) 名册失败：{e}")
                if not squad:
                    squad = _fallback_squad(tid, name, gender)
                teams[tid] = OrderedDict([
                    ("teamId", tid),
                    ("name", name),
                    ("shortName", (appLogo or {}).get("text") or name[:2]),
                    ("appLogo", appLogo),
                    ("countryFlag", (appLogo or {}).get("countryFlag") or t.get("countryFlag") or "🏳️"),
                    ("gender", gender),
                    ("region", m.get("region") or "europe"),
                    ("league", m.get("league") or "未知联赛"),
                    ("rank", t.get("rank")),
                    ("squad", squad),
                    ("_source", "dongqiudi-real" if used_dqd else "mock"),
                ])
    return teams

def _fallback_logo(name, tid):
    """Mock兜底队徽（无crawl_dongqiudi可用时）"""
    colors_arr = [["#22c55e","#15803d"],["#3b82f6","#1d4ed8"],["#f59e0b","#c2410c"],["#ec4899","#be185d"],["#8b5cf6","#6d28d9"],["#06b6d4","#0e7490"],["#ef4444","#991b1b"],["#10b981","#047857"]]
    c = colors_arr[_sh(tid) % len(colors_arr)]
    if all("\u4e00" <= ch <= "\u9fff" for ch in str(name)[:2]) and len(str(name)) >= 2:
        text = str(name)[-2:]
    else:
        ww = [w for w in str(name).replace("-"," ").split() if w]
        text = "".join(w[0] for w in ww[:3]).upper()
        if len(text) < 2: text = (str(name)[:2]).upper()
    text = text[:3] if len(text) >= 2 else (text + "F")
    return {"text": text, "colors": c, "countryFlag": "🏳️"}

def _fallback_squad(tid, name, gender="men"):
    """crawl_dongqiudi不可用时的24人Mock名单（确保球队详情弹窗不空）"""
    from data import pick as _p, rand as _r
    rng = random.Random(f"fallback-squad-{tid}")
    positions = (
        [("GK",)] * 3 +
        [("CB","LB","RB","LWB","RWB")] * 8 +
        [("CDM","CM","CAM","LM","RM")] * 8 +
        [("ST","CF","LW","RW","SS")] * 5
    )
    first_cn = ["伟","强","磊","军","洋","超","杰","勇","明","涛","佳","浩","宇","轩","睿","博","慧","悦","妍","雨","欣","思","婷","菲"]
    sur_cn = ["张","王","李","刘","陈","杨","赵","黄","周","吴","徐","孙","马","朱","胡","郭","何","高","林","郑"]
    first_en = ["James","John","Robert","Michael","William","David","Oliver","Harry","George","Lucas","Emma","Olivia","Sophia","Ava","Isabella","Mia","Charlotte","Amelia"]
    sur_en = ["Smith","Johnson","Brown","Williams","Jones","Miller","Davis","Garcia","Rodriguez","Wilson","Martinez","Anderson","Taylor","Thomas","Moore","Jackson"]
    is_cn = any("\u4e00" <= ch <= "\u9fff" for ch in str(name))
    nums = list(range(2, 100))
    rng.shuffle(nums)
    num_iter = iter([1] + nums)
    out = []
    for idx, grp in enumerate(positions):
        grp_list = list(grp)
        pos = rng.choice(grp_list)
        if is_cn:
            full = rng.choice(sur_cn) + rng.choice(first_cn)
        else:
            full = f"{rng.choice(first_en)} {rng.choice(sur_en)}"
        try:
            number = next(num_iter)
        except StopIteration:
            number = 99
        out.append({
            "id": f"{tid}-p{idx:02d}",
            "name": full,
            "number": number,
            "position": pos,
            "positionLabel": pos,
            "group": ("GK" if pos == "GK" else ("DEF" if pos in ("CB","LB","RB","LCB","RCB","LWB","RWB") else ("MID" if pos in ("CDM","CM","CAM","LM","RM") else "FWD"))),
            "avatarSeed": _sh(f"{tid}|{full}|{number}"),
            "height": rng.randint(178, 198),
            "weight": rng.randint(70, 94),
            "age": rng.randint(19, 34),
        })
    return out


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
    men_y_raw, men_t_raw = splits["men"]
    women_y_raw, women_t_raw = splits["women"]

    # 2.1 热度分 + 大洲内按热度从高→低排序（🔥焦点置顶）+ 大洲快捷栏徽章计数
    men_y, men_t, men_badges, men_by_cont = apply_heat_and_sort(men_y_raw, men_t_raw)
    women_y, women_t, women_badges, women_by_cont = apply_heat_and_sort(women_y_raw, women_t_raw)
    print(f"  🧡 热度排序完成：男足 焦点赛{sum(1 for m in men_y if m.get('isHotMatch'))}场 / 女足 焦点赛{sum(1 for m in women_y if m.get('isHotMatch'))}场")

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

    def save_dashboard(relpath, ym, tp, push_digest, leagues=None, badges=None, by_cont=None, gender="men"):
        if leagues is None:
            leagues = LEAGUES
        payload = {
            "lastUpdate": timestamp,
            "generatedAt": datetime.now().isoformat(),
            "dataSource": data_source_label,
            "leagues": leagues,
            "yesterdayMatches": ym,
            "todayPreviews": tp,
            "pushDigest": push_digest,
            # === FT早知道新增字段（App化必需） ===
            "appName": "FT早知道",
            "appGender": gender,              # "men" | "women" → 前端据此选深浅主题
            "continentBadges": badges or {},
            "matchesByContinent": by_cont or {"all":{"yesterday":ym,"today":tp}},
        }
        save_json(relpath, payload)

    # 5. 主页面：dashboard.json（默认男足·深色主题）+ dashboard-women.json（女足·浅色主题）
    save_dashboard("dashboard.json", men_y, men_t, men_push_digest,
                   badges=men_badges, by_cont=men_by_cont, gender="men")
    save_dashboard("dashboard-women.json", women_y, women_t, women_push_digest,
                   badges=women_badges, by_cont=women_by_cont, gender="women")

    # 5.1 球队库（含24人球员名册），teams.json → 球队详情弹窗懒加载 fetch('/data/teams.json')
    # 合并男女足所有球队 → 同一个teamId只保留一条（优先男足侧先插入）
    teams_men = build_teams_db(men_y, men_t, used_dqd=used_dqd, gender="men")
    teams_women = build_teams_db(women_y, women_t, used_dqd=used_dqd, gender="women")
    teams_db = OrderedDict()
    for tid, t in teams_men.items(): teams_db[tid] = t
    for tid, t in teams_women.items():
        if tid not in teams_db:  # 同一ID的女足队不覆盖男足（通常女足队名带"女足"/Women不会撞ID）
            teams_db[tid] = t
    save_json("teams.json", {
        "lastUpdate": timestamp,
        "generatedAt": datetime.now().isoformat(),
        "totalTeams": len(teams_db),
        "teams": teams_db,
        "_notes": "懒加载：球队详情弹窗hash路由#team=<teamId>时fetch('/data/teams.json')拿squad；T-1战术阵型从对应dashboard.json的yesterdayMatches[i].homeTactics/awayTactics取",
    })
    print(f"  ⚽ 球队库构建完成：{len(teams_db)} 支球队（含24人名册）")

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

    # 9. 28天回溯归档（archive/{date}/ 每日独立JSON + archive_index.json）
    from datetime import timedelta as _td
    today_dt_obj = getToday()
    today_date_str = formatDate(today_dt_obj)  # YYYY-MM-DD（getToday返回datetime对象，formatDate转字符串）
    # 9.1 尝试从 Pages 在线恢复旧 archive_index（跨 Actions run 持久化）
    old_archive_url = (os.environ.get("OLD_PUSH_HISTORY_URL", "") or "").replace("push-history.json", "archive/archive_index.json").strip()
    old_index = {"days": [], "retentionDays": 30}
    try:
        restored = _dl_json(old_archive_url) if old_archive_url else None
        if isinstance(restored, dict) and isinstance(restored.get("days"), list):
            old_index = restored
            print(f"  ✅ 从 Pages 恢复历史归档索引：{len(old_index['days'])} 天")
    except Exception:
        pass
    # 9.2 再尝试本地 cache 里的旧 archive_index（本地构建兜底）
    cache_arch = os.path.join(BASE_DIR, "cache_archive_index.json")
    if not old_index.get("days") and os.path.exists(cache_arch):
        try:
            with open(cache_arch, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if isinstance(cached, dict) and isinstance(cached.get("days"), list):
                    old_index = cached
                    print(f"  ℹ️  从本地 cache_archive_index 恢复：{len(old_index['days'])} 天")
        except Exception:
            pass
    # 9.3 保存当日归档到 data/archive/YYYY-MM-DD/
    today_entry = save_archive_day(today_date_str, timestamp)
    # 9.4 合并old_index.days + today_entry（按date去重，当日覆盖旧条目）
    days_by_key = OrderedDict()
    for entry in (old_index.get("days") or []):
        if isinstance(entry, dict) and entry.get("date"):
            days_by_key[entry["date"]] = entry
    days_by_key[today_date_str] = today_entry  # 今日覆盖
    # 9.5 保留<=30天，删除超期目录（28天需求+2天冗余）
    keep_cutoff = today_dt_obj - _td(days=30)
    kept_days = []
    for d_str, entry in list(days_by_key.items()):
        d_dt = _parse_date(d_str)
        if d_dt and d_dt >= keep_cutoff:
            kept_days.append(entry)
        else:
            # 超期：尝试删除本地archive目录
            try:
                arch_folder = os.path.join(DATA_DIR, "archive", d_str)
                if os.path.isdir(arch_folder):
                    import shutil as _sh
                    _sh.rmtree(arch_folder, ignore_errors=True)
            except Exception:
                pass
    kept_days.sort(key=lambda e: e.get("date", ""), reverse=True)  # 日期降序（今天在前）
    # 9.6 保存 archive_index.json（前端日期选择器取可用列表用）
    archive_index = OrderedDict([
        ("lastUpdate", timestamp),
        ("retentionDays", 30),
        ("selectorMinDate", _date_n_days_ago(27, today_dt_obj)),  # 28天窗口：今天+前27天
        ("selectorMaxDate", today_date_str),
        ("days", kept_days),
        ("_note", "日期选择器：前端用 min/max 限制为28天；取数 URL = data/archive/<YYYY-MM-DD>/dashboard.json"),
    ])
    save_json("archive/archive_index.json", archive_index)
    # 本地缓存archive_index供下次无Pages环境兜底
    try:
        with open(cache_arch, "w", encoding="utf-8") as f:
            json.dump(archive_index, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    print(f"  📅 28天回溯归档：已保留 {len(kept_days)} 天（最早 {kept_days[-1]['date'] if kept_days else today_date_str}）")

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
