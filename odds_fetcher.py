"""
odds_fetcher.py — 从 football-data.co.uk 抓取真实博彩赔率
=========================================================
数据源：https://www.football-data.co.uk
免费CSV格式，覆盖12家主流博彩公司（Bet365/Pinnacle/Betfair/Bwin/Ladbrokes等）的
亚盘让球(AH)、大小球(O/U)、胜平负(1X2)，以及已完赛场次的实际比分（FTHG/FTAG）。
"""
from __future__ import annotations
import csv
import io
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, date
from difflib import SequenceMatcher
from typing import Optional, Dict, List, Any, Tuple


# ===========================================================================
# 博彩公司配置
# ===========================================================================
BOOKMAKERS = [
    {"key": "B365",   "name": "Bet365",       "region": "🇬🇧", "rank": 1},
    {"key": "PS",     "name": "Pinnacle",     "region": "🇨🇼", "rank": 2},
    {"key": "BFE",    "name": "Betfair Ex",   "region": "🇬🇧", "rank": 3},
    {"key": "BFD",    "name": "Betfair SB",   "region": "🇬🇧", "rank": 4},
    {"key": "BW",     "name": "Bwin",         "region": "🇪🇺", "rank": 5},
    {"key": "VC",     "name": "BetVictor",    "region": "🇬🇧", "rank": 6},
    {"key": "WH",     "name": "William Hill", "region": "🇬🇧", "rank": 7},
    {"key": "LB",     "name": "Ladbrokes",    "region": "🇬🇧", "rank": 8},
    {"key": "Avg",    "name": "市场均值",     "region": "📊", "rank": 9},
    {"key": "Max",    "name": "市场最高",     "region": "📊", "rank": 10},
]

DIV_MAP = {
    "E0":  {"cn": "英超",        "en": "Premier League"},
    "E1":  {"cn": "英冠",        "en": "Championship"},
    "E2":  {"cn": "英甲",        "en": "League One"},
    "E3":  {"cn": "英乙",        "en": "League Two"},
    "EC":  {"cn": "英非联",      "en": "Conference"},
    "D1":  {"cn": "德甲",        "en": "Bundesliga"},
    "D2":  {"cn": "德乙",        "en": "2. Bundesliga"},
    "SP1": {"cn": "西甲",        "en": "La Liga"},
    "SP2": {"cn": "西乙",        "en": "Segunda Division"},
    "I1":  {"cn": "意甲",        "en": "Serie A"},
    "I2":  {"cn": "意乙",        "en": "Serie B"},
    "F1":  {"cn": "法甲",        "en": "Ligue 1"},
    "F2":  {"cn": "法乙",        "en": "Ligue 2"},
    "N1":  {"cn": "荷甲",        "en": "Eredivisie"},
    "B1":  {"cn": "比甲",        "en": "Pro League"},
    "P1":  {"cn": "葡超",        "en": "Primeira Liga"},
    "T1":  {"cn": "土超",        "en": "Super Lig"},
    "G1":  {"cn": "希超",        "en": "Super League Greece"},
    "S1":  {"cn": "瑞士超",      "en": "Super League"},
    "SC0": {"cn": "苏超",        "en": "Scottish Premiership"},
    "SC1": {"cn": "苏冠",        "en": "Scottish Championship"},
    "A1":  {"cn": "奥超",        "en": "Austrian Bundesliga"},
    "M1":  {"cn": "俄超",        "en": "Russian Premier League"},
    "R1":  {"cn": "俄超",        "en": "Russian Premier League"},
}


# ===========================================================================
# 常用中英球队名映射（en → cn）
# ===========================================================================
EN_TO_CN_TEAMS: Dict[str, str] = {
    # 英超
    "Arsenal": "阿森纳", "Aston Villa": "阿斯顿维拉", "Bournemouth": "伯恩茅斯",
    "Brentford": "布伦特福德", "Brighton": "布莱顿", "Brighton & Hove Albion": "布莱顿",
    "Burnley": "伯恩利", "Chelsea": "切尔西", "Crystal Palace": "水晶宫", "Everton": "埃弗顿",
    "Fulham": "富勒姆", "Ipswich": "伊普斯维奇", "Ipswich Town": "伊普斯维奇",
    "Leicester": "莱斯特城", "Leicester City": "莱斯特城",
    "Liverpool": "利物浦", "Manchester City": "曼城", "Man City": "曼城",
    "Manchester United": "曼联", "Man United": "曼联",
    "Newcastle": "纽卡斯尔", "Newcastle United": "纽卡斯尔",
    "Nott'm Forest": "诺丁汉森林", "Nottingham Forest": "诺丁汉森林",
    "Southampton": "南安普顿", "Tottenham": "热刺", "Tottenham Hotspur": "热刺",
    "West Ham": "西汉姆", "West Ham United": "西汉姆",
    "Wolves": "狼队", "Wolverhampton Wanderers": "狼队",
    "Leeds": "利兹联", "Leeds United": "利兹联",
    "Sunderland": "桑德兰", "Watford": "沃特福德",
    "Norwich": "诺维奇", "Norwich City": "诺维奇",
    "West Brom": "西布朗", "West Bromwich Albion": "西布朗",
    "Sheffield Utd": "谢菲联", "Sheffield United": "谢菲联",
    "Luton": "卢顿", "Luton Town": "卢顿",
    "Bolton": "博尔顿", "Bolton Wanderers": "博尔顿",
    "Middlesbrough": "米德尔斯堡", "Stoke": "斯托克城", "Stoke City": "斯托克城",
    "Swansea": "斯旺西", "Swansea City": "斯旺西",
    "Cardiff": "加的夫城", "Cardiff City": "加的夫城",
    "Huddersfield": "哈德斯菲尔德", "Derby": "德比郡", "Derby County": "德比郡",
    "Preston": "普雷斯顿", "Preston North End": "普雷斯顿",
    "Blackburn": "布莱克本", "Blackburn Rovers": "布莱克本",
    "QPR": "QPR", "Birmingham": "伯明翰", "Birmingham City": "伯明翰",
    "Hull": "赫尔城", "Hull City": "赫尔城",
    "Charlton": "查尔顿", "Charlton Athletic": "查尔顿",
    "Millwall": "米尔沃尔", "Coventry": "考文垂", "Coventry City": "考文垂",
    "Rotherham": "罗瑟汉姆", "Barnsley": "巴恩斯利", "Blackpool": "布莱克浦",
    "Bristol City": "布里斯托尔城", "Plymouth": "普利茅斯", "Plymouth Argyle": "普利茅斯",
    "Wrexham": "雷克瑟姆", "Portsmouth": "朴茨茅斯", "Oxford United": "牛津联",
    "Cambridge": "剑桥联", "Cambridge United": "剑桥联", "Reading": "雷丁",
    # 德甲
    "Bayern Munich": "拜仁慕尼黑", "Bayern München": "拜仁慕尼黑",
    "Dortmund": "多特蒙德", "Borussia Dortmund": "多特蒙德",
    "RB Leipzig": "RB莱比锡", "Leipzig": "RB莱比锡",
    "Bayer Leverkusen": "勒沃库森", "Leverkusen": "勒沃库森",
    "M'gladbach": "门兴", "Borussia Mönchengladbach": "门兴格拉德巴赫",
    "Wolfsburg": "沃尔夫斯堡", "Eintracht Frankfurt": "法兰克福", "Frankfurt": "法兰克福",
    "Hoffenheim": "霍芬海姆", "Mainz": "美因茨", "Mainz 05": "美因茨",
    "Freiburg": "弗赖堡", "Augsburg": "奥格斯堡",
    "Hertha": "柏林赫塔", "Hertha Berlin": "柏林赫塔", "Hertha BSC": "柏林赫塔",
    "Union Berlin": "柏林联合", "Köln": "科隆", "FC Köln": "科隆",
    "Schalke": "沙尔克04", "Schalke 04": "沙尔克04",
    "Werder Bremen": "云达不莱梅", "Bremen": "不莱梅",
    "Stuttgart": "斯图加特", "Bochum": "波鸿",
    "Heidenheim": "海登海姆", "Darmstadt": "达姆施塔特",
    "Holstein Kiel": "基尔", "St. Pauli": "圣保利", "Hamburg": "汉堡",
    "Nürnberg": "纽伦堡", "Hannover": "汉诺威96", "Karlsruhe": "卡尔斯鲁厄",
    "Kaiserslautern": "凯泽斯劳滕", "Greuther Fürth": "菲尔特",
    "Düsseldorf": "杜塞尔多夫", "Magdeburg": "马格德堡",
    # 西甲
    "Real Madrid": "皇家马德里", "Barcelona": "巴塞罗那",
    "Atletico Madrid": "马德里竞技", "Atl. Madrid": "马德里竞技",
    "Athletic Club": "毕尔巴鄂竞技", "Ath Bilbao": "毕尔巴鄂竞技",
    "Real Sociedad": "皇家社会", "Real Betis": "贝蒂斯", "Betis": "贝蒂斯",
    "Villarreal": "比利亚雷亚尔", "Valencia": "瓦伦西亚",
    "Sevilla": "塞维利亚", "Getafe": "赫塔费", "Girona": "赫罗纳",
    "Osasuna": "奥萨苏纳", "Celta Vigo": "塞尔塔", "Celta": "塞尔塔",
    "Mallorca": "马略卡", "Rayo Vallecano": "巴列卡诺", "Rayo": "巴列卡诺",
    "Alaves": "阿拉维斯", "Alavés": "阿拉维斯",
    "Las Palmas": "拉斯帕尔马斯", "Espanyol": "西班牙人",
    "Leganes": "莱加内斯", "Leganés": "莱加内斯",
    "Valladolid": "巴拉多利德", "Cadiz": "加的斯", "Granada": "格拉纳达",
    "Almeria": "阿尔梅里亚", "Almería": "阿尔梅里亚",
    "Levante": "莱万特", "Eibar": "埃瓦尔",
    # 意甲
    "Inter": "国际米兰", "Inter Milan": "国际米兰",
    "Juventus": "尤文图斯", "AC Milan": "AC米兰", "Milan": "AC米兰",
    "Napoli": "那不勒斯", "Atalanta": "亚特兰大",
    "Roma": "罗马", "AS Roma": "罗马", "Lazio": "拉齐奥",
    "Fiorentina": "佛罗伦萨", "Bologna": "博洛尼亚", "Torino": "都灵",
    "Monza": "蒙扎", "Udinese": "乌迪内斯", "Sassuolo": "萨索洛",
    "Empoli": "恩波利", "Cagliari": "卡利亚里",
    "Genoa": "热那亚", "Hellas Verona": "维罗纳", "Verona": "维罗纳",
    "Lecce": "莱切", "Salernitana": "萨勒尼塔纳", "Frosinone": "弗罗西诺内",
    "Parma": "帕尔马", "Como": "科莫", "Venezia": "威尼斯",
    "Sampdoria": "桑普多利亚", "Brescia": "布雷西亚", "Palermo": "巴勒莫",
    "Bari": "巴里", "Pisa": "比萨", "Modena": "摩德纳",
    # 法甲
    "Paris SG": "巴黎圣日耳曼", "PSG": "巴黎圣日耳曼",
    "Marseille": "马赛", "Monaco": "摩纳哥", "AS Monaco": "摩纳哥",
    "Lyon": "里昂", "Lille": "里尔",
    "Nice": "尼斯", "Rennes": "雷恩", "Lens": "朗斯",
    "Strasbourg": "斯特拉斯堡", "Toulouse": "图卢兹",
    "Nantes": "南特", "Brest": "布雷斯特", "Reims": "兰斯",
    "Montpellier": "蒙彼利埃", "Lorient": "洛里昂",
    "Metz": "梅斯", "Clermont": "克莱蒙", "Le Havre": "勒阿弗尔",
    "Auxerre": "欧塞尔", "Saint-Étienne": "圣埃蒂安", "St Etienne": "圣埃蒂安",
    "Angers": "昂热", "Troyes": "特鲁瓦", "Ajaccio": "阿雅克肖",
    "Bordeaux": "波尔多", "Caen": "卡昂", "Boulogne": "布洛涅",
    "Nancy": "南锡", "Pau": "波城", "Rodez": "罗德兹",
    "Dunkerque": "敦刻尔克",
    # 荷甲
    "Ajax": "阿贾克斯", "PSV": "埃因霍温", "PSV Eindhoven": "埃因霍温",
    "Feyenoord": "费耶诺德", "AZ Alkmaar": "阿尔克马尔", "AZ": "阿尔克马尔",
    "Twente": "特温特", "Utrecht": "乌得勒支", "Vitesse": "维特斯",
    "Heerenveen": "海伦芬", "Sparta Rotterdam": "鹿特丹斯巴达",
    "NEC": "奈梅亨", "NEC Nijmegen": "奈梅亨",
    "Go Ahead Eagles": "前进之鹰", "Heracles": "赫拉克勒斯",
    "Fortuna Sittard": "锡塔德幸运", "PEC Zwolle": "兹沃勒", "Zwolle": "兹沃勒",
    "Excelsior": "SBV精英", "RKC Waalwijk": "瓦尔韦克",
    "Volendam": "福伦丹", "Cambuur": "坎布尔",
    "Almere City": "阿尔梅勒城", "Almere": "阿尔梅勒城",
    "Willem II": "威廉二世", "Groningen": "格罗宁根",
    # 比甲
    "Club Brugge": "布鲁日", "Anderlecht": "安德莱赫特", "Genk": "亨克",
    "Gent": "根特", "Antwerp": "安特卫普", "Standard": "标准列日",
    "Charleroi": "沙勒罗瓦", "Union SG": "圣吉罗斯联合",
    "Cercle Brugge": "色格拉布鲁日", "Mechelen": "梅赫伦",
    "Kortrijk": "科特赖克", "OH Leuven": "奥哈瓦里鲁汶",
    "Eupen": "奥伊彭", "Sint-Truiden": "圣图尔登", "STVV": "圣图尔登",
    "Westerlo": "韦斯特洛", "Molenbeek": "莫伦贝克", "RWDM": "莫伦贝克",
    "Dender": "登德",
    # 葡超
    "Benfica": "本菲卡", "Porto": "波尔图", "Sporting CP": "葡萄牙体育",
    "Braga": "布拉加", "Vitoria SC": "吉马良斯", "Boavista": "博阿维斯塔",
    "Famalicao": "法马利康", "Estoril": "埃斯托里尔", "Casa Pia": "卡萨皮亚",
    "Rio Ave": "里奥阿维", "Arouca": "阿罗卡", "Chaves": "查韦斯",
    "Moreirense": "莫雷拉人", "Portimonense": "波尔蒂芒人",
    "Gil Vicente": "吉尔维森特", "Santa Clara": "圣克拉拉",
    "Farense": "法伦斯", "AVS": "AVS俱乐部", "Nacional": "马德拉国民",
    # 苏超
    "Celtic": "凯尔特人", "Rangers": "流浪者", "Aberdeen": "阿伯丁",
    "Hearts": "哈茨", "Hibernian": "希伯尼安", "Kilmarnock": "基尔马诺克",
    "Motherwell": "马瑟韦尔", "St Mirren": "圣米伦", "St Johnstone": "圣约翰斯通",
    "Ross County": "罗斯郡", "Livingston": "利文斯顿", "Dundee": "邓迪",
    "Dundee United": "邓迪联", "Partick": "帕尔蒂克", "Airdrie Utd": "艾尔德里联",
    "Dumbarton": "邓巴顿", "Clyde": "克莱德", "East Kilbride": "东基尔布赖德",
    # 奥超
    "Red Bull Salzburg": "萨尔茨堡红牛", "Sturm Graz": "格拉茨风暴",
    "LASK": "林茨", "Rapid Vienna": "维也纳快速", "Austria Vienna": "奥地利维也纳",
    "Hartberg": "哈特贝格", "Wolfsberg": "沃尔夫斯贝格",
    "Altach": "阿尔塔奇", "WSG Tirol": "蒂罗尔WSG",
    "Blau-Weiss Linz": "林茨蓝白", "Grazer AK": "格拉茨AK",
    "Austria Klagenfurt": "克拉根福",
    # 希超
    "Olympiakos": "奥林匹亚科斯", "Olympiacos": "奥林匹亚科斯",
    "Panathinaikos": "帕纳辛奈科斯", "AEK Athens": "雅典AEK",
    "PAOK": "塞萨洛尼基", "Aris": "阿里斯",
}

# 反向映射（中文 → 候选英文队名集合）
CN_TO_EN_TEAMS: Dict[str, List[str]] = {}
for en, cn in EN_TO_CN_TEAMS.items():
    CN_TO_EN_TEAMS.setdefault(cn, []).append(en)


# ===========================================================================
# 工具函数
# ===========================================================================
def _normalize_team(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    for ch in [".", "-", "_", "'", "&", ",", "!"]:
        s = s.replace(ch, " ")
    for ch in ["  ", "   "]:
        s = s.replace(ch, " ")
    stopwords = {
        "fc", "cf", "sc", "ac", "as", "us", "sd", "rc", "ud", "cd", "afc", "bsc",
        "vfl", "sv", "msv", "krc", "kaa", "rkc", "gdz", "1", "05",
    }
    words = [w for w in s.split() if w not in stopwords and len(w) > 1]
    return " ".join(words)


def _parse_fd_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _fmt_handicap_cn(line: float) -> str:
    if line is None:
        return "—"
    if abs(line) < 0.125:
        return "平手"
    if line > 0:
        return f"主让{_fmt_q(line)}"
    return f"客让{_fmt_q(-line)}"


def _fmt_q(v: float) -> str:
    v = round(v, 2)
    if abs(v - round(v)) < 0.01:
        return str(int(round(v)))
    q = int(round(v * 4))
    whole = q // 4
    frac = q % 4
    if frac == 1:
        return f"{whole}.25" if whole > 0 else "0.25"
    elif frac == 2:
        return f"{whole}.5" if whole > 0 else "0.5"
    elif frac == 3:
        return f"{whole}.75" if whole > 0 else "0.75"
    return f"{whole}"


# ===========================================================================
# T-1 盘口结算
# ===========================================================================
def evaluate_handicap(ah_line: float, fthg: int, ftag: int) -> Dict[str, Any]:
    if fthg is None or ftag is None or ah_line is None:
        return {"result": "unknown", "label_cn": "—", "homeMargin": 0}
    diff = fthg - ftag
    margin = diff - ah_line
    if abs(margin) < 0.001:
        return {"result": "push", "label_cn": "走水", "homeMargin": diff, "margin": 0}
    elif margin > 0.25:
        return {"result": "home-win", "label_cn": "主赢盘", "homeMargin": diff, "margin": round(margin, 2)}
    elif margin > 0:
        return {"result": "home-half-win", "label_cn": "主赢半", "homeMargin": diff, "margin": round(margin, 2)}
    elif margin > -0.25:
        return {"result": "away-half-win", "label_cn": "客赢半", "homeMargin": diff, "margin": round(margin, 2)}
    else:
        return {"result": "away-win", "label_cn": "客赢盘", "homeMargin": diff, "margin": round(margin, 2)}


def evaluate_overunder(ou_line: float, fthg: int, ftag: int) -> Dict[str, Any]:
    if fthg is None or ftag is None or ou_line is None:
        return {"result": "unknown", "label_cn": "—", "total": 0}
    total = fthg + ftag
    margin = total - ou_line
    if abs(margin) < 0.001:
        return {"result": "push", "label_cn": "走水", "total": total, "margin": 0}
    elif margin > 0.25:
        return {"result": "over", "label_cn": "大球", "total": total, "margin": round(margin, 2)}
    elif margin > 0:
        return {"result": "over-half", "label_cn": "大赢半", "total": total, "margin": round(margin, 2)}
    elif margin > -0.25:
        return {"result": "under-half", "label_cn": "小赢半", "total": total, "margin": round(margin, 2)}
    else:
        return {"result": "under", "label_cn": "小球", "total": total, "margin": round(margin, 2)}


# ===========================================================================
# OddsFetcher 主类
# ===========================================================================
class OddsFetcher:
    BASE_URL = "https://www.football-data.co.uk"
    SEASONS = ["2627", "2526"]
    DIVS = ["E0", "E1", "E2", "E3", "EC", "D1", "D2", "SP1", "SP2", "I1", "I2",
            "F1", "F2", "N1", "B1", "P1", "T1", "G1", "S1", "SC0", "SC1", "A1"]

    def __init__(self, cache_ttl: int = 3600):
        self._cache: Dict[str, Tuple[float, List[Dict[str, str]]]] = {}
        self._cache_ttl = cache_ttl
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE
        self._ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36")
        self._en_norm_to_cn: Dict[str, str] = {}
        for en, cn in EN_TO_CN_TEAMS.items():
            self._en_norm_to_cn[_normalize_team(en)] = cn
        self._cn_to_en_list: Dict[str, List[str]] = CN_TO_EN_TEAMS
        self._all_rows_cache: Optional[List[Dict[str, Any]]] = None

    def _fetch_csv(self, url: str) -> Optional[List[Dict[str, str]]]:
        now = time.time()
        if url in self._cache:
            ts, rows = self._cache[url]
            if now - ts < self._cache_ttl:
                return rows
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._ua})
            resp = urllib.request.urlopen(req, context=self._ctx, timeout=20)
            raw = resp.read()
        except Exception as e:
            print(f"[odds] 下载失败 {url}: {e}")
            return None
        text = None
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return None
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except Exception as e:
            print(f"[odds] CSV解析失败 {url}: {e}")
            return None
        self._cache[url] = (now, rows)
        return rows

    def load_all(self) -> List[Dict[str, Any]]:
        if self._all_rows_cache is not None:
            return self._all_rows_cache
        all_rows: List[Dict[str, Any]] = []
        fx = self._fetch_csv(f"{self.BASE_URL}/fixtures.csv")
        if fx:
            for r in fx:
                nr = dict(r)
                nr["_source"] = "fixtures"
                nr["_div"] = r.get("Div", "")
                nr["_date"] = _parse_fd_date(r.get("Date", ""))
                all_rows.append(nr)
        for season in self.SEASONS:
            for div in self.DIVS:
                url = f"{self.BASE_URL}/mmz4281/{season}/{div}.csv"
                rows = self._fetch_csv(url)
                if not rows:
                    continue
                for r in rows:
                    nr = dict(r)
                    nr["_source"] = "history"
                    nr["_div"] = div
                    nr["_season"] = season
                    nr["_date"] = _parse_fd_date(r.get("Date", ""))
                    all_rows.append(nr)
        self._all_rows_cache = all_rows
        print(f"[odds] 加载完成：共 {len(all_rows)} 条赔率记录")
        return all_rows

    def _match_team_cn_to_en(self, cn_name: str) -> List[str]:
        if not cn_name:
            return []
        if cn_name in self._cn_to_en_list:
            return self._cn_to_en_list[cn_name]
        candidates = []
        for cn, ens in self._cn_to_en_list.items():
            if len(cn) >= 2 and (cn_name in cn or cn in cn_name):
                candidates.extend(ens)
        seen = set()
        uniq = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq

    @staticmethod
    def _to_float(v) -> Optional[float]:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _extract_bookmakers(self, row: Dict[str, str], ou_line: float) -> List[Dict[str, Any]]:
        books = []
        # football-data.co.uk AHh 符号约定：负数=主让球（主热），正数=客让球（客热）
        # 我们内部统一为：正数=主让球，负数=客让球，所以取反
        ah_open_raw = self._to_float(row.get("AHh"))
        ah_close_raw = self._to_float(row.get("AHCh"))
        ah_open = -ah_open_raw if ah_open_raw is not None else None
        ah_close = -ah_close_raw if ah_close_raw is not None else None
        ah_line = ah_open if ah_open is not None else ah_close

        for bm in BOOKMAKERS:
            key = bm["key"]
            entry: Dict[str, Any] = {
                "key": key, "name": bm["name"], "region": bm["region"],
            }
            if key == "PS":
                ah_home_o = self._to_float(row.get("PAHH"))
                ah_away_o = self._to_float(row.get("PAHA"))
                ah_home_c = self._to_float(row.get("PCAHH"))
                ah_away_c = self._to_float(row.get("PCAHA"))
                h_o = self._to_float(row.get("PSH"))
                d_o = self._to_float(row.get("PSD"))
                a_o = self._to_float(row.get("PSA"))
                h_c = self._to_float(row.get("PSCH"))
                d_c = self._to_float(row.get("PSCD"))
                a_c = self._to_float(row.get("PSCA"))
            else:
                ah_home_o = self._to_float(row.get(f"{key}AHH"))
                ah_away_o = self._to_float(row.get(f"{key}AHA"))
                ah_home_c = self._to_float(row.get(f"{key}CAHH"))
                ah_away_c = self._to_float(row.get(f"{key}CAHA"))
                h_o = self._to_float(row.get(f"{key}H"))
                d_o = self._to_float(row.get(f"{key}D"))
                a_o = self._to_float(row.get(f"{key}A"))
                h_c = self._to_float(row.get(f"{key}CH"))
                d_c = self._to_float(row.get(f"{key}CD"))
                a_c = self._to_float(row.get(f"{key}CA"))

            ou_over_o = self._to_float(row.get(f"{key}>2.5"))
            ou_under_o = self._to_float(row.get(f"{key}<2.5"))
            ou_over_c = self._to_float(row.get(f"{key}C>2.5"))
            ou_under_c = self._to_float(row.get(f"{key}C<2.5"))

            has_any = any([ah_home_o, ah_away_o, h_o, d_o, a_o, ou_over_o, ou_under_o,
                           ah_home_c, ah_away_c, h_c, d_c, a_c, ou_over_c, ou_under_c])
            if not has_any:
                continue

            entry["ah"] = {
                "line": ah_line, "lineOpen": ah_open, "lineClose": ah_close,
                "homeOpen": ah_home_o, "awayOpen": ah_away_o,
                "homeClose": ah_home_c, "awayClose": ah_away_c,
            }
            entry["ou"] = {
                "line": ou_line,
                "overOpen": ou_over_o, "underOpen": ou_under_o,
                "overClose": ou_over_c, "underClose": ou_under_c,
            }
            entry["hda"] = {
                "homeOpen": h_o, "drawOpen": d_o, "awayOpen": a_o,
                "homeClose": h_c, "drawClose": d_c, "awayClose": a_c,
            }
            books.append(entry)
        return books

    def _consensus(self, books: List[Dict[str, Any]],
                   ah_fallback: Optional[float],
                   ou_fallback: float) -> Dict[str, Optional[float]]:
        ah_lines = [b["ah"]["line"] for b in books if b["ah"]["line"] is not None]
        if ah_lines:
            ah_lines.sort()
            ah = ah_lines[len(ah_lines) // 2]
        else:
            ah = ah_fallback
        return {"ah": ah, "ou": ou_fallback}

    def match_odds(self,
                   home_cn: str,
                   away_cn: str,
                   match_date: Optional[str | date] = None,
                   league_hint: Optional[str] = None,
                   allow_date_window_days: int = 3) -> Optional[Dict[str, Any]]:
        tgt_date = None
        if match_date is not None:
            if isinstance(match_date, date):
                tgt_date = match_date
            else:
                try:
                    tgt_date = datetime.strptime(str(match_date)[:10], "%Y-%m-%d").date()
                except Exception:
                    tgt_date = None

        all_rows = self.load_all()
        if not all_rows:
            return None

        home_cands = self._match_team_cn_to_en(home_cn)
        away_cands = self._match_team_cn_to_en(away_cn)
        if not home_cands or not away_cands:
            return None

        def _norm(n: str) -> str:
            return n.lower().strip().replace(".", "").replace("  ", " ")

        home_cand_set = {_norm(c) for c in home_cands}
        away_cand_set = {_norm(c) for c in away_cands}

        best_match = None
        best_score = -1.0

        for r in all_rows:
            rd = r.get("_date")
            if tgt_date and rd is not None:
                if abs((rd - tgt_date).days) > allow_date_window_days:
                    continue
            en_home = (r.get("HomeTeam") or "").strip()
            en_away = (r.get("AwayTeam") or "").strip()
            if not en_home or not en_away:
                continue
            ehn = _norm(en_home)
            ean = _norm(en_away)

            home_hit = ehn in home_cand_set
            away_hit = ean in away_cand_set
            swapped = False
            if not (home_hit and away_hit):
                home_hit_swap = ehn in away_cand_set
                away_hit_swap = ean in home_cand_set
                if home_hit_swap and away_hit_swap:
                    home_hit = away_hit = True
                    swapped = True
                else:
                    home_hit = any(SequenceMatcher(None, ehn, c).ratio() > 0.88
                                   for c in home_cand_set)
                    away_hit = any(SequenceMatcher(None, ean, c).ratio() > 0.88
                                   for c in away_cand_set)
                    if not (home_hit and away_hit):
                        continue
                    swapped = False

            score = 1.0
            if tgt_date and rd is not None and rd == tgt_date:
                score += 3.0
            elif tgt_date and rd is not None:
                score -= 0.2 * abs((rd - tgt_date).days)
            if not swapped:
                score += 0.5
            fthg = self._to_float(r.get("FTHG"))
            ftag = self._to_float(r.get("FTAG"))
            if fthg is not None and ftag is not None:
                score += 0.3
            if r.get("AHh"):
                score += 0.2

            if score > best_score:
                best_score = score
                best_match = (r, swapped, fthg, ftag)

        if best_match is None:
            return None
        row, swapped, fthg, ftag = best_match

        div = row.get("_div", "")
        league_info = DIV_MAP.get(div, {"cn": div or league_hint or "", "en": div or ""})
        if league_hint and league_info["cn"] not in league_hint and league_hint not in league_info["cn"]:
            league_info = {"cn": league_hint, "en": league_info["en"]}

        # football-data.co.uk 原始AHh: 负=主让, 正=客让；统一为正=主让，所以取反
        ah_line_open_raw = self._to_float(row.get("AHh"))
        ah_line_close_raw = self._to_float(row.get("AHCh"))
        ah_line_open = -ah_line_open_raw if ah_line_open_raw is not None else None
        ah_line_close = -ah_line_close_raw if ah_line_close_raw is not None else None
        ah_line = ah_line_open if ah_line_open is not None else ah_line_close
        ou_line = 2.5

        if swapped and ah_line is not None:
            # swapped：CSV主客颠倒，盘口线方向也要反转
            ah_line = -ah_line

        books = self._extract_bookmakers(row, ou_line)
        if swapped:
            for b in books:
                ah = b["ah"]
                ah["homeOpen"], ah["awayOpen"] = ah["awayOpen"], ah["homeOpen"]
                ah["homeClose"], ah["awayClose"] = ah["awayClose"], ah["homeClose"]
                # 盘口线也取反（主客颠倒，让球方向反转）
                if ah["line"] is not None:
                    ah["line"] = -ah["line"]
                if ah["lineOpen"] is not None:
                    ah["lineOpen"] = -ah["lineOpen"]
                if ah["lineClose"] is not None:
                    ah["lineClose"] = -ah["lineClose"]
                hda = b["hda"]
                hda["homeOpen"], hda["awayOpen"] = hda["awayOpen"], hda["homeOpen"]
                hda["homeClose"], hda["awayClose"] = hda["awayClose"], hda["homeClose"]

        consensus = self._consensus(books, ah_line, ou_line)

        t1 = None
        has_result = fthg is not None and ftag is not None
        if has_result:
            fthg_i = int(fthg)
            ftag_i = int(ftag)
            line_ah = consensus["ah"] if consensus["ah"] is not None else 0
            line_ou = consensus["ou"] if consensus["ou"] is not None else 2.5
            hc = evaluate_handicap(line_ah, fthg_i, ftag_i)
            ou = evaluate_overunder(line_ou, fthg_i, ftag_i)
            t1 = {
                "fthg": fthg_i, "ftag": ftag_i,
                "total": fthg_i + ftag_i, "homeMargin": fthg_i - ftag_i,
                "handicap": hc, "overunder": ou,
            }

        home_en_final = (row.get("AwayTeam") if swapped else row.get("HomeTeam") or "")
        away_en_final = (row.get("HomeTeam") if swapped else row.get("AwayTeam") or "")

        return {
            "source": "football-data.co.uk",
            "div": div,
            "league": league_info,
            "matchDate": row.get("_date").isoformat() if row.get("_date") else row.get("Date"),
            "homeEn": home_en_final,
            "awayEn": away_en_final,
            "swapped": swapped,
            "ahLine": consensus["ah"],
            "ouLine": consensus["ou"],
            "ahLineLabel": _fmt_handicap_cn(consensus["ah"]),
            "ouLineLabel": f"{_fmt_q(consensus['ou'])}球",
            "bookmakers": books,
            "bookmakerCount": len(books),
            "hasLiveResult": has_result,
            "fthg": int(fthg) if has_result else None,
            "ftag": int(ftag) if has_result else None,
            "t1Comparison": t1,
        }


# ===========================================================================
# CLI 自测
# ===========================================================================
if __name__ == "__main__":
    fetcher = OddsFetcher()
    test_matches = [
        ("Club Brugge", "Kortrijk", "2026-08-08", None),  # B1比甲fixtures.csv中有
        ("Bochum", "Hertha", "2026-08-08", None),
    ]
    for h, a, d, lg in test_matches:
        print(f"\n=== 测试: {h} vs {a} ({d}) ===")
        r = fetcher.match_odds(h, a, d, lg)
        if r is None:
            print("  未匹配")
            continue
        print(f"  匹配到: {r['homeEn']} vs {r['awayEn']} / {r['league']['cn']} / AH={r['ahLineLabel']}")
        print(f"  博彩公司数: {r['bookmakerCount']}")
        for b in r["bookmakers"][:5]:
            ah = b["ah"]
            print(f"    {b['name']}: AH主{ah['homeOpen']}/客{ah['awayOpen']}  "
                  f"OU大{b['ou']['overOpen']}/小{b['ou']['underOpen']}")
        if r["hasLiveResult"]:
            t = r["t1Comparison"]
            print(f"  实际比分: {t['fthg']}-{t['ftag']}  盘口:{t['handicap']['label_cn']}  大小:{t['overunder']['label_cn']}")
