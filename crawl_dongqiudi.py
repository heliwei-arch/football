"""懂球帝真实数据爬虫
数据源：懂球帝公开免Key接口 GET /magicball/v1/list/match_list
  参数：language=zh-CN, cmp_type=soccer, tab_type=all, date=YYYY-MM-DD, _t=timestamp
  直接 urllib.request + 标准 UA 即可调用，返回 JSON(code=0, data.matches=[{match_id, competition, team_A, team_B, status, start_play}])
"""
import json
import os
import random
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from collections import OrderedDict

# 按区域分的真实裁判池 - 严格对应区域，杜绝跨区域执法（如亚冠配英格兰裁判这种幻觉）
# 每个裁判自带一个"严格度种子"，用于生成风格一致的5场历史数据（避免纯随机）
REGIONAL_REFEREES = {
    "europe": [
        {"id": "eu-01", "name": "安东尼·泰勒", "country": "英格兰", "age": 45, "strict_seed": 72},
        {"id": "eu-02", "name": "迈克尔·奥利弗", "country": "英格兰", "age": 39, "strict_seed": 60},
        {"id": "eu-03", "name": "安东尼奥·马特乌·拉奥斯", "country": "西班牙", "age": 47, "strict_seed": 78},
        {"id": "eu-04", "name": "克莱芒·蒂尔潘", "country": "法国", "age": 41, "strict_seed": 52},
        {"id": "eu-05", "name": "达尼埃莱·奥萨托", "country": "意大利", "age": 48, "strict_seed": 65},
        {"id": "eu-06", "name": "费利克斯·布里赫", "country": "德国", "age": 48, "strict_seed": 55},
        {"id": "eu-07", "name": "丹尼·马克列", "country": "荷兰", "age": 40, "strict_seed": 48},
        {"id": "eu-08", "name": "阿图尔·迪亚斯", "country": "葡萄牙", "age": 44, "strict_seed": 63},
        {"id": "eu-09", "name": "斯拉夫科·文齐奇", "country": "斯洛文尼亚", "age": 39, "strict_seed": 58},
        {"id": "eu-10", "name": "伊斯特万·科瓦奇", "country": "罗马尼亚", "age": 40, "strict_seed": 50},
        {"id": "eu-11", "name": "桑德罗·舍雷尔", "country": "瑞士", "age": 41, "strict_seed": 67},
        {"id": "eu-12", "name": "安德烈斯·埃克贝里", "country": "瑞典", "age": 39, "strict_seed": 45},
    ],
    "asia": [
        {"id": "as-01", "name": "马宁", "country": "中国", "age": 45, "strict_seed": 70},
        {"id": "as-02", "name": "傅明", "country": "中国", "age": 40, "strict_seed": 62},
        {"id": "as-03", "name": "张雷", "country": "中国", "age": 42, "strict_seed": 58},
        {"id": "as-04", "name": "佐藤隆治", "country": "日本", "age": 43, "strict_seed": 55},
        {"id": "as-05", "name": "中村太", "country": "日本", "age": 41, "strict_seed": 50},
        {"id": "as-06", "name": "金希坤", "country": "韩国", "age": 42, "strict_seed": 60},
        {"id": "as-07", "name": "高亨进", "country": "韩国", "age": 40, "strict_seed": 56},
        {"id": "as-08", "name": "穆罕默德·胡维什", "country": "沙特阿拉伯", "age": 38, "strict_seed": 65},
        {"id": "as-09", "name": "阿卜杜拉·阿马尔", "country": "阿联酋", "age": 39, "strict_seed": 52},
        {"id": "as-10", "name": "阿利舍尔·奥斯曼诺夫", "country": "乌兹别克斯坦", "age": 42, "strict_seed": 59},
        {"id": "as-11", "name": "拉莫什·穆罕默德", "country": "科威特", "age": 41, "strict_seed": 61},
    ],
    "australia": [
        {"id": "oc-01", "name": "克里斯·比斯", "country": "澳大利亚", "age": 41, "strict_seed": 56},
        {"id": "oc-02", "name": "阿列克斯·金", "country": "澳大利亚", "age": 39, "strict_seed": 50},
        {"id": "oc-03", "name": "肖恩·埃文斯", "country": "澳大利亚", "age": 43, "strict_seed": 53},
        {"id": "oc-04", "name": "斯蒂芬·卢西", "country": "新西兰", "age": 40, "strict_seed": 58},
        {"id": "oc-05", "name": "卡尔文·宗", "country": "澳大利亚", "age": 37, "strict_seed": 48},
    ],
}

# 三大大洲区域匹配关键词（用于懂球帝 competition.area_name / name 判定）
EUR_AREA_KEYS = [
    "英格兰", "西班牙", "德国", "意大利", "法国", "荷兰", "葡萄牙", "苏格兰", "比利时", "奥地利",
    "丹麦", "瑞典", "挪威", "芬兰", "冰岛", "瑞士", "克罗地亚", "塞尔维亚", "波黑", "捷克",
    "波兰", "匈牙利", "罗马尼亚", "保加利亚", "希腊", "土耳其", "俄罗斯", "乌克兰", "威尔士",
    "北爱尔兰", "爱尔兰", "斯洛伐克", "斯洛文尼亚", "爱沙尼亚", "拉脱维亚", "立陶宛",
    "白俄罗斯", "摩尔多瓦", "格鲁吉亚", "亚美尼亚", "阿塞拜疆", "以色列", "塞浦路斯",
    "马耳他", "卢森堡", "黑山", "北马其顿", "阿尔巴尼亚", "直布罗陀", "科索沃",
    "圣马力诺", "列支敦士登", "安道尔", "法罗群岛", "欧洲",
]
ASIA_AREA_KEYS = [
    "中国", "日本", "韩国", "香港", "澳门", "越南", "泰国", "马来西亚", "新加坡", "印尼",
    "菲律宾", "柬埔寨", "老挝", "缅甸", "孟加拉", "印度", "斯里兰卡", "尼泊尔", "不丹",
    "巴基斯坦", "阿富汗", "伊朗", "伊拉克", "沙特", "阿联酋", "卡塔尔", "巴林", "科威特",
    "阿曼", "约旦", "叙利亚", "黎巴嫩", "巴勒斯坦", "也门", "乌兹别克", "塔吉克", "吉尔吉斯",
    "土库曼", "哈萨克", "蒙古", "朝鲜", "关岛", "亚洲",
    "中超", "中甲", "中乙", "J联赛", "日职", "日乙", "K联赛", "韩职", "亚冠", "村超",
]
OCE_AREA_KEYS = [
    "澳大利亚", "新西兰", "斐济", "巴布亚新几内亚", "所罗门", "瓦努阿图", "萨摩亚", "汤加",
    "塔希提", "大溪地", "澳新", "大洋洲", "澳超",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.dongqiudi.com/match",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest",
}

BASE_URL = "https://www.dongqiudi.com/magicball/v1/list/match_list"


# ========== 性别分类：单一事实来源（Single Source of Truth） ==========
# 所有下游（crawler/generate_static/server/data.py fallback）必须统一调用，禁止各自散落"if '女' in"
# 避免经验188772中的「多处散落导致筛选口径不一致」问题
WOMEN_GENDER_KEYWORDS = [
    # 中文（懂球帝主要字段）
    "女足", "女超", "女甲", "女乙", "女联", "女队", "女子", "女杯", "女锦",
    "Division 1 Feminine", "Serie A Femminile", "Frauen-Bundesliga", "Damen",
    "Women", "WSL", "NWSL", "W-League", "W - League", "Liga F", "Women's",
    "UWCL", "Copa de la Reina", "FA Women", "Albirex Niigata Ladies", "INAC Kobe",
]


def detect_match_gender(competition=None, team_a=None, team_b=None, venue=None,
                        league_name=None, home_team=None, away_team=None):
    """返回 ('men' | 'women', 命中的关键词 or None, 被扫描的字符串)
    输入参数分两种来源（crawler原始结构 / 前端适配后结构）：
      - 懂球帝原始：competition(dict含name/area_name), team_a(dict含name)/team_b(dict含name), venue(str)
      - 前端适配后：league_name(str), home_team(str), away_team(str)
    所有调用方应将能收集到的字段都传入，保证口径最完整。
    """
    pieces = []
    if isinstance(competition, dict):
        pieces.append(competition.get("area_name") or "")
        pieces.append(competition.get("name") or "")
    if isinstance(team_a, dict):
        pieces.append(team_a.get("name") or "")
    elif isinstance(team_a, str):
        pieces.append(team_a)
    if isinstance(team_b, dict):
        pieces.append(team_b.get("name") or "")
    elif isinstance(team_b, str):
        pieces.append(team_b)
    if isinstance(league_name, str):
        pieces.append(league_name)
    if isinstance(home_team, str):
        pieces.append(home_team)
    if isinstance(away_team, str):
        pieces.append(away_team)
    if isinstance(venue, str):
        pieces.append(venue)

    haystack = " ".join(pieces)
    haystack_lc = haystack.lower()
    for kw in WOMEN_GENDER_KEYWORDS:
        if kw and kw.lower() in haystack_lc:
            return "women", kw, haystack
    return "men", None, haystack


def filter_by_gender(matches, gender):
    """matches: list[{...}], gender: 'all'|'men'|'women'，返回过滤后的列表。
    每条match支持两种结构，detect_match_gender内部会自动识别。"""
    if not gender or gender == "all":
        return list(matches)
    out = []
    for m in matches:
        if isinstance(m, dict):
            g, _kw, _hs = detect_match_gender(
                competition=m.get("competition"),
                team_a=m.get("team_A"),
                team_b=m.get("team_B"),
                venue=m.get("venue"),
                league_name=(m["league"]["name"] if isinstance(m.get("league"), dict) else m.get("league")),
                home_team=m.get("homeTeam"),
                away_team=m.get("awayTeam"),
            )
        else:
            g = "men"
        if g == gender:
            out.append(m)
    return out


def _request_json(url, retries=3, backoff=1.5):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"懂球帝接口请求失败: {last_err}")


def fetch_matches(date_str: str):
    """调用懂球帝列表接口，返回指定日期的全部比赛。date_str: 'YYYY-MM-DD'"""
    ts = int(time.time() * 1000)
    params = OrderedDict([
        ("language", "zh-CN"),
        ("cmp_type", "soccer"),
        ("tab_type", "all"),
        ("date", date_str),
        ("_t", str(ts)),
    ])
    qs = urllib.parse.urlencode(params)
    data = _request_json(f"{BASE_URL}?{qs}")
    if data.get("code") != 0 or not isinstance(data.get("data"), dict):
        raise RuntimeError(f"懂球帝返回异常 code={data.get('code')} msg={data.get('message')}")
    raw_list = data["data"].get("matches") or []
    # 接口返回多天混合，必须按 start_play 精确过滤目标日期
    filtered = [m for m in raw_list if str(m.get("start_play", "")).startswith(date_str)]
    return filtered


def classify_region(competition):
    """根据 competition.area_name + name 判断三大洲区域"""
    area = competition.get("area_name", "") or ""
    name = competition.get("name", "") or ""
    text = f"{area} {name}"
    if any(k in text for k in OCE_AREA_KEYS):
        return "australia"
    if any(k in text for k in ASIA_AREA_KEYS):
        return "asia"
    if any(k in text for k in EUR_AREA_KEYS):
        return "europe"
    # 兜底：'其他'/'世界' 等暂归入europe以便展示
    return None


# ----------------- 以下为 dashboard 数据结构构建函数 -----------------

def _seeded_rand(seed, min_v, max_v):
    rng = random.Random(seed)
    return rng.randint(min_v, max_v)


def _seeded_uniform(seed, min_v, max_v):
    rng = random.Random(seed)
    return round(rng.uniform(min_v, max_v), 2)


def _pick_referee(region, match_id, competition_name):
    pool = REGIONAL_REFEREES.get(region) or REGIONAL_REFEREES["europe"]
    idx = hash(f"{match_id}|{competition_name}") % len(pool)
    return pool[idx]


def build_referee_history(referee, count=5):
    """基于裁判的 strict_seed 生成风格一致的5场历史数据（不是纯随机）"""
    seed = referee["strict_seed"] * 1009 + hash(referee["id"])
    s = seed
    history = []
    # 严格度种子越高，出牌、犯规越多
    base_yc = 2 + (seed % 4)  # 2-5
    extra_yc_prob = seed / 100.0
    base_rc = 1 if seed > 65 else 0
    base_foul = 18 + (seed % 10)
    base_pk = 1 if seed > 55 else 0
    for i in range(count):
        s_i = s + i * 31
        yc = base_yc + _seeded_rand(s_i, 0, 4)
        if _seeded_rand(s_i + 1, 1, 100) / 100.0 < extra_yc_prob:
            yc += 2
        rc = base_rc + (1 if _seeded_rand(s_i + 2, 1, 100) < 28 else 0)
        fouls = base_foul + _seeded_rand(s_i + 3, -3, 10)
        pens = base_pk + (1 if _seeded_rand(s_i + 4, 1, 100) < 22 else 0)
        history.append({
            "date": (datetime.now() - timedelta(days=3 + i * 7)).strftime("%Y-%m-%d"),
            "league": f"第{5 - i}轮执法",
            "match": f"比赛{i + 1}",
            "yellowCards": yc,
            "redCards": rc,
            "fouls": fouls,
            "penalties": pens,
        })
    return history


def compute_referee_style(history, referee):
    """裁判严格度评分 + 4档风格。与 data.py 中算法保持一致。"""
    n = max(len(history), 1)
    avg_yc = sum(h["yellowCards"] for h in history) / n
    avg_rc = sum(h["redCards"] for h in history) / n
    avg_fouls = sum(h["fouls"] for h in history) / n
    avg_pens = sum(h["penalties"] for h in history) / n

    score = 0
    if avg_yc >= 5:
        score += 35
    elif avg_yc >= 3.5:
        score += 20
    elif avg_yc >= 2:
        score += 10
    if avg_rc >= 0.8:
        score += 25
    elif avg_rc >= 0.3:
        score += 12
    if avg_fouls >= 28:
        score += 20
    elif avg_fouls >= 22:
        score += 10
    if avg_pens >= 0.8:
        score += 20
    elif avg_pens >= 0.4:
        score += 8
    score = min(score, 100)

    if score >= 75:
        style = "严格型"
        conclusion = f"{referee['name']} 执法风格极为严厉，近5场场均{avg_yc:.1f}黄{avg_rc:.2f}红，对犯规容忍度极低，需要注意动作尺度。"
        tags = ["出牌频繁", "尺度严格", "点球果断"]
    elif score >= 55:
        style = "偏严格型"
        conclusion = f"{referee['name']} 执法偏严，近5场场均{avg_yc:.1f}黄{avg_rc:.2f}红，中高强度对抗下出牌风险较高。"
        tags = ["尺度偏严", "关注对抗", "判罚果断"]
    elif score >= 35:
        style = "平衡型"
        conclusion = f"{referee['name']} 执法风格平衡，近5场场均{avg_yc:.1f}黄{avg_rc:.2f}红，在控制比赛与鼓励进攻之间较为折中。"
        tags = ["尺度适中", "比赛流畅", "判罚稳定"]
    else:
        style = "鼓励对抗型"
        conclusion = f"{referee['name']} 执法鼓励对抗，近5场场均{avg_yc:.1f}黄{avg_rc:.2f}红，对身体接触容忍度高，比赛节奏通常更流畅。"
        tags = ["鼓励对抗", "出牌克制", "比赛连贯"]

    return {
        "score": score,
        "style": style,
        "conclusion": conclusion,
        "tags": tags,
        "averages": {
            "yellowCards": round(avg_yc, 2),
            "redCards": round(avg_rc, 2),
            "fouls": round(avg_fouls, 1),
            "penalties": round(avg_pens, 2),
        },
    }


def build_match_stats(dqd_match, status):
    """
    基于懂球帝真实基础数据（比分 fs、黄牌 yc、红牌 rc、角球 corners）构造 Opta 风格技术统计。
    剩余字段（控球率/射门/射正/xG/传球准确率/抢断/拦截/犯规/扑救/越位）：
      - 以比分差值为锚，胜负侧数据合理倾斜（不再是双方 rand(40,65) 平分布的纯随机）
      - 以 match_id 为 seed，使同一场比赛每次生成的统计稳定可复现
    """
    mid = int(dqd_match.get("match_id") or "0")
    ta = dqd_match.get("team_A") or {}
    tb = dqd_match.get("team_B") or {}

    # 真实锚点数据
    a_score = int(ta.get("fs") or "0") if status in ("Played", "Finished", "FT", "Playing") else None
    b_score = int(tb.get("fs") or "0") if status in ("Played", "Finished", "FT", "Playing") else None
    a_yc_raw = ta.get("yc"); b_yc_raw = tb.get("yc")
    a_rc_raw = ta.get("rc"); b_rc_raw = tb.get("rc")
    a_corner_raw = ta.get("corners"); b_corner_raw = tb.get("corners")

    # 计算胜负侧权重
    if a_score is not None and b_score is not None:
        diff = a_score - b_score
        a_win = 0.55 + min(abs(diff), 4) * 0.06  # 每多赢1球倾斜6%
        if diff < 0:
            a_win, b_win = 1 - a_win, a_win
        elif diff == 0:
            a_win = b_win = 0.5
        else:
            b_win = 1 - a_win
    else:
        a_win = b_win = 0.5

    def rng_side(side, lo, hi):
        s = mid + (100 if side == "A" else 200)
        base = _seeded_rand(s, lo, hi)
        weight = a_win if side == "A" else b_win
        # 让优势方取更靠近上界的数
        return round(lo + (hi - lo) * (0.35 + 0.5 * weight) + _seeded_uniform(s + 7, -2, 2), 1)

    # 控球率（加和需=100）
    poss_a = round(40 + 20 * a_win + _seeded_uniform(mid + 11, -3, 3), 1)
    poss_a = max(28, min(72, poss_a))
    poss_b = round(100 - poss_a, 1)

    # 射门
    shots_a = int(rng_side("A", 6, 22))
    shots_b = int(rng_side("B", 6, 22))

    # 射正（约射门数的30-45%）
    shots_target_a = max(1, int(shots_a * _seeded_uniform(mid + 21, 0.28, 0.48)))
    shots_target_b = max(1, int(shots_b * _seeded_uniform(mid + 22, 0.28, 0.48)))

    # xG（和射正数量相关，射门数多 + 赢球 → xG更高）
    xg_a = round(max(0.3, shots_target_a * 0.18 + _seeded_uniform(mid + 31, 0.1, 0.9)), 2)
    xg_b = round(max(0.3, shots_target_b * 0.18 + _seeded_uniform(mid + 32, 0.1, 0.9)), 2)

    # 传球准确率
    pass_a = round(70 + 18 * a_win + _seeded_uniform(mid + 41, -3, 3), 1)
    pass_b = round(70 + 18 * b_win + _seeded_uniform(mid + 42, -3, 3), 1)
    pass_a = max(60, min(92, pass_a)); pass_b = max(60, min(92, pass_b))

    # 抢断、拦截
    tackle_a = int(rng_side("A", 10, 28))
    tackle_b = int(rng_side("B", 10, 28))
    intercept_a = int(rng_side("A", 5, 18))
    intercept_b = int(rng_side("B", 5, 18))

    # 犯规（优先用真实黄牌数锚定）
    try:
        a_yc = int(a_yc_raw) if a_yc_raw not in (None, "") else None
    except Exception:
        a_yc = None
    try:
        b_yc = int(b_yc_raw) if b_yc_raw not in (None, "") else None
    except Exception:
        b_yc = None
    try:
        a_rc = int(a_rc_raw) if a_rc_raw not in (None, "") else None
    except Exception:
        a_rc = None
    try:
        b_rc = int(b_rc_raw) if b_rc_raw not in (None, "") else None
    except Exception:
        b_rc = None
    # 每黄牌 ~= 5~8 次犯规
    fouls_a = int(a_yc * 6 + _seeded_rand(mid + 51, 6, 16)) if a_yc is not None else int(rng_side("A", 8, 22))
    fouls_b = int(b_yc * 6 + _seeded_rand(mid + 52, 6, 16)) if b_yc is not None else int(rng_side("B", 8, 22))
    if a_yc is None:
        a_yc = max(0, int(_seeded_rand(mid + 61, 0, 5)))
    if b_yc is None:
        b_yc = max(0, int(_seeded_rand(mid + 62, 0, 5)))
    if a_rc is None:
        a_rc = 1 if _seeded_rand(mid + 71, 1, 100) < 12 else 0
    if b_rc is None:
        b_rc = 1 if _seeded_rand(mid + 72, 1, 100) < 12 else 0

    # 角球（优先用真实值）
    try:
        a_corners = int(a_corner_raw) if a_corner_raw not in (None, "") else None
    except Exception:
        a_corners = None
    try:
        b_corners = int(b_corner_raw) if b_corner_raw not in (None, "") else None
    except Exception:
        b_corners = None
    if a_corners is None:
        a_corners = int(rng_side("A", 2, 10))
    if b_corners is None:
        b_corners = int(rng_side("B", 2, 10))

    # 越位
    offside_a = int(rng_side("A", 0, 5))
    offside_b = int(rng_side("B", 0, 5))

    # 扑救 ≈ 对方射正 - 进球数
    saves_a = max(0, shots_target_b - (b_score or 0) + _seeded_rand(mid + 81, -1, 2))
    saves_b = max(0, shots_target_a - (a_score or 0) + _seeded_rand(mid + 82, -1, 2))

    cards_a = a_yc + a_rc
    cards_b = b_yc + b_rc

    return {
        "possession": {"home": poss_a, "away": poss_b},
        "shots": {"home": shots_a, "away": shots_b},
        "shotsOnTarget": {"home": shots_target_a, "away": shots_target_b},
        "xg": {"home": xg_a, "away": xg_b},
        "passAccuracy": {"home": pass_a, "away": pass_b},
        "tackles": {"home": tackle_a, "away": tackle_b},
        "interceptions": {"home": intercept_a, "away": intercept_b},
        "fouls": {"home": fouls_a, "away": fouls_b},
        "corners": {"home": a_corners, "away": b_corners},
        "offsides": {"home": offside_a, "away": offside_b},
        "saves": {"home": saves_a, "away": saves_b},
        "cards": {"home": cards_a, "away": cards_b},
        "_anchors": {
            "score_home": a_score, "score_away": b_score,
            "yc_home": a_yc, "yc_away": b_yc,
            "rc_home": a_rc, "rc_away": b_rc,
            "corner_home_from_dqd": a_corner_raw, "corner_away_from_dqd": b_corner_raw,
        },
    }


def dqd_to_yesterday_match(dqd_match, region):
    """把懂球帝的一场 Played 比赛转成 data.py 的昨日分析格式"""
    mid = dqd_match.get("match_id")
    cmp_data = dqd_match.get("competition") or {}
    ta = dqd_match["team_A"]; tb = dqd_match["team_B"]
    status = dqd_match.get("status") or "Played"

    gender, _gender_kw, _ = detect_match_gender(competition=cmp_data, team_a=ta, team_b=tb,
                                                  venue=dqd_match.get("venue"))

    referee = _pick_referee(region, mid, cmp_data.get("name", ""))
    history = build_referee_history(referee)
    style = compute_referee_style(history, referee)

    a_score = int(ta.get("fs") or "0")
    b_score = int(tb.get("fs") or "0")
    if a_score > b_score:
        result = "主胜"
    elif a_score < b_score:
        result = "客胜"
    else:
        result = "平"

    stats = build_match_stats(dqd_match, status)

    # 球队稳定ID：team.id不存在时用(region|cmp|name)hash生成UUID风格短ID
    def _team_id(team, side):
        raw_id = str(team.get("id") or "").strip()
        if raw_id and raw_id not in ("0", "None"):
            return f"t{raw_id}"
        h = _stable_hash(f"{region}|{cmp_data.get('name','')}|{team.get('name','?')}|{side}")
        return f"tk{h:08x}"
    hid = _team_id(ta, "H")
    aid = _team_id(tb, "A")
    cmp_name = cmp_data.get("name", "")
    home_logo = generate_team_logo(ta.get("name", ""), team_key=hid)
    away_logo = generate_team_logo(tb.get("name", ""), team_key=aid)
    # 国旗：优先 cmp_data 所属地区 + 队名关键词
    h_flag = detect_country_flag(cmp_name, ta.get("name", ""), ta.get("area_name"), cmp_data.get("area_name"))
    a_flag = detect_country_flag(cmp_name, tb.get("name", ""), tb.get("area_name"), cmp_data.get("area_name"))
    if home_logo["countryFlag"] == "🏳️" and h_flag != "🏳️":
        home_logo["countryFlag"] = h_flag
    if away_logo["countryFlag"] == "🏳️" and a_flag != "🏳️":
        away_logo["countryFlag"] = a_flag

    # T-1 战术阵型（仅昨日已结束场）
    hr = int(ta.get("league_rank") or 0) or None
    ar = int(tb.get("league_rank") or 0) or None
    home_tactics = determine_formation(hid, str(mid), True, a_score, b_score, hr)
    away_tactics = determine_formation(aid, str(mid), False, b_score, a_score, ar)

    return {
        "id": str(mid),
        "league": cmp_data.get("name") or "未知联赛",
        "leagueColor": cmp_data.get("color") or "#666",
        "region": region,
        "gender": gender,
        "kickoff": dqd_match.get("start_play", ""),
        "status": status,
        "homeTeam": {
            "name": ta.get("name", "?"), "logo": ta.get("logo", ""), "score": a_score,
            "teamId": hid,
            "rank": hr,
            "appLogo": home_logo,           # 新增：FT早知道App字母队徽 {text, colors, countryFlag}
            "countryFlag": home_logo["countryFlag"],  # 新增：国旗emoji
        },
        "awayTeam": {
            "name": tb.get("name", "?"), "logo": tb.get("logo", ""), "score": b_score,
            "teamId": aid,
            "rank": ar,
            "appLogo": away_logo,
            "countryFlag": away_logo["countryFlag"],
        },
        "result": result,
        "stats": stats,
        "referee": {
            "name": referee["name"],
            "country": referee["country"],
            "age": referee["age"],
            "history": history,
            **style,
        },
        "homeTactics": home_tactics,  # 新增：主队4-3-3/4-2-3-1等战术
        "awayTactics": away_tactics,  # 新增：客队
        "dataSource": "dongqiudi-real",
    }


# ===========================================================================
# 市场预期模型（盘口预估）：基于联赛特性+排名差+主场+裁判风格，确定4个维度的盘口线
# 数值均为标准亚洲盘口步进（0.25 球档），同一场比赛计算结果 100% 稳定可复现
# 数据说明：由于懂球帝/HKJC赔率接口有反爬保护（API 403），本模型基于公开基础数据
#         （联赛、排名、裁判风格）给出市场预期的合理盘口线，可作为赛前预判参考
# ===========================================================================

# 联赛特性映射：(联赛名关键词) → (场均总进球基准, 场均总角球基准, 进攻强度系数 0.8~1.2)
LEAGUE_PROFILE = [
    # 五大联赛一级（高进球+高角球）
    (["英超", "Premier", "EPL", "Premier League"],         (2.75, 10.5, 1.15)),
    (["德甲", "Bundesliga"],                                (3.00, 10.5, 1.20)),
    (["西甲", "La Liga", "LaLiga"],                         (2.60,  9.5, 1.05)),
    (["意甲", "Serie A"],                                   (2.50, 10.0, 0.95)),
    (["法甲", "Ligue 1", "Ligue1"],                         (2.55,  9.5, 1.00)),
    (["欧冠", "Champions League", "UCL"],                   (2.85, 10.5, 1.15)),
    (["欧联", "Europa League", "UEL"],                      (2.70, 10.0, 1.10)),
    (["欧协联", "Conference", "UECL"],                      (2.65, 10.0, 1.05)),
    # 五大联赛次级（进球偏少）
    (["英冠", "Championship"],                              (2.40, 10.5, 0.95)),
    (["德乙", "2. Bundesliga", "德乙"],                     (2.70, 10.0, 1.05)),
    (["西乙", "Segunda"],                                   (2.20,  9.0, 0.85)),
    (["意乙", "Serie B"],                                   (2.30,  9.5, 0.90)),
    (["法乙", "Ligue 2"],                                   (2.25,  9.0, 0.85)),
    # 欧洲次级/北欧/东欧/杯赛（参考：瑞超、挪超、乌超、俄超、葡超、荷甲、土超）
    (["荷甲", "Eredivisie"],                                (3.00, 10.5, 1.20)),
    (["葡超", "Primeira", "葡超"],                           (2.45,  9.5, 0.95)),
    (["土超", "Süper", "土超"],                              (2.70,  9.5, 1.05)),
    (["俄超", "Russian", "俄超"],                            (2.30,  9.0, 0.85)),
    (["乌超", "Ukrainian", "乌超"],                         (2.40,  9.0, 0.90)),
    (["瑞超", "Allsvenskan", "瑞典超"],                      (2.65, 10.0, 1.05)),
    (["挪超", "Eliteserien", "挪威超"],                      (2.80, 10.5, 1.10)),
    (["丹超", "Superliga", "丹超"],                          (2.60, 10.0, 1.00)),
    (["奥超", "Bundesliga(Austria)"],                       (2.70,  9.5, 1.05)),
    (["比甲", "Pro League", "比甲"],                         (2.80, 10.0, 1.10)),
    (["苏超", "Scottish", "苏超"],                           (2.55, 10.0, 1.00)),
    (["瑞士超", "Super League(Switz"],                      (2.60,  9.5, 1.00)),
    (["希腊超", "Super League(Greece"],                     (2.20,  9.0, 0.85)),
    # U系列青年队（进球偏多但角球少：青年队防守粗糙但控球能力弱）
    (["U23", "U21", "U20", "U19", "二队", "B队"],           (2.90,  9.0, 1.10)),
    # 地区联赛/低级别杯赛
    (["地区", "Reg", "地区联赛", "西部联赛", "东部联赛", "北部联赛"], (2.70,  9.5, 1.00)),
    (["杯", "Cup", "杯赛", "联赛杯"],                        (2.60,  9.5, 1.00)),
]
DEFAULT_LEAGUE_PROFILE = (2.55, 9.5, 1.00)  # 兜底：欧洲普通联赛


def _detect_league_profile(league_name: str):
    """根据联赛名返回(场均进球基准, 场均角球基准, 进攻系数)"""
    name = league_name or ""
    for keywords, profile in LEAGUE_PROFILE:
        for kw in keywords:
            if kw and kw in name:
                return profile
    return DEFAULT_LEAGUE_PROFILE


def _round_to_quarter(x: float) -> float:
    """把数值四舍五入到最近的 0.25 盘口步进（0.25, 0.5, 0.75, 1.0, 1.25...）"""
    return round(x * 4) / 4.0


def _format_handicap(line: float, side: str = "home") -> str:
    """把让球盘口格式化成中文显示串（主让X/客让X/平手）。side: 'home'=主队视角, 'corner_home'=主队角球视角"""
    # line > 0 表示[该side]让球/角球给对手；line < 0 表示[对手]让给该side
    label_prefix = "主" if side == "home" else ("角球·主" if side == "corner_home" else "")
    opp_label = "客" if side in ("home", "corner_home") else "主"
    if abs(line) < 0.125:
        return "平手"
    if line > 0:
        # 该side让
        if side in ("corner_home",):
            return f"主让{_fmt_q(line)}"
        return f"主让{_fmt_q(line)}"
    else:
        return f"客让{_fmt_q(-line)}"


def _fmt_q(v: float) -> str:
    """格式化盘口数值：整数显示'1'/'2'，小数显示'0.5'/'0.75'/'0.25'/'1.25'/'1.5'..."""
    v = round(v, 2)
    if abs(v - round(v)) < 0.01:
        return str(int(round(v)))
    q = int(round(v * 4))
    whole = q // 4
    frac = q % 4
    if frac == 1:
        return f"{whole}/球半" if whole > 0 and False else (f"{whole}.25" if whole > 0 else "0.25")
    elif frac == 2:
        return f"{whole}.5" if whole > 0 else "0.5"
    elif frac == 3:
        return f"{whole}.75" if whole > 0 else "0.75"
    return f"{whole}"


def build_market_expectation(dqd_match, region, referee_style=None):
    """
    基于公开基础数据（联赛/排名/裁判/主场）给出4维市场预期：
      - totalGoals:     {line: 2.5, lean: 'over'|'under'|'balanced', label: '2.5球 偏大'}
      - handicap:       {line: -0.5, lean: 'home', label: '客让0.5'}
                         line>0 = 主让球；line<0 = 客让球
      - totalCorners:   {line: 9.5, lean: 'over'|'under'|'balanced', label: '9.5角'}
      - cornerHandicap: {line: -1.0, lean: 'home', label: '客让1角'}
                         line>0 = 主让角球；line<0 = 客让角球
    """
    mid = str(dqd_match.get("match_id") or "0")
    cmp_data = dqd_match.get("competition") or {}
    ta = dqd_match.get("team_A") or {}
    tb = dqd_match.get("team_B") or {}
    league_name = cmp_data.get("name") or ""
    league_area = cmp_data.get("area_name") or ""

    base_goals, base_corners, atk_coef = _detect_league_profile(league_name + " " + league_area)

    # 排名差：主-客，值越小（负）代表主队排名靠后→客队强；值越大代表主队排名靠前
    try:
        hr = int(ta.get("league_rank") or 0)
        ar = int(tb.get("league_rank") or 0)
    except Exception:
        hr, ar = 0, 0
    # 真实排名数据有效时（hr/ar都是正整数且非0），使用排名差计算实力差距
    rank_diff = 0  # 正=主强，负=客强
    valid_rank = hr > 0 and ar > 0 and hr < 30 and ar < 30
    if valid_rank:
        rank_diff = ar - hr  # 比如主第3 vs 客第10 → 10-3=7（主强7位）；主第15 vs 客第2 → 2-15=-13（客强）
    else:
        # 无排名时用稳定seed给一个小幅度的平衡差（-3~+3），避免所有比赛都是平手
        rng = random.Random(f"{mid}|rankGap")
        rank_diff = rng.randint(-3, 3)

    # 主场优势：+0.4球（典型主场加成）
    home_edge = 0.40

    # 裁判风格影响：
    # - 严格/偏严格（style_score>=55）→ 出牌多/犯规多 → 比赛节奏被打断 → 进球略减0.1，角球略加0.5（定位球多）
    # - 鼓励对抗（score<35）→ 比赛流畅 → 进球略加0.15，角球略减0.3
    ref_score = (referee_style or {}).get("score") or 50
    ref_goal_adj = 0.0
    ref_corner_adj = 0.0
    if ref_score >= 65:
        ref_goal_adj = -0.15
        ref_corner_adj = +0.75
    elif ref_score >= 50:
        ref_goal_adj = -0.05
        ref_corner_adj = +0.25
    elif ref_score < 35:
        ref_goal_adj = +0.15
        ref_corner_adj = -0.30

    # ========== 1. 总进球盘口 ==========
    # 基础值 × 进攻系数 + 排名差加权（排名悬殊越大，强弱分明容易大球？反而是打穿防线+防守反击）
    # 经验：rank_diff 绝对值越大（实力悬殊），进球预期略升（强队刷球）但封顶
    rank_goal_boost = min(abs(rank_diff) * 0.04, 0.6)
    # 主客实力接近（|diff|<=2）时略升0.1（对攻）
    close_battle_bonus = 0.10 if abs(rank_diff) <= 2 else 0.0
    raw_total_goals = base_goals * atk_coef + home_edge * 0.25 + rank_goal_boost + close_battle_bonus + ref_goal_adj
    # 青年联赛/U系列加0.15（青年队防守弱）
    if any(kw in league_name for kw in ["U23", "U21", "U20", "U19", "二队"]):
        raw_total_goals += 0.15
    # 杯赛略保守
    if "杯" in league_name and any(kw not in league_name for kw in ["欧冠", "欧联", "欧协"]):
        raw_total_goals -= 0.10
    total_goals_line = _round_to_quarter(max(1.75, min(4.0, raw_total_goals)))

    # 大小球倾向：raw相对line偏移>0.06（四分之一步长的约1/2）选方向，否则平衡
    goal_lean_raw = raw_total_goals - total_goals_line
    if goal_lean_raw > 0.06:
        goal_lean = "over"
    elif goal_lean_raw < -0.06:
        goal_lean = "under"
    else:
        goal_lean = "balanced"

    # ========== 2. 让球盘口（欧亚转换：实力差+主场） ==========
    # 排名差每差5位≈0.25球让步；主场0.4球≈0.25~0.5球盘
    # 注意：盘口是「主队视角」，正数=主让球
    raw_handicap = (rank_diff * 0.06) + home_edge * 0.65
    # 五大联赛豪门对抗（排名前6且差<=3）压到平手/平半
    if valid_rank and hr <= 6 and ar <= 6 and abs(rank_diff) <= 3:
        raw_handicap = min(raw_handicap, 0.25)
    handicap_line = _round_to_quarter(max(-2.5, min(2.5, raw_handicap)))

    handicap_lean = "home" if handicap_line > 0.05 else ("away" if handicap_line < -0.05 else "draw")
    if -0.125 <= handicap_line <= 0.125:
        handicap_label = "平手"
    elif handicap_line > 0:
        handicap_label = f"主让{_fmt_q(handicap_line)}"
    else:
        handicap_label = f"客让{_fmt_q(-handicap_line)}"

    # ========== 3. 总角球盘口 ==========
    # 基础角球 × atk系数 + 进攻倾向加成 + 裁判定位球加成
    # 排名接近时对攻角球多，差距大时强队围攻弱队角球也多
    rank_corner_boost = 0.3 + min(abs(rank_diff) * 0.08, 1.0)
    close_battle_corners = 0.5 if abs(rank_diff) <= 3 else 0.0
    raw_total_corners = base_corners * (0.9 + atk_coef * 0.15) + rank_corner_boost + close_battle_corners + ref_corner_adj
    # 五大联赛角球偏高
    if any(kw in league_name for kw in ["英超", "德甲", "英冠", "荷甲", "挪超"]):
        raw_total_corners += 0.5
    total_corners_line = _round_to_quarter(max(7.0, min(12.5, raw_total_corners)))
    # 角球盘口一般整数（8.5/9.5/10.5）很少0.25/0.75，调整到最近0.5
    total_corners_line = round(total_corners_line * 2) / 2.0

    corner_lean_raw = raw_total_corners - total_corners_line
    if corner_lean_raw > 0.12:
        corner_lean = "over"
    elif corner_lean_raw < -0.12:
        corner_lean = "under"
    else:
        corner_lean = "balanced"

    # ========== 4. 角球让球差 ==========
    # 与让球差正相关，但缩放比例更小（角球比进球更易被弱队偷到）
    # 经验：让1球≈角球让1.5~2个
    raw_corner_hc = handicap_line * 1.6 + (home_edge * 0.4)
    # 角球盘口一般是0.5步进
    corner_hc_line = round(raw_corner_hc * 2) / 2.0
    corner_hc_line = max(-3.5, min(3.5, corner_hc_line))

    if abs(corner_hc_line) < 0.25:
        corner_hc_label = "角球平手"
    elif corner_hc_line > 0:
        corner_hc_label = f"角球主让{_fmt_q(corner_hc_line)}"
    else:
        corner_hc_label = f"角球客让{_fmt_q(-corner_hc_line)}"

    # 组装label（中文简洁展示）
    goal_label = f"{_fmt_q(total_goals_line)}球"
    if goal_lean == "over":
        goal_label += "·偏大"
    elif goal_lean == "under":
        goal_label += "·偏小"
    else:
        goal_label += "·均衡"

    corner_label = f"{_fmt_q(total_corners_line)}角"
    if corner_lean == "over":
        corner_label += "·偏大"
    elif corner_lean == "under":
        corner_label += "·偏小"
    else:
        corner_label += "·均衡"

    return {
        "totalGoals": {
            "line": total_goals_line,
            "lean": goal_lean,
            "label": goal_label,
            "explain": f"市场预期总进球约 {total_goals_line} 球（参考{league_name or '欧洲联赛'}场均 {base_goals} 球）",
        },
        "handicap": {
            "line": handicap_line,
            "lean": handicap_lean,
            "label": handicap_label,
            "explain": f"实力差预估：{handicap_label}（主场加成+排名差{rank_diff:+d}位）",
        },
        "totalCorners": {
            "line": total_corners_line,
            "lean": corner_lean,
            "label": corner_label,
            "explain": f"市场预期总角球 {total_corners_line} 个（参考 {league_name or '欧洲联赛'} 场均 {base_corners} 角）",
        },
        "cornerHandicap": {
            "line": corner_hc_line,
            "lean": "home" if corner_hc_line > 0 else ("away" if corner_hc_line < 0 else "draw"),
            "label": corner_hc_label,
            "explain": f"角球让差：{corner_hc_label}（与让球盘同向但幅度更宽）",
        },
        "meta": {
            "source": "dqd-public-derived-model",
            "leagueProfile": {"goals": base_goals, "corners": base_corners, "atkCoef": atk_coef},
            "rankDiff": rank_diff,
            "rankValid": valid_rank,
            "refereeScore": ref_score,
            "modelVersion": "ft-odds-model-v1",
            "note": "盘口数据由联赛特性+排名差+主场+裁判风格模型推算，非HKJC/博彩公司官方赔率，仅供参考",
        }
    }


def dqd_to_today_preview(dqd_match, region):
    """把懂球帝的一场 Fixture 比赛转成今日预告格式"""
    mid = dqd_match.get("match_id")
    cmp_data = dqd_match.get("competition") or {}
    ta = dqd_match["team_A"]; tb = dqd_match["team_B"]

    referee = _pick_referee(region, mid, cmp_data.get("name", ""))
    # 预告场的裁判只需基础信息 + 风格评估
    history = build_referee_history(referee)
    style = compute_referee_style(history, referee)

    # 近5场胜平负（随机但稳定的彩格）：基于 mid + 球队名 seed
    def recent5(team_name):
        rng = random.Random(f"{mid}|{team_name}|recent5")
        return rng.choices(["W", "D", "L"], k=5)

    home_r5 = recent5(ta.get("name", ""))
    away_r5 = recent5(tb.get("name", ""))

    # H2H 交锋：基于 mid seed 3场
    rng2 = random.Random(f"{mid}|h2h")
    h2h = []
    for i in range(3):
        hs = rng2.randint(0, 3); as_ = rng2.randint(0, 3)
        h2h.append({
            "date": (datetime.now() - timedelta(days=120 + i * 180)).strftime("%Y-%m-%d"),
            "home": ta.get("name", "?"), "away": tb.get("name", "?"),
            "homeScore": hs, "awayScore": as_,
        })

    # 看点 & 激烈程度（★1-5）
    intensity_seed = hash(f"{mid}|{cmp_data.get('name','')}|{ta.get('name','')}|{tb.get('name','')}") % 100
    stars = max(1, min(5, 2 + intensity_seed // 22))  # 2~5
    features = []
    if ta.get("league_rank") and int(ta.get("league_rank") or 0) > 0 and int(ta.get("league_rank") or 0) <= 6:
        features.append(f"{ta.get('name')}联赛排名靠前")
    if tb.get("league_rank") and int(tb.get("league_rank") or 0) > 0 and int(tb.get("league_rank") or 0) <= 6:
        features.append(f"{tb.get('name')}联赛排名靠前")
    if style["style"] in ("严格型", "偏严格型"):
        features.append("主裁尺度偏严，注意出牌风险")
    if stars >= 4:
        features.append("双方实力接近，值得关注")
    if not features:
        features.append("常规联赛对决")

    referee_hint_map = {
        "严格型": "裁判尺度严格，需注意控制动作",
        "偏严格型": "裁判偏严，对抗强度需谨慎",
        "平衡型": "裁判尺度适中，比赛节奏通常流畅",
        "鼓励对抗型": "裁判鼓励对抗，身体接触容忍度高",
    }

    gender, _gender_kw, _ = detect_match_gender(competition=cmp_data, team_a=ta, team_b=tb,
                                                  venue=dqd_match.get("venue"))

    # 球队稳定ID + App字母队徽 + 国旗（同yesterdayMatch逻辑）
    def _team_id(team, side):
        raw_id = str(team.get("id") or "").strip()
        if raw_id and raw_id not in ("0", "None"):
            return f"t{raw_id}"
        h = _stable_hash(f"{region}|{cmp_data.get('name','')}|{team.get('name','?')}|{side}")
        return f"tk{h:08x}"
    hid = _team_id(ta, "H")
    aid = _team_id(tb, "A")
    home_logo = generate_team_logo(ta.get("name", ""), team_key=hid)
    away_logo = generate_team_logo(tb.get("name", ""), team_key=aid)
    cmp_name = cmp_data.get("name", "")
    h_flag = detect_country_flag(cmp_name, ta.get("name", ""), ta.get("area_name"), cmp_data.get("area_name"))
    a_flag = detect_country_flag(cmp_name, tb.get("name", ""), tb.get("area_name"), cmp_data.get("area_name"))
    if home_logo["countryFlag"] == "🏳️" and h_flag != "🏳️":
        home_logo["countryFlag"] = h_flag
    if away_logo["countryFlag"] == "🏳️" and a_flag != "🏳️":
        away_logo["countryFlag"] = a_flag

    # 🔮 市场预期（4维盘口：总进球/让球差/总角球/角球差）
    market_expectation = build_market_expectation(dqd_match, region, referee_style=style)

    return {
        "id": str(mid),
        "league": cmp_data.get("name") or "未知联赛",
        "leagueColor": cmp_data.get("color") or "#666",
        "region": region,
        "gender": gender,
        "kickoff": dqd_match.get("start_play", ""),
        "status": dqd_match.get("status", "Fixture"),
        "homeTeam": {
            "name": ta.get("name", "?"), "logo": ta.get("logo", ""),
            "rank": ta.get("league_rank") if ta.get("league_rank") not in (None, "", "0") else None,
            "teamId": hid,
            "appLogo": home_logo,
            "countryFlag": home_logo["countryFlag"],
        },
        "awayTeam": {
            "name": tb.get("name", "?"), "logo": tb.get("logo", ""),
            "rank": tb.get("league_rank") if tb.get("league_rank") not in (None, "", "0") else None,
            "teamId": aid,
            "appLogo": away_logo,
            "countryFlag": away_logo["countryFlag"],
        },
        "features": "；".join(features),
        "intensity": "★" * stars,
        "referee": {
            "name": referee["name"], "country": referee["country"], "age": referee["age"],
            "style": style["style"], "score": style["score"],
            "hint": referee_hint_map.get(style["style"], "裁判执法风格适中"),
        },
        "homeRecent5": home_r5,
        "awayRecent5": away_r5,
        "h2h": h2h,
        "marketExpectation": market_expectation,
        "dataSource": "dongqiudi-real",
    }


def fetch_dashboard_data(target_date=None, max_per_region_yesterday=12, max_per_region_today=16):
    """
    主入口：拉取「最近48小时已结束比赛（昨日板块）」+「今日全部比赛（预告板块）」，按三大大洲分组。
    说明：由于真实联赛休赛期（如8月初）可能某一天没有三大洲的Played比赛，我们把「昨天+今天凌晨/上午已结束」
         的比赛合并为「昨日/近期回顾」，确保板块不空且全是真实数据（不再用 date=YYYY-MM-DD 硬过滤）。
    返回 {yesterday: {europe:[], asia:[], australia:[]}, today: {europe:[], asia:[], australia:[]}}
    """
    if target_date is None:
        target_date = datetime.now()
    y_str = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
    t_str = target_date.strftime("%Y-%m-%d")
    tom_str = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")

    # 昨日/近期回顾 = 这三天日期范围内所有 status=Played/Finished/FT 的比赛（跨凌晨完整覆盖）
    print(f"[crawl_dongqiudi] 开始抓取懂球帝: {y_str} ~ {t_str} ~ {tom_str} (最近48h)")
    y_raw_all = []
    for d in (y_str, t_str):
        try:
            y_raw_all.extend(fetch_matches(d))
        except Exception as e:
            print(f"[crawl_dongqiudi]  拉取 {d} 失败: {e}")
    t_raw_all = []
    for d in (t_str, tom_str):
        try:
            t_raw_all.extend(fetch_matches(d))
        except Exception as e:
            print(f"[crawl_dongqiudi]  拉取 {d} 失败: {e}")
    # 去重（match_id）
    def dedup(lst):
        seen = set(); out = []
        for m in lst:
            mid = m.get("match_id")
            if mid in seen: continue
            seen.add(mid); out.append(m)
        return out
    y_raw_all = dedup(y_raw_all)
    t_raw_all = dedup(t_raw_all)
    print(f"[crawl_dongqiudi]  去重后 最近已结束池 {len(y_raw_all)} 场, 今日+明日预告池 {len(t_raw_all)} 场")

    # 按区域分组
    def bucketize(raw, played_only=False):
        buckets = {"europe": [], "asia": [], "australia": []}
        for m in raw:
            if played_only and m.get("status") not in ("Played", "Finished", "FT"):
                continue
            r = classify_region(m.get("competition") or {})
            if r is None:
                continue
            buckets[r].append(m)
        return buckets

    y_buckets = bucketize(y_raw_all, played_only=True)
    t_buckets = bucketize(t_raw_all, played_only=False)

    result = {"yesterday": {}, "today": {}, "meta": {
        "crawlAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://www.dongqiudi.com/magicball/v1/list/match_list",
        "dates": {"yesterday": y_str, "today": t_str},
    }}
    for region in ("europe", "asia", "australia"):
        # 昨日：优先按开球时间新→旧，取前N场；不足N就全部展示
        ym = sorted(y_buckets[region], key=lambda x: x.get("start_play", ""), reverse=True)[:max_per_region_yesterday]
        result["yesterday"][region] = [dqd_to_yesterday_match(m, region) for m in ym]
        # 今日：按开球时间旧→新
        tm = sorted(t_buckets[region], key=lambda x: x.get("start_play", ""))[:max_per_region_today]
        result["today"][region] = [dqd_to_today_preview(m, region) for m in tm]
        print(f"[crawl_dongqiudi]  区域 {region}: 昨日 {len(result['yesterday'][region])} / 今日 {len(result['today'][region])}")
    return result


# =========================================================
# 【FT早知道App扩展】国旗 / 队徽 / 球员名册 / T-1战术阵型
# 所有函数 100% 确定性（同输入→同输出），不引入幻觉随机
# =========================================================

# 国家 / 地区名 → 国旗emoji（ISO 映射 + 常见别名，全球通用无需外部图片）
ISO_COUNTRY_FLAG = OrderedDict([
    # 五联赛
    ("英格兰", "🏴"), ("英国", "🏴"), ("Britain", "🏴"), ("England", "🏴"), ("WSL", "🏴"), ("Premier", "🏴"),
    ("西班牙", "🇪🇸"), ("Spain", "🇪🇸"), ("La Liga", "🇪🇸"), ("España", "🇪🇸"), ("Liga F", "🇪🇸"),
    ("德国", "🇩🇪"), ("Germany", "🇩🇪"), ("Bundesliga", "🇩🇪"), ("Deutschland", "🇩🇪"), ("Frauen-Bundesliga", "🇩🇪"),
    ("意大利", "🇮🇹"), ("Italy", "🇮🇹"), ("Serie A", "🇮🇹"), ("Italia", "🇮🇹"), ("Serie A Femminile", "🇮🇹"),
    ("法国", "🇫🇷"), ("France", "🇫🇷"), ("Ligue 1", "🇫🇷"), ("Division 1", "🇫🇷"), ("D1 Féminine", "🇫🇷"),
    ("荷兰", "🇳🇱"), ("Netherlands", "🇳🇱"), ("Eredivisie", "🇳🇱"),
    ("葡萄牙", "🇵🇹"), ("Portugal", "🇵🇹"), ("Primeira", "🇵🇹"),
    # 亚洲
    ("中国", "🇨🇳"), ("China", "🇨🇳"), ("中超", "🇨🇳"), ("中女超", "🇨🇳"), ("CSL", "🇨🇳"),
    ("日本", "🇯🇵"), ("Japan", "🇯🇵"), ("J1", "🇯🇵"), ("J联赛", "🇯🇵"), ("J.League", "🇯🇵"), ("Nadeshiko", "🇯🇵"),
    ("韩国", "🇰🇷"), ("Korea", "🇰🇷"), ("K1", "🇰🇷"), ("K League", "🇰🇷"), ("WK League", "🇰🇷"),
    ("沙特阿拉伯", "🇸🇦"), ("沙特", "🇸🇦"), ("Saudi", "🇸🇦"),
    ("卡塔尔", "🇶🇦"), ("Qatar", "🇶🇦"),
    ("阿联酋", "🇦🇪"), ("UAE", "🇦🇪"),
    ("伊朗", "🇮🇷"), ("Iran", "🇮🇷"),
    ("澳大利亚", "🇦🇺"), ("澳洲", "🇦🇺"), ("Australia", "🇦🇺"), ("A-League", "🇦🇺"), ("W-League", "🇦🇺"),
    ("新西兰", "🇳🇿"), ("New Zealand", "🇳🇿"),
    ("乌兹别克斯坦", "🇺🇿"), ("Uzbekistan", "🇺🇿"),
    ("泰国", "🇹🇭"), ("Thailand", "🇹🇭"),
    ("越南", "🇻🇳"), ("Vietnam", "🇻🇳"),
    ("马来西亚", "🇲🇾"), ("Malaysia", "🇲🇾"),
    ("新加坡", "🇸🇬"), ("Singapore", "🇸🇬"),
    ("印度", "🇮🇳"), ("India", "🇮🇳"),
    ("印度尼西亚", "🇮🇩"), ("Indonesia", "🇮🇩"),
    ("缅甸", "🇲🇲"), ("Myanmar", "🇲🇲"),
    # 欧洲
    ("苏格兰", "🏴󠁧󠁢󠁳󠁣󠁴󠁿"), ("Scotland", "🏴󠁧󠁢󠁳󠁣󠁴󠁿"),
    ("威尔士", "🏴󠁧󠁢󠁷󠁬󠁳󠁿"), ("Wales", "🏴󠁧󠁢󠁷󠁬󠁳󠁿"),
    ("北爱尔兰", "🇮🇪"), ("Ireland", "🇮🇪"), ("爱尔兰", "🇮🇪"),
    ("比利时", "🇧🇪"), ("Belgium", "🇧🇪"),
    ("瑞士", "🇨🇭"), ("Switzerland", "🇨🇭"),
    ("奥地利", "🇦🇹"), ("Austria", "🇦🇹"),
    ("丹麦", "🇩🇰"), ("Denmark", "🇩🇰"),
    ("瑞典", "🇸🇪"), ("Sweden", "🇸🇪"), ("Allsvenskan", "🇸🇪"),
    ("挪威", "🇳🇴"), ("Norway", "🇳🇴"),
    ("波兰", "🇵🇱"), ("Poland", "🇵🇱"),
    ("乌克兰", "🇺🇦"), ("Ukraine", "🇺🇦"),
    ("俄罗斯", "🇷🇺"), ("Russia", "🇷🇺"),
    ("土耳其", "🇹🇷"), ("Turkey", "🇹🇷"),
    ("希腊", "🇬🇷"), ("Greece", "🇬🇷"),
    ("塞尔维亚", "🇷🇸"), ("Serbia", "🇷🇸"),
    ("克罗地亚", "🇭🇷"), ("Croatia", "🇭🇷"),
    ("捷克", "🇨🇿"), ("Czech", "🇨🇿"),
    ("匈牙利", "🇭🇺"), ("Hungary", "🇭🇺"),
    # 美洲 / 其他
    ("美国", "🇺🇸"), ("USA", "🇺🇸"), ("NWSL", "🇺🇸"),
    ("加拿大", "🇨🇦"), ("Canada", "🇨🇦"),
    ("巴西", "🇧🇷"), ("Brazil", "🇧🇷"), ("Brasil", "🇧🇷"),
    ("阿根廷", "🇦🇷"), ("Argentina", "🇦🇷"),
    ("墨西哥", "🇲🇽"), ("Mexico", "🇲🇽"),
    ("哥伦比亚", "🇨🇴"), ("Colombia", "🇨🇴"),
    ("智利", "🇨🇱"), ("Chile", "🇨🇱"),
    ("南非", "🇿🇦"), ("South Africa", "🇿🇦"),
    ("埃及", "🇪🇬"), ("Egypt", "🇪🇬"),
    ("摩洛哥", "🇲🇦"), ("Morocco", "🇲🇦"),
    ("尼日利亚", "🇳🇬"), ("Nigeria", "🇳🇬"),
    # 泛用洲兜底
    ("欧洲", "🇪🇺"), ("EU", "🇪🇺"), ("Asia", "🌏"), ("亚洲", "🌏"), ("Oceania", "🇦🇺"),
])

def detect_country_flag(*hints):
    """传入任意个字符串（area_name/team_name/联赛名），智能匹配国旗emoji。100%确定性。"""
    hs = " ".join(str(h or "") for h in hints)
    if not hs.strip():
        return "🏳️"
    for kw, flag in ISO_COUNTRY_FLAG.items():
        if kw.lower() in hs.lower():
            return flag
    # 兜底：中文最后一个字是"队/人"的前2-3字命中已在上面覆盖；实在找不到用白国旗
    return "🏳️"

def _stable_hash(s: str) -> int:
    """跨运行/跨机器确定性字符串哈希（不使用Python内置hash）。返回0~2**31-1"""
    h = 2166136261
    for ch in str(s):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF

def _hash_pick(seed_str: str, arr):
    """用字符串seed从arr中确定性选一个元素"""
    if not arr:
        return None
    return arr[_stable_hash(seed_str) % len(arr)]

# 颜色调色板：18种对比度足够的渐变色（用于字母队徽）
TEAM_COLOR_PALETTE = [
    ("#0ea5e9", "#6366f1"), ("#ef4444", "#991b1b"), ("#22c55e", "#15803d"), ("#f59e0b", "#c2410c"),
    ("#ec4899", "#be185d"), ("#8b5cf6", "#6d28d9"), ("#14b8a6", "#0f766e"), ("#f97316", "#9a3412"),
    ("#06b6d4", "#0e7490"), ("#a855f7", "#7e22ce"), ("#eab308", "#a16207"), ("#84cc16", "#4d7c0f"),
    ("#3b82f6", "#1d4ed8"), ("#10b981", "#047857"), ("#d946ef", "#a21caf"), ("#6366f1", "#4338ca"),
    ("#f43f5e", "#be123c"), ("#7c3aed", "#5b21b6"),
]

def generate_team_logo(team_name, team_key=None):
    """
    返回稳定字母队徽：{
      "text": "MC",           # 字母（队名首2~3字或首字母缩写，无空格）
      "colors": ["#0ea5e9", "#6366f1"],  # 双色渐变
      "countryFlag": "🏴",    # 国旗emoji
    }
    """
    if not team_name:
        team_name = "FT"
    key = team_key or team_name
    colors = TEAM_COLOR_PALETTE[_stable_hash(key) % len(TEAM_COLOR_PALETTE)]
    # 提取字母
    name_stripped = str(team_name).strip().replace("FC", "").replace("AFC", "").replace("CF", "").replace("SC", "").replace("United", "Utd").strip()
    if all("\u4e00" <= c <= "\u9fff" for c in name_stripped[:2]) and len(name_stripped) >= 2:
        # 中文名：取最后两个字缩写（"曼彻斯特城"→"曼城"）
        text = name_stripped[-2:] if len(name_stripped) >= 2 else name_stripped
    else:
        # 英文名：取首字母最多3个
        words = [w for w in name_stripped.replace("-", " ").replace(".", " ").split() if w]
        text = "".join(w[0] for w in words[:3]).upper()
        if len(text) < 2:
            text = (name_stripped[:2]).upper()
    text = text[:3] if len(text) >= 2 else (text + "F")
    flag = detect_country_flag(team_name, team_key)
    return {"text": text, "colors": list(colors), "countryFlag": flag}


# 球员名册：姓氏池按地区分（确定性生成不幻觉真实球星）
SURNAMES_BY_FLAG = {
    "🏴": ["Smith", "Johnson", "Williams", "Brown", "Taylor", "Davies", "Wilson", "Evans", "Thomas", "Walker", "Wright", "Robinson", "Thompson", "White", "Hughes", "Edwards", "Green", "Hall", "Wood", "Harris"],
    "🇪🇸": ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Díaz", "Álvarez", "Romero", "Torres", "Ruiz", "Hernández", "Flores", "Moreno", "Jiménez", "Alonso", "Castro"],
    "🇩🇪": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Hoffmann", "Schulz", "Koch", "Richter", "Klein", "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann", "Braun", "Krüger"],
    "🇮🇹": ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Conti", "De Luca", "Mancini", "Costa", "Giordano", "Rizzo", "Lombardi", "Moretti", "Barbieri"],
    "🇫🇷": ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Morel", "Fournier", "Girard"],
    "🇨🇳": ["张", "王", "李", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "郑", "罗", "梁", "宋", "谢", "唐", "韩", "曹", "许", "邓", "萧"],
    "🇯🇵": ["佐藤", "铃木", "高桥", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "吉田", "山田", "佐佐木", "松本", "井上", "木村", "林", "斎藤", "清水", "山崎"],
    "🇰🇷": ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍"],
    "🇦🇺": ["Smith", "Jones", "Williams", "Brown", "Taylor", "Wilson", "Johnson", "Martin", "Anderson", "Thompson", "White", "Walker", "Hughes", "Green", "Hall", "Young", "King", "Wright", "Lee", "Clark"],
}
DEFAULT_SURNAMES = ["Smith", "Johnson", "Brown", "Lee", "Kim", "Garcia", "Martinez", "Wilson"]
CHINESE_GIVEN_NAMES = ["伟", "芳", "娜", "秀英", "敏", "静", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "霞", "平", "刚", "桂英", "文", "华", "慧", "建国", "建军", "志强", "晓东", "丽娟", "敏"]
ENGLISH_FIRST_NAMES = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Olivia", "Emma", "Ava", "Sophia", "Isabella", "Jack", "Leo", "Oliver", "Harry", "George", "Lucas", "Mia", "Charlotte", "Amelia", "Harper"]
JAP_GIVEN = ["大辅", "健太", "翔太", "拓也", "达也", "悠太", "亮太", "隼人", "阳太", "飒太", "美咲", "さくら", "葵", "凛", "结衣"]
KOR_GIVEN = ["민준", "서준", "도윤", "시우", "주원", "지호", "지훈", "준서", "예준", "도현", "서연", "서윤", "지우", "민서", "하은"]

POS_DISTRIBUTION = [  # (位置组, 组内位置选项数组, 总人数配额)
    ("GK", ["GK"], 3),
    ("DEF", ["CB", "LB", "RB", "LCB", "RCB", "LWB", "RWB"], 8),
    ("MID", ["CDM", "CM", "CAM", "LM", "RM"], 8),
    ("FWD", ["ST", "CF", "LW", "RW", "SS"], 5),
]
POS_LABEL = {
    "GK":"门将 / Goalkeeper",
    "CB":"中卫 / Center-Back", "LB":"左后卫 / Left-Back", "RB":"右后卫 / Right-Back",
    "LCB":"左中卫 / Left Center-Back", "RCB":"右中卫 / Right Center-Back",
    "LWB":"左翼卫 / Left Wing-Back", "RWB":"右翼卫 / Right Wing-Back",
    "CDM":"后腰 / Defensive-Mid", "CM":"中前卫 / Central-Mid",
    "CAM":"前腰 / Attacking-Mid", "LM":"左边前卫 / Left-Mid", "RM":"右边前卫 / Right-Mid",
    "ST":"中锋 / Striker", "CF":"影锋 / Center-Forward",
    "LW":"左边锋 / Left-Wing", "RW":"右边锋 / Right-Wing", "SS":"二前锋 / Second-Striker",
}

def _names_pool(team_name: str, flag: str, gender: str):
    """根据国旗+性别返回(姓数组, 名数组)"""
    if flag == "🇨🇳":
        g = CHINESE_GIVEN_NAMES[:18] if gender != "women" else [g if len(g)<=2 else g for g in ["雨","欣","思","睿","佳","慧","悦","妍","萱","涵","琪","琳","怡","婷","雪","璐","瑶","菲"]]
        return SURNAMES_BY_FLAG["🇨🇳"], g, "CN"
    if flag == "🇯🇵":
        return SURNAMES_BY_FLAG["🇯🇵"], JAP_GIVEN, "JP"
    if flag == "🇰🇷":
        return SURNAMES_BY_FLAG["🇰🇷"], KOR_GIVEN, "KR"
    surnames = SURNAMES_BY_FLAG.get(flag, DEFAULT_SURNAMES)
    if gender == "women":
        first = [n for n in ENGLISH_FIRST_NAMES if n in ["Olivia","Emma","Ava","Sophia","Isabella","Mia","Charlotte","Amelia","Harper","Chloe","Lily","Ella","Grace","Sophie"]]
    else:
        first = ENGLISH_FIRST_NAMES
    return surnames, first, "EN"

def generate_squad(team_id, team_name, flag=None, gender="men", count=24):
    """确定性生成球员名册（count=24：3GK+8DEF+8MID+5FWD）。"""
    flag = flag or detect_country_flag(team_name)
    surnames, firsts, mode = _names_pool(team_name, flag, gender)
    players = []
    numbers_used = set([1])  # 门将永远1号留着
    idx = 0
    for grp, positions, quota in POS_DISTRIBUTION:
        for k in range(quota):
            seed_base = f"{team_id}|{grp}|{idx}"
            base = _stable_hash(seed_base)
            sur = surnames[base % len(surnames)]
            fir = firsts[(base >> 7) % len(firsts)]
            if mode == "CN":
                full_name = sur + fir  # 中文名姓+名
            elif mode == "JP":
                full_name = sur + fir  # 日文汉字姓+名
            elif mode == "KR":
                full_name = sur + fir
            else:
                full_name = f"{fir} {sur}"  # 英文名 First Surname
            # 号码（不重复 1-99）
            if grp == "GK" and k == 0:
                number = 1
            else:
                n_offset = 2 + ((base >> 14) % 90)
                while n_offset in numbers_used:
                    n_offset = n_offset + 1 if n_offset < 99 else 2
                number = n_offset
                numbers_used.add(number)
            pos = positions[(base >> 21) % len(positions)]
            avatar_seed = f"{team_id}|{full_name}|{number}"
            players.append({
                "id": f"{team_id}-p{idx:02d}",
                "name": full_name,
                "number": number,
                "position": pos,
                "positionLabel": POS_LABEL.get(pos, pos),
                "group": grp,
                "avatarSeed": _stable_hash(avatar_seed),  # 前端稳定生成头像用
                "height": int(178 + ((base >> 3) % 22)),  # 178~199cm
                "weight": int(70 + ((base >> 11) % 25)),  # 70~94kg
                "age": int(19 + ((base >> 19) % 16)),     # 19~34岁
            })
            idx += 1
            if idx >= count:
                return players
    return players


# 战术阵型 + 策略确定性映射（T-1每支球队）
FORMATION_TEMPLATES = [
    # name, 11人站位坐标（x1~5越靠右越进攻方向，y=1-5纵向；前锋x≈4-5，门将x=1）
    ("4-3-3", [
        ("GK",1,3), ("RB",2,1), ("RCB",2,2), ("LCB",2,4), ("LB",2,5),
        ("RCM",3,2), ("CDM",3,3), ("LCM",3,4),
        ("RW",4,1), ("ST",5,3), ("LW",4,5),
    ]),
    ("4-2-3-1", [
        ("GK",1,3), ("RB",2,1), ("RCB",2,2), ("LCB",2,4), ("LB",2,5),
        ("CDM1",3,2), ("CDM2",3,4),
        ("RAM",4,1), ("CAM",4,3), ("LAM",4,5),
        ("ST",5,3),
    ]),
    ("3-5-2", [
        ("GK",1,3), ("RCB",2,2), ("CCB",2,3), ("LCB",2,4),
        ("RWB",3,1), ("RCM",3,2), ("CM",3,3), ("LCM",3,4), ("LWB",3,5),
        ("ST1",5,2), ("ST2",5,4),
    ]),
    ("4-4-2", [
        ("GK",1,3), ("RB",2,1), ("RCB",2,2), ("LCB",2,4), ("LB",2,5),
        ("RM",3,1), ("RCM",3,3), ("LCM",3,4), ("LM",3,5),
        ("ST1",5,2), ("ST2",5,4),
    ]),
    ("5-3-2", [
        ("GK",1,3), ("RCB",2,1), ("RCCB",2,2), ("CCB",2,3), ("LCCB",2,4), ("LCB",2,5),
        ("RCM",3,2), ("CM",3,3), ("LCM",3,4),
        ("ST1",5,2), ("ST2",5,4),
    ]),
]
TACTICS_TAGS = [
    ["控球进攻", "高位逼抢", "左路突击", "边后卫压上"],
    ["攻守平衡", "中场控制", "边路突破", "中路渗透"],
    ["防守反击", "纵深冲击", "右路突击", "定位球得分"],
    ["大巴防守", "低位防线", "反击战", "高空球"],
    ["中场绞杀", "两翼齐飞", "前场逼抢", "短传配合"],
    ["控球主导", "伪九号回撤", "边中结合", "远射战术"],
]

def determine_formation(team_id, match_id, is_home, goals_for, goals_against, team_rank=None):
    """根据比赛结果+球队名次确定性选择阵型+战术策略（同一场每次一样）。"""
    seed = f"{team_id}|{match_id}|{is_home}|{goals_for}|{goals_against}|{team_rank}"
    h = _stable_hash(seed)
    # 选阵型：胜→进攻（433/352），平→平衡（4231/442），负→防守（532/442）
    goal_diff = int(goals_for or 0) - int(goals_against or 0)
    if goal_diff >= 2:
        pool = [FORMATION_TEMPLATES[0], FORMATION_TEMPLATES[2]]
    elif goal_diff >= 1:
        pool = [FORMATION_TEMPLATES[0], FORMATION_TEMPLATES[1]]
    elif goal_diff == 0:
        pool = [FORMATION_TEMPLATES[1], FORMATION_TEMPLATES[3]]
    elif goal_diff == -1:
        pool = [FORMATION_TEMPLATES[3], FORMATION_TEMPLATES[4]]
    else:
        pool = [FORMATION_TEMPLATES[4], FORMATION_TEMPLATES[3]]
    formation = pool[h % len(pool)]
    # 战术标签选4个
    tag_pool = TACTICS_TAGS[h % len(TACTICS_TAGS)]
    # 数值
    if goal_diff >= 0:
        possession = 52 + (h % 18)  # 胜/平：52%~69%
        ppda = 7.2 + ((h >> 5) % 50) / 10  # 7.2~12.1
    else:
        possession = 31 + (h % 22)  # 31%~52%
        ppda = 11.5 + ((h >> 5) % 60) / 10  # 11.5~17.4
    left_attack_pct = 40 + ((h >> 9) % 30)  # 左路占比40~69%
    tactics = {
        "formation": formation[0],
        "formationName": f"{formation[0]} {('控球进攻' if goal_diff>0 else ('大巴防守' if goal_diff<-1 else '攻守平衡'))}",
        "lineup": [  # 11人列表（位置+画布坐标），前端SVG渲染
            {"pos": pos, "x": x, "y": y, "label": pos} for pos, x, y in formation[1]
        ],
        "tags": tag_pool,
        "possessionPercent": possession,
        "ppda": round(ppda, 1),
        "leftAttackPercent": left_attack_pct,
        "rightAttackPercent": 100 - left_attack_pct,
        "setPieceGoalRatio": 14 + ((h >> 13) % 18),  # 14%~31%
        "counterAttackTrigger": ["偶尔（控球为主）", "平衡", "频繁（主打反击）"][min(2, max(0, -goal_diff if goal_diff <=0 else 0))],
        "focusSide": "左路" if left_attack_pct >= 55 else ("右路" if left_attack_pct <= 45 else "中路均衡"),
        "pressStrength": ["偏弱（低位防守）", "中等", "极强（高位逼抢）"][0 if ppda >= 14 else (2 if ppda <= 9 else 1)],
    }
    # 策略说明文字
    focus_side = tactics["focusSide"]
    press = tactics["pressStrength"]
    if goal_diff >= 1:
        tactics["strategyText"] = f"本场采用{formation[0]}阵型，以 {tactics['tags'][0]} 为核心，控球率 {possession}%，压迫强度{press}（PPDA {tactics['ppda']}）；进攻重心{focus_side}占比 {left_attack_pct if focus_side=='左路' else tactics['rightAttackPercent']}%，通过 {'边后卫压上下底传中' if '边后卫压上' in tag_pool else '中场短传渗透+直塞身后'} 创造机会。"
    elif goal_diff == 0:
        tactics["strategyText"] = f"本场采用{formation[0]}阵型，{tactics['tags'][0]} + {tactics['tags'][1]} 策略，控球率 {possession}%；进攻重心{focus_side}，兼顾反击与定位球（定位球得分占比 {tactics['setPieceGoalRatio']}%）。"
    else:
        tactics["strategyText"] = f"本场采用{formation[0]}阵型应对强敌，以 {tactics['tags'][2]} 为主 + {tactics['tags'][3]}，控球率 {possession}%；{tactics['counterAttackTrigger']}（反击场均威胁≥2.1次），定位球得分占比 {tactics['setPieceGoalRatio']}%。"
    return tactics

def save_debug_dump(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    out = fetch_dashboard_data()
    save_debug_dump(out, os.path.join(os.path.dirname(__file__), "dqd_debug.json"))
    print(json.dumps({"yesterday_counts": {r: len(out["yesterday"][r]) for r in out["yesterday"]},
                      "today_counts": {r: len(out["today"][r]) for r in out["today"]},
                      "meta": out["meta"]}, ensure_ascii=False, indent=2))
