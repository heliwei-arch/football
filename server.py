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


def updateDashboardData(manualTrigger=False):
    """核心数据更新函数"""
    global cacheData
    timestamp = datetime.now().isoformat()
    print(f"\n[数据更新] {'手动触发' if manualTrigger else '定时任务'} 开始 - {timestamp}")
    try:
        random.seed()  # 重置随机种子
        yesterdayMatches = generateYesterdayMatches()
        todayPreviews = generateTodayPreviews()
        pushDigest = generatePushDigest(yesterdayMatches, todayPreviews)

        cacheData["lastUpdate"] = timestamp
        cacheData["yesterdayMatches"] = yesterdayMatches
        cacheData["todayPreviews"] = todayPreviews
        cacheData["pushDigest"] = pushDigest

        entry = {"timestamp": timestamp, "manual": manualTrigger, "digest": pushDigest}
        cacheData.setdefault("pushHistory", []).insert(0, entry)
        if len(cacheData["pushHistory"]) > 30:
            cacheData["pushHistory"] = cacheData["pushHistory"][:30]

        saveCache()

        print(f"[数据更新] 完成 - T-1赛事: {len(yesterdayMatches)}场, 今日预告: {len(todayPreviews)}场")
        print(f"[推送摘要] {pushDigest['title']}")
        print(f"  昨日精选: {pushDigest['yesterdaySummary'][:80]}...")
        print(f"  今日焦点: {pushDigest['todaySummary'][:80]}...")

        return {"success": True, "timestamp": timestamp,
                "counts": {"yesterday": len(yesterdayMatches), "today": len(todayPreviews)}}
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
            self._send_json({
                "status": "ok",
                "uptime": round(time.time() - self.server.start_time, 2),
                "lastUpdate": cacheData.get("lastUpdate"),
                "hasData": len(cacheData.get("yesterdayMatches", [])) > 0
            })
            return
        if path == "/api/dashboard":
            region = qs.get("region", ["all"])[0]
            ym = cacheData.get("yesterdayMatches", [])
            tp = cacheData.get("todayPreviews", [])
            if region and region != "all":
                ym = [m for m in ym if m.get("region") == region]
                tp = [m for m in tp if m.get("region") == region]
            self._send_json({
                "lastUpdate": cacheData.get("lastUpdate"),
                "generatedAt": datetime.now().isoformat(),
                "leagues": LEAGUES,
                "yesterdayMatches": ym,
                "todayPreviews": tp,
                "pushDigest": cacheData.get("pushDigest")
            })
            return
        if path == "/api/matches/yesterday":
            region = qs.get("region", ["all"])[0]
            mid = qs.get("id", [None])[0]
            data = cacheData.get("yesterdayMatches", [])
            if region and region != "all":
                data = [m for m in data if m.get("region") == region]
            if mid:
                data = next((m for m in data if m.get("id") == mid), None)
            self._send_json({"lastUpdate": cacheData.get("lastUpdate"), "data": data})
            return
        if path == "/api/matches/today":
            region = qs.get("region", ["all"])[0]
            mid = qs.get("id", [None])[0]
            data = cacheData.get("todayPreviews", [])
            if region and region != "all":
                data = [m for m in data if m.get("region") == region]
            if mid:
                data = next((m for m in data if m.get("id") == mid), None)
            self._send_json({"lastUpdate": cacheData.get("lastUpdate"), "data": data})
            return
        if path == "/api/push/latest":
            self._send_json({
                "lastUpdate": cacheData.get("lastUpdate"),
                "latest": cacheData.get("pushDigest"),
                "history": (cacheData.get("pushHistory") or [])[:5]
            })
            return
        if path == "/api/push/history":
            self._send_json({"history": cacheData.get("pushHistory") or []})
            return

        # 静态文件
        if not path.startswith("/api/"):
            self._send_file(path)
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/update":
            result = updateDashboardData(True)
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
