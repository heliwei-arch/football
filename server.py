"""足球赛道仪表盘后端服务器 (Python标准库实现，零外部依赖)"""
import json
import os
import sys
import threading
import time
import random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_FILE = os.path.join(BASE_DIR, "cache.json")
PORT = int(os.environ.get("PORT", 3000))

# 导入数据层
sys.path.insert(0, BASE_DIR)
from data import (
    LEAGUES,
    formatDate,
    getToday,
    generateYesterdayMatches,
    generateTodayPreviews,
    generatePushDigest
)

# 优先懂球帝真实数据（和 generate_static.py 共享同一套 Adapter）
try:
    from generate_static import build_from_dongqiudi
    _DQD_AVAILABLE = True
except Exception as _e:
    print(f"[server] 懂球帝适配器未加载（fallback到Mock）: {_e}")
    build_from_dongqiudi = None
    _DQD_AVAILABLE = False

# 单一事实来源：男足/女足筛选口径，禁止在各API散落if "女足" in导致口径漂移
# （和 crawl_dongqiudi.py / generate_static.py 保持一致）
try:
    from crawl_dongqiudi import filter_by_gender as _ssot_filter_by_gender
    _FILTER_GENDER_OK = True
except Exception as _e:
    _ssot_filter_by_gender = None
    _FILTER_GENDER_OK = False
    print(f"[server] 性别筛选SSOT未加载，fallback全量: {_e}")
try:
    from generate_static import split_by_gender as _ssot_split_by_gender
except Exception:
    _ssot_split_by_gender = None


def _split_gender_counts(ym, tp):
    """给定全量ym/tp，按SSOT性别筛选返回{men:{y,t}, women:{y,t}} + counts字典。"""
    counts_men = {"yesterday": 0, "today": 0}
    counts_women = {"yesterday": 0, "today": 0}
    if _ssot_filter_by_gender:
        ym_men = _ssot_filter_by_gender(ym, "men")
        ym_women = _ssot_filter_by_gender(ym, "women")
        tp_men = _ssot_filter_by_gender(tp, "men")
        tp_women = _ssot_filter_by_gender(tp, "women")
    else:
        # 极端兜底：SSOT未加载 → 全部归为men，men兜底不丢失数据
        ym_men, ym_women = list(ym), []
        tp_men, tp_women = list(tp), []
    counts_men["yesterday"] = len(ym_men); counts_men["today"] = len(tp_men)
    counts_women["yesterday"] = len(ym_women); counts_women["today"] = len(tp_women)
    return (ym_men, tp_men, ym_women, tp_women), {"men": counts_men, "women": counts_women}

# ================= 内存缓存 ================
cacheData = {
    "lastUpdate": None,
    "yesterdayMatches": [],
    "todayPreviews": [],
    "pushDigest": None,
    "pushHistory": []
}


def loadCache():
    """从磁盘加载缓存"""
    global cacheData
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                cacheData = json.load(f)
            print(f"[缓存加载] 已加载历史数据，上次更新: {cacheData.get('lastUpdate') or '无'}")
    except Exception as e:
        print(f"[缓存加载] 失败: {e}")


def saveCache():
    """保存缓存到磁盘"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(cacheData, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[缓存保存] 失败: {e}")


def updateDashboardData(manualTrigger=False, gender="men"):
    """核心数据更新函数：优先懂球帝真实数据，失败fallback到Mock

    gender: "men" | "women" | "all" —— 仅控制返回 counts 按该性别口径返回；
            实际拉取/缓存仍是全量（与 generate_static.py 拆分一致，SSOT筛选在查询时）。
    """
    global cacheData
    timestamp = datetime.now().isoformat()
    print(f"\n[数据更新] {'手动触发' if manualTrigger else '定时任务'} 开始 - {timestamp}")
    try:
        random.seed()

        yesterdayMatches = None
        todayPreviews = None
        dataSource = "mock-generated"
        if _DQD_AVAILABLE and build_from_dongqiudi is not None:
            try:
                yesterdayMatches, todayPreviews = build_from_dongqiudi()
                if yesterdayMatches is not None or todayPreviews is not None:
                    dataSource = "dongqiudi-real"
            except Exception as e:
                print(f"[数据更新] 懂球帝拉取失败，回退Mock: {e}")

        if yesterdayMatches is None:
            yesterdayMatches = generateYesterdayMatches()
        if todayPreviews is None:
            todayPreviews = generateTodayPreviews()

        # 按SSOT拆分男女足，给pushDigest两份
        (ym_men, tp_men, ym_women, tp_women), gender_counts = _split_gender_counts(
            yesterdayMatches, todayPreviews
        )

        pushDigest = generatePushDigest(yesterdayMatches, todayPreviews)
        pushDigestMen = generatePushDigest(ym_men, tp_men)
        pushDigestWomen = generatePushDigest(ym_women, tp_women)
        if dataSource == "dongqiudi-real":
            for pd, label, g in [
                (pushDigest, "（懂球帝真实数据）", None),
                (pushDigestMen, "（懂球帝真实数据 · 男足）", "men"),
                (pushDigestWomen, "（懂球帝真实数据 · 女足）", "women"),
            ]:
                pd["title"] = (pd.get("title") or "") + label
                pd["_dataSource"] = "dongqiudi-real"
                if g:
                    pd["_gender"] = g

        cacheData["lastUpdate"] = timestamp
        cacheData["yesterdayMatches"] = yesterdayMatches
        cacheData["todayPreviews"] = todayPreviews
        cacheData["pushDigest"] = pushDigest
        cacheData["pushDigestMen"] = pushDigestMen
        cacheData["pushDigestWomen"] = pushDigestWomen
        cacheData["dataSource"] = dataSource
        cacheData["genderCounts"] = gender_counts

        entry = {"timestamp": timestamp, "manual": manualTrigger, "digest": pushDigest}
        entry_men = {"timestamp": timestamp, "manual": manualTrigger, "digest": pushDigestMen}
        entry_women = {"timestamp": timestamp, "manual": manualTrigger, "digest": pushDigestWomen}
        cacheData.setdefault("pushHistory", []).insert(0, entry)
        cacheData.setdefault("pushHistoryMen", []).insert(0, entry_men)
        cacheData.setdefault("pushHistoryWomen", []).insert(0, entry_women)
        for k in ("pushHistory", "pushHistoryMen", "pushHistoryWomen"):
            if len(cacheData[k]) > 30:
                cacheData[k] = cacheData[k][:30]

        saveCache()

        # 返回 counts：按传入gender
        if gender == "women":
            resp_counts = dict(gender_counts["women"])
            resp_push = pushDigestWomen
        elif gender == "men":
            resp_counts = dict(gender_counts["men"])
            resp_push = pushDigestMen
        else:
            resp_counts = {
                "yesterday": len(yesterdayMatches), "today": len(todayPreviews),
                "_byGender": gender_counts,
            }
            resp_push = pushDigest

        print(f"[数据更新] 完成 - 数据源:{dataSource}, "
              f"男足(T-1:{gender_counts['men']['yesterday']},今日:{gender_counts['men']['today']}) "
              f"女足(T-1:{gender_counts['women']['yesterday']},今日:{gender_counts['women']['today']})")
        print(f"[推送摘要] {pushDigest['title']}")
        print(f"  昨日精选: {str(pushDigest.get('yesterdaySummary',''))[:80]}...")
        print(f"  今日焦点: {str(pushDigest.get('todaySummary',''))[:80]}...")

        return {
            "success": True, "timestamp": timestamp, "dataSource": dataSource,
            "gender": gender,
            "counts": resp_counts,
            "genderCounts": gender_counts,
            "pushDigest": resp_push,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[数据更新] 出错: {e}")
        return {"success": False, "error": str(e)}


# ================= HTTP 处理器 ================
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf"
}


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "FootballDashboard/1.0"

    def log_message(self, format, *args):
        """精简日志"""
        msg = f"{self.address_string()} - {format % args}"
        if not msg.startswith("GET /api"):
            print(msg)

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, relpath):
        fp = os.path.join(PUBLIC_DIR, relpath.lstrip("/").replace("/", os.sep))
        # 安全：防止路径穿越
        if not fp.startswith(PUBLIC_DIR):
            self.send_error(403)
            return
        if not os.path.isfile(fp):
            # 默认返回 index.html (SPA)
            fp = os.path.join(PUBLIC_DIR, "index.html")
            if not os.path.exists(fp):
                self.send_error(404)
                return
        ext = os.path.splitext(fp)[1].lower()
        mime = MIME.get(ext, "application/octet-stream")
        try:
            with open(fp, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        # 🔴 防CDN强缓存：对 index.html / .html 永远加 no-cache+must-revalidate，避免用户拿到3天前的死版本
        basename = os.path.basename(fp)
        if ext == ".html" or basename == "index.html":
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        elif ext in (".js", ".css"):
            # 静态资源加短缓存（1分钟），避免首次空白屏后第二刷新仍拿旧资源
            self.send_header("Cache-Control", "public, max-age=60, must-revalidate")
        else:
            # 图片/JSON等其他资源：5分钟缓存
            self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)

    # ---------- 路由分发 ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self._send_file("index.html")
            return
        if path == "/api/health":
            ym_all = cacheData.get("yesterdayMatches", []) or []
            tp_all = cacheData.get("todayPreviews", []) or []
            _c, gender_counts = _split_gender_counts(ym_all, tp_all)
            self._send_json({
                "status": "ok",
                "uptime": round(time.time() - self.server.start_time, 2),
                "lastUpdate": cacheData.get("lastUpdate"),
                "hasData": len(ym_all) > 0,
                "dataSource": cacheData.get("dataSource", "mock-generated"),
                "genderCounts": gender_counts,
                "counts": {
                    "all": {"yesterday": len(ym_all), "today": len(tp_all)},
                    "men": gender_counts["men"],
                    "women": gender_counts["women"],
                }
            })
            return
        if path == "/api/dashboard":
            region = qs.get("region", ["all"])[0]
            gender = (qs.get("gender", ["men"])[0] or "men").lower()
            if gender not in ("men", "women", "all"):
                gender = "men"
            ym = list(cacheData.get("yesterdayMatches", []) or [])
            tp = list(cacheData.get("todayPreviews", []) or [])
            # 1) gender筛选（SSOT）
            if gender != "all" and _ssot_filter_by_gender:
                ym = _ssot_filter_by_gender(ym, gender)
                tp = _ssot_filter_by_gender(tp, gender)
            # 2) region筛选
            if region and region != "all":
                ym = [m for m in ym if m.get("region") == region]
                tp = [m for m in tp if m.get("region") == region]
            # 3) 推送摘要：按gender选
            if gender == "women":
                push_pick = cacheData.get("pushDigestWomen") or cacheData.get("pushDigest")
            elif gender == "men":
                push_pick = cacheData.get("pushDigestMen") or cacheData.get("pushDigest")
            else:
                push_pick = cacheData.get("pushDigest")
            _c, gender_counts = _split_gender_counts(
                cacheData.get("yesterdayMatches", []) or [],
                cacheData.get("todayPreviews", []) or []
            )
            self._send_json({
                "lastUpdate": cacheData.get("lastUpdate"),
                "generatedAt": datetime.now().isoformat(),
                "dataSource": cacheData.get("dataSource", "mock-generated"),
                "gender": gender,
                "leagues": LEAGUES,
                "yesterdayMatches": ym,
                "todayPreviews": tp,
                "pushDigest": push_pick,
                "genderCounts": gender_counts,
            })
            return
        if path == "/api/matches/yesterday":
            region = qs.get("region", ["all"])[0]
            gender = (qs.get("gender", ["men"])[0] or "men").lower()
            mid = qs.get("id", [None])[0]
            data = list(cacheData.get("yesterdayMatches", []) or [])
            if gender not in ("all",) and _ssot_filter_by_gender:
                data = _ssot_filter_by_gender(data, gender if gender in ("men","women") else "men")
            if region and region != "all":
                data = [m for m in data if m.get("region") == region]
            if mid:
                data = next((m for m in data if m.get("id") == mid), None)
            self._send_json({"lastUpdate": cacheData.get("lastUpdate"), "gender": gender, "data": data})
            return
        if path == "/api/matches/today":
            region = qs.get("region", ["all"])[0]
            gender = (qs.get("gender", ["men"])[0] or "men").lower()
            mid = qs.get("id", [None])[0]
            data = list(cacheData.get("todayPreviews", []) or [])
            if gender not in ("all",) and _ssot_filter_by_gender:
                data = _ssot_filter_by_gender(data, gender if gender in ("men","women") else "men")
            if region and region != "all":
                data = [m for m in data if m.get("region") == region]
            if mid:
                data = next((m for m in data if m.get("id") == mid), None)
            self._send_json({"lastUpdate": cacheData.get("lastUpdate"), "gender": gender, "data": data})
            return
        if path == "/api/push/latest":
            gender = (qs.get("gender", ["men"])[0] or "men").lower()
            if gender == "women":
                latest = cacheData.get("pushDigestWomen") or cacheData.get("pushDigest")
                history = cacheData.get("pushHistoryWomen") or []
            elif gender == "men":
                latest = cacheData.get("pushDigestMen") or cacheData.get("pushDigest")
                history = cacheData.get("pushHistoryMen") or cacheData.get("pushHistory") or []
            else:
                latest = cacheData.get("pushDigest")
                history = cacheData.get("pushHistory") or []
            self._send_json({
                "lastUpdate": cacheData.get("lastUpdate"),
                "gender": gender,
                "latest": latest,
                "history": list(history)[:5]
            })
            return
        if path == "/api/push/history":
            gender = (qs.get("gender", ["men"])[0] or "men").lower()
            if gender == "women":
                history = cacheData.get("pushHistoryWomen") or []
            elif gender == "men":
                history = cacheData.get("pushHistoryMen") or cacheData.get("pushHistory") or []
            else:
                history = cacheData.get("pushHistory") or []
            self._send_json({"history": list(history), "gender": gender})
            return

        # 静态文件
        if not path.startswith("/api/"):
            self._send_file(path)
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path == "/api/update":
            gender = (qs.get("gender", ["men"])[0] or "men").lower()
            if gender not in ("men", "women", "all"):
                gender = "men"
            result = updateDashboardData(True, gender=gender)
            self._send_json(result, 200 if result["success"] else 500)
            return
        self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ================= 定时更新线程 =================
def scheduler_loop():
    """线程：每天上午 9:00 (Asia/Shanghai ≈ UTC+8，所以UTC 1点) 执行更新"""
    # 简化：每分钟检查一次，若当前本地时间为 9:xx 且今天尚未更新，则执行
    last_run_date = None
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            if (now.hour == 9 and last_run_date != today_str):
                print(f"\n⏰ [定时任务触发] 每日9点更新 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
                updateDashboardData(False)
                last_run_date = today_str
        except Exception as e:
            print(f"[调度线程异常] {e}")
        time.sleep(30)  # 每30秒检查一次


# ================= 启动 =================
def main():
    # 1. 加载缓存
    loadCache()

    # 2. 如果没有数据，立即生成一次
    if not cacheData.get("lastUpdate") or len(cacheData.get("yesterdayMatches", [])) == 0:
        print("[启动] 首次运行，正在生成初始数据...")
        updateDashboardData(True)

    # 3. 启动定时线程
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    print("✅ [定时任务已注册] 每日上午9:00 自动更新数据（本地线程调度）")

    # 4. 启动HTTP服务
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    server.start_time = time.time()
    print("\n" + "=" * 60)
    print("🚀 足球赛道分析仪表盘已启动 (Python版)")
    print(f"📅 今日日期: {formatDate(getToday())}")
    print(f"🌐 网页访问: http://localhost:{PORT}/")
    print(f"📡 API 接口: http://localhost:{PORT}/api/dashboard")
    print(f"🔄 下次更新: 明日上午 9:00")
    print("=" * 60 + "\n")
    print("提示: 如需立即更新，可发送 POST /api/update")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[停止] 服务已关闭")
        server.server_close()


if __name__ == "__main__":
    main()
