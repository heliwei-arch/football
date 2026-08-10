"""数据层：球赛数据、裁判分析、模拟数据生成（Python版，与原data.js保持同构）"""
import json
import random
import os
from datetime import datetime, timedelta

# 区域联赛配置
LEAGUES = {
    "europe": [
        {"id": "epl", "name": "英超联赛", "country": "英格兰", "flag": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"},
        {"id": "laliga", "name": "西甲联赛", "country": "西班牙", "flag": "\U0001f1ea\U0001f1f8"},
        {"id": "bundesliga", "name": "德甲联赛", "country": "德国", "flag": "\U0001f1e9\U0001f1ea"},
        {"id": "seriea", "name": "意甲联赛", "country": "意大利", "flag": "\U0001f1ee\U0001f1f9"},
        {"id": "ligue1", "name": "法甲联赛", "country": "法国", "flag": "\U0001f1eb\U0001f1f7"},
        {"id": "ucl", "name": "欧冠联赛", "country": "欧洲", "flag": "\U0001f1ea\U0001f1fa"}
    ],
    "asia": [
        {"id": "csl", "name": "中超联赛", "country": "中国", "flag": "\U0001f1e8\U0001f1f3"},
        {"id": "jleague", "name": "J联赛", "country": "日本", "flag": "\U0001f1ef\U0001f1f5"},
        {"id": "kleague", "name": "K联赛", "country": "韩国", "flag": "\U0001f1f0\U0001f1f7"},
        {"id": "acl", "name": "亚冠联赛", "country": "亚洲", "flag": "\U0001f3c6"},
        {"id": "apl", "name": "沙特联赛", "country": "沙特阿拉伯", "flag": "\U0001f1f8\U0001f1e6"}
    ],
    "australia": [
        {"id": "aleague", "name": "澳超联赛", "country": "澳大利亚", "flag": "\U0001f1e6\U0001f1fa"},
        {"id": "nzfootball", "name": "新西兰超级联赛", "country": "新西兰", "flag": "\U0001f1f3\U0001f1ff"}
    ]
}

# 用简单的旗帜代替上面复杂的emoji，避免显示问题
LEAGUES["europe"][0]["flag"] = "\U0001f3f4"

TEAMS = {
    "epl": ["曼联", "曼城", "利物浦", "阿森纳", "切尔西", "热刺", "纽卡斯尔", "布莱顿", "阿斯顿维拉", "西汉姆", "布伦特福德", "埃弗顿"],
    "laliga": ["皇家马德里", "巴塞罗那", "马竞", "塞维利亚", "皇家社会", "比利亚雷亚尔", "毕尔巴鄂", "瓦伦西亚", "皇家贝蒂斯"],
    "bundesliga": ["拜仁慕尼黑", "多特蒙德", "RB莱比锡", "勒沃库森", "柏林联盟", "弗赖堡", "法兰克福", "沃尔夫斯堡"],
    "seriea": ["国际米兰", "AC米兰", "尤文图斯", "那不勒斯", "罗马", "拉齐奥", "亚特兰大", "佛罗伦萨"],
    "ligue1": ["巴黎圣日耳曼", "马赛", "摩纳哥", "里昂", "里尔", "尼斯", "雷恩"],
    "ucl": ["拜仁慕尼黑", "皇家马德里", "曼城", "巴黎圣日耳曼", "巴塞罗那", "国际米兰", "阿森纳", "多特蒙德"],
    "csl": ["上海海港", "山东泰山", "上海申花", "北京国安", "成都蓉城", "武汉三镇", "河南队", "浙江队"],
    "jleague": ["川崎前锋", "横滨水手", "鹿岛鹿角", "浦和红钻", "名古屋鲸八", "大阪樱花", "东京FC"],
    "kleague": ["全北现代", "蔚山现代", "浦项制铁", "首尔FC", "大邱FC", "仁川联"],
    "acl": ["上海海港", "川崎前锋", "全北现代", "蔚山现代", "横滨水手", "山东泰山"],
    "apl": ["利雅得新月", "吉达联合", "利雅得胜利", "吉达国民", "利雅得青年"],
    "aleague": ["悉尼FC", "墨尔本胜利", "西悉尼流浪者", "布里斯班狮吼", "珀斯光荣", "惠灵顿凤凰"],
    "nzfootball": ["奥克兰城", "惠灵顿奥林匹克", "坎特伯雷联", "奥克兰联"]
}

REFEREES = [
    {"id": "r001", "name": "安东尼·泰勒", "country": "英格兰", "age": 45},
    {"id": "r002", "name": "迈克尔·奥利弗", "country": "英格兰", "age": 39},
    {"id": "r003", "name": "安东尼奥·马特乌", "country": "西班牙", "age": 47},
    {"id": "r004", "name": "克莱芒·蒂尔潘", "country": "法国", "age": 41},
    {"id": "r005", "name": "丹妮埃莱·奥萨托", "country": "意大利", "age": 48},
    {"id": "r006", "name": "费利克斯·茨瓦耶", "country": "德国", "age": 42},
    {"id": "r007", "name": "丹尼·马克列", "country": "荷兰", "age": 40},
    {"id": "r008", "name": "阿图尔·迪亚斯", "country": "葡萄牙", "age": 44},
    {"id": "r009", "name": "傅明", "country": "中国", "age": 40},
    {"id": "r010", "name": "马宁", "country": "中国", "age": 45},
    {"id": "r011", "name": "佐藤隆治", "country": "日本", "age": 43},
    {"id": "r012", "name": "金希坤", "country": "韩国", "age": 42},
    {"id": "r013", "name": "克里斯·比斯", "country": "澳大利亚", "age": 41}
]


def rand(min_val, max_val):
    return random.randint(min_val, max_val)


def pick(arr):
    return random.choice(arr)


def pickN(arr, n):
    if n >= len(arr):
        return arr.copy()
    return random.sample(arr, n)


def getYesterday():
    return datetime.now() - timedelta(days=1)


def getToday():
    return datetime.now()


def formatDate(date):
    return date.strftime("%Y-%m-%d")


def generateRefereeHistory(referee, count=5):
    """生成裁判前5场历史记录"""
    history = []
    all_leagues = LEAGUES["europe"] + LEAGUES["asia"]
    for i in range(count):
        yellowCards = rand(2, 8)
        redCards = rand(0, 2)
        penalties = rand(0, 2)
        fouls = rand(15, 35)
        varChecks = rand(0, 5)
        cardIndex = yellowCards + redCards * 3
        d = getYesterday() - timedelta(days=i + 1)
        history.append({
            "matchNumber": count - i,
            "date": formatDate(d),
            "league": pick(all_leagues)["name"],
            "yellowCards": yellowCards,
            "redCards": redCards,
            "penalties": penalties,
            "fouls": fouls,
            "varChecks": varChecks,
            "cardIndex": cardIndex
        })
    return history


def analyzeRefereeStyle(referee, history):
    """分析裁判风格"""
    avgYellow = sum(h["yellowCards"] for h in history) / len(history)
    avgRed = sum(h["redCards"] for h in history) / len(history)
    avgFouls = sum(h["fouls"] for h in history) / len(history)
    avgPenalties = sum(h["penalties"] for h in history) / len(history)
    avgCardIndex = sum(h["cardIndex"] for h in history) / len(history)
    avgVar = sum(h["varChecks"] for h in history) / len(history)

    strictnessScore = 0
    if avgYellow >= 5: strictnessScore += 35
    elif avgYellow >= 4: strictnessScore += 25
    elif avgYellow >= 3: strictnessScore += 15
    else: strictnessScore += 5

    if avgRed >= 0.8: strictnessScore += 25
    elif avgRed >= 0.4: strictnessScore += 15
    elif avgRed >= 0.2: strictnessScore += 8
    else: strictnessScore += 2

    if avgFouls >= 28: strictnessScore += 20
    elif avgFouls >= 22: strictnessScore += 12
    elif avgFouls >= 18: strictnessScore += 6
    else: strictnessScore += 2

    if avgPenalties >= 0.8: strictnessScore += 20
    elif avgPenalties >= 0.4: strictnessScore += 12
    else: strictnessScore += 5

    if strictnessScore >= 75:
        style = "严格型"
        styleDesc = "该裁判倾向于严格执法，对犯规零容忍。比赛中频繁出示黄牌，红牌概率较高。球队需注意动作规范，避免过激对抗。"
        keyTraits = ["出牌频率高", "对恶意犯规零容忍", "点球判罚果断", "VAR介入频繁"]
    elif strictnessScore >= 55:
        style = "偏严格型"
        styleDesc = "该裁判执法相对严格，对明显犯规会及时出牌。在关键场次或强强对话中尺度可能收紧。"
        keyTraits = ["关键战出牌多", "对危险动作敏感", "偶有点球判罚", "中规中矩的执法"]
    elif strictnessScore >= 35:
        style = "平衡型"
        styleDesc = "该裁判执法尺度平衡，既保证比赛流畅性又不会纵容犯规。鼓励合理对抗，出牌较为克制。"
        keyTraits = ["鼓励对抗", "出牌谨慎", "比赛流畅度高", "点球判罚较少"]
    else:
        style = "鼓励对抗型"
        styleDesc = "该裁判倾向于让比赛流畅进行，对身体对抗容忍度高。出牌非常克制，比赛节奏快，对抗激烈。"
        keyTraits = ["极少出牌", "鼓励身体对抗", "比赛中断少", "极少判罚点球"]

    return {
        "referee": referee,
        "history": history,
        "statistics": {
            "avgYellow": f"{avgYellow:.1f}",
            "avgRed": f"{avgRed:.2f}",
            "avgFouls": f"{avgFouls:.1f}",
            "avgPenalties": f"{avgPenalties:.2f}",
            "avgCardIndex": f"{avgCardIndex:.1f}",
            "avgVar": f"{avgVar:.1f}",
            "strictnessScore": round(strictnessScore)
        },
        "style": style,
        "styleDesc": styleDesc,
        "keyTraits": keyTraits
    }


def generateMatchStats(homeTeam, awayTeam):
    """生成Opta/StatsBomb风格的比赛对比数据"""
    homeScore = rand(0, 4)
    awayScore = rand(0, 3)
    homePossession = rand(35, 68)
    return {
        "score": {"home": homeScore, "away": awayScore},
        "possession": {"home": homePossession, "away": 100 - homePossession},
        "shots": {"home": rand(6, 22), "away": rand(5, 18)},
        "shotsOnTarget": {"home": rand(2, 9), "away": rand(1, 7)},
        "xG": {
            "home": f"{rand(5, 30) / 10:.2f}",
            "away": f"{rand(4, 28) / 10:.2f}"
        },
        "passes": {"home": rand(280, 650), "away": rand(250, 580)},
        "passAccuracy": {
            "home": f"{rand(72, 90)}%",
            "away": f"{rand(70, 88)}%"
        },
        "tackles": {"home": rand(12, 28), "away": rand(10, 25)},
        "interceptions": {"home": rand(6, 20), "away": rand(5, 18)},
        "fouls": {"home": rand(8, 22), "away": rand(7, 20)},
        "corners": {"home": rand(2, 10), "away": rand(2, 9)},
        "yellowCards": {"home": rand(0, 4), "away": rand(0, 4)},
        "redCards": {"home": rand(0, 1), "away": rand(0, 1)},
        "offsides": {"home": rand(1, 6), "away": rand(0, 5)},
        "saves": {"home": rand(1, 6), "away": rand(1, 5)}
    }


def generateKeyEvents(homeTeam, awayTeam, stats):
    """生成关键事件时间线"""
    events = []
    minute = 1
    for i in range(stats["score"]["home"]):
        minute = rand(minute, min(90, minute + 20))
        events.append({
            "minute": minute,
            "type": "goal",
            "team": "home",
            "teamName": homeTeam,
            "description": f"{homeTeam} 进球！精彩射门得分"
        })
        minute = min(90, minute + 5)
    minute = 1
    for i in range(stats["score"]["away"]):
        minute = rand(minute, min(90, minute + 20))
        events.append({
            "minute": minute,
            "type": "goal",
            "team": "away",
            "teamName": awayTeam,
            "description": f"{awayTeam} 进球！扳平/反超比分"
        })
        minute = min(90, minute + 5)

    totalYellow = stats["yellowCards"]["home"] + stats["yellowCards"]["away"]
    for i in range(totalYellow):
        isHome = random.random() < (stats["yellowCards"]["home"] / max(1, totalYellow))
        team_name = homeTeam if isHome else awayTeam
        events.append({
            "minute": rand(1, 90),
            "type": "yellow",
            "team": "home" if isHome else "away",
            "teamName": team_name,
            "description": f"{team_name} 球员犯规吃到黄牌"
        })
    if stats["redCards"]["home"] > 0:
        events.append({
            "minute": rand(30, 85),
            "type": "red",
            "team": "home",
            "teamName": homeTeam,
            "description": f"{homeTeam} 球员严重犯规直接红牌罚下"
        })
    if stats["redCards"]["away"] > 0:
        events.append({
            "minute": rand(30, 85),
            "type": "red",
            "team": "away",
            "teamName": awayTeam,
            "description": f"{awayTeam} 球员两黄变一红被罚下"
        })
    events.sort(key=lambda x: x["minute"])
    return events


def generateMatchAnalysis(homeTeam, awayTeam, stats, refereeAnalysis):
    """生成比赛分析结论"""
    insights = []
    sh = stats["score"]["home"]
    sa = stats["score"]["away"]
    xgH = float(stats["xG"]["home"])
    xgA = float(stats["xG"]["away"])
    if sh > sa:
        insights.append(f"{homeTeam} 主场取胜，实际进球 {sh} vs xG {stats['xG']['home']}，{'把握机会能力超强' if xgH < sh else '进攻效率符合预期'}")
    elif sh < sa:
        insights.append(f"{awayTeam} 客场奏凯，反击效率极高，xG {stats['xG']['away']} 支撑了最终比分")
    else:
        insights.append(f"双方握手言和，{'创造出大量机会但临门一脚欠佳' if xgH + xgA > 2.5 else '场面胶着机会寥寥'}")

    if stats["possession"]["home"] >= 60:
        insights.append(f"{homeTeam} 控球率达到 {stats['possession']['home']}%，主导了比赛节奏，但{'射门转化率偏低' if stats['shotsOnTarget']['home'] < 5 else '有效射门质量不错'}")
    elif stats["possession"]["away"] >= 60:
        insights.append(f"{awayTeam} 反客为主掌控场面，传球 {stats['passes']['away']} 次展现了传控功底")
    else:
        insights.append("双方控球率相对均衡，场面开放对攻激烈")

    ss = refereeAnalysis["statistics"]["strictnessScore"]
    totalY = stats["yellowCards"]["home"] + stats["yellowCards"]["away"]
    totalR = stats["redCards"]["home"] + stats["redCards"]["away"]
    totalF = stats["fouls"]["home"] + stats["fouls"]["away"]
    if ss >= 70:
        insights.append(f"裁判执法偏严（严格度 {ss}分），全场共出示 {totalY} 黄{totalR}红，直接影响了比赛节奏")
    elif ss <= 35:
        insights.append(f"裁判鼓励对抗（严格度 {ss}分），比赛流畅度高，犯规 {totalF} 次仅出示 {totalY} 张黄牌")
    else:
        insights.append("裁判执法尺度平衡，比赛中规中矩")

    if totalF >= 32:
        insights.append(f"本场比赛对抗激烈，双方共计 {totalF} 次犯规，拼抢强度拉满")
    return insights


def generateYesterdayMatches():
    """生成T-1（昨日）赛事"""
    matches = []
    allLeagues = []
    for region in ["europe", "asia", "australia"]:
        for l in LEAGUES[region]:
            allLeagues.append({**l, "region": region})
    selectedLeagues = pickN(allLeagues, 8)

    for league in selectedLeagues:
        teams = TEAMS.get(league["id"]) or TEAMS["epl"]
        matchCount = rand(1, 2)
        for m in range(matchCount):
            selected = pickN(teams, 2)
            homeTeam, awayTeam = selected[0], selected[1]
            referee = pick(REFEREES)
            stats = generateMatchStats(homeTeam, awayTeam)
            refHistory = generateRefereeHistory(referee, 5)
            refAnalysis = analyzeRefereeStyle(referee, refHistory)
            keyEvents = generateKeyEvents(homeTeam, awayTeam, stats)
            analysis = generateMatchAnalysis(homeTeam, awayTeam, stats, refAnalysis)
            hour = rand(19, 22)
            minute = pick([0, 15, 30, 45])
            matches.append({
                "id": f"y-{int(datetime.now().timestamp()*1000)}-{len(matches)}",
                "date": formatDate(getYesterday()),
                "time": f"{hour:02d}:{minute:02d}",
                "league": league,
                "region": league["region"],
                "homeTeam": homeTeam,
                "awayTeam": awayTeam,
                "venue": f"{homeTeam}主场",
                "stats": stats,
                "refereeAnalysis": refAnalysis,
                "keyEvents": keyEvents,
                "analysis": analysis
            })
    return matches


def generateTodayPreviews():
    """生成今日预告"""
    previews = []
    allLeagues = []
    for region in ["europe", "asia", "australia"]:
        for l in LEAGUES[region]:
            allLeagues.append({**l, "region": region})
    selectedLeagues = pickN(allLeagues, 10)

    featurePool = [
        "强强对话，争夺联赛榜首",
        "保级关键战，双方抢分心切",
        "德比大战，历史恩怨看点十足",
        "主场龙对阵客场龙，谁能更胜一筹",
        "近期状态火热，连胜势头能否延续",
        "欧战资格关键六分战",
        "新援首秀，期待磨合效果",
        "主帅对决，战术博弈引人关注",
        "进攻大战，双方防守皆有漏洞",
        "防守对决，预测低比分收场"
    ]

    for league in selectedLeagues:
        teams = TEAMS.get(league["id"]) or TEAMS["epl"]
        matchCount = rand(1, 2)
        for m in range(matchCount):
            selected = pickN(teams, 2)
            homeTeam, awayTeam = selected[0], selected[1]
            referee = pick(REFEREES)
            refHistory = generateRefereeHistory(referee, 5)
            refAnalysis = analyzeRefereeStyle(referee, refHistory)
            hour = rand(18, 22)
            minute = pick([0, 15, 30, 45])
            features = pickN(featurePool, rand(2, 3)).copy()
            if refAnalysis["style"] == "严格型":
                features.append(f"裁判{referee['name']}执法偏严，双方需注意动作规范")
            elif refAnalysis["style"] == "鼓励对抗型":
                features.append(f"裁判{referee['name']}鼓励对抗，比赛预计节奏快拼抢激烈")
            else:
                features.append(f"裁判{referee['name']}执法平衡，比赛流畅度值得期待")

            previews.append({
                "id": f"t-{int(datetime.now().timestamp()*1000)}-{len(previews)}",
                "date": formatDate(getToday()),
                "time": f"{hour:02d}:{minute:02d}",
                "league": league,
                "region": league["region"],
                "homeTeam": homeTeam,
                "awayTeam": awayTeam,
                "venue": f"{homeTeam}主场",
                "refereeAnalysis": refAnalysis,
                "features": features,
                "predictedDifficulty": rand(1, 5),
                "homeRecentForm": pickN(["胜", "平", "负", "胜", "平", "负", "胜"], 5),
                "awayRecentForm": pickN(["胜", "平", "负", "胜", "平", "负", "胜"], 5),
                "h2hLast5": {
                    "homeWins": rand(0, 4),
                    "draws": rand(0, 3),
                    "awayWins": rand(0, 4)
                }
            })
    return previews


def generatePushDigest(yesterdayMatches, todayPreviews):
    """生成推送摘要"""
    def winner_of(m):
        sh, sa = m["stats"]["score"]["home"], m["stats"]["score"]["away"]
        if sh > sa: return m["homeTeam"] + "获胜"
        if sh < sa: return m["awayTeam"] + "获胜"
        return "战平"

    yesterdaySummary = "；".join(
        f"{m['league']['flag']} {m['league']['name']}：{m['homeTeam']} {m['stats']['score']['home']}-{m['stats']['score']['away']} {m['awayTeam']}（{winner_of(m)}）"
        for m in yesterdayMatches[:3]
    )
    todaySummary = "；".join(
        f"{m['league']['flag']} {m['homeTeam']} vs {m['awayTeam']}（{m['features'][0]}）"
        for m in todayPreviews[:3]
    )
    return {
        "title": f"\u26bd 足球赛道日报 - {formatDate(getToday())}",
        "yesterdaySummary": yesterdaySummary,
        "todaySummary": todaySummary,
        "yesterdayCount": len(yesterdayMatches),
        "todayCount": len(todayPreviews),
        "fullReport": True
    }
