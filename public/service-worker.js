/* =========================================================
 * 🔵 FT早知道 Service Worker（PWA离线缓存 + 移动端App内核）
 * - 策略：App Shell（index.html / women.html / manifest / 图标）= 安装时预缓存+Stale-While-Revalidate
 * - 静态数据JSON（dashboard/teams/push）= 安装时预缓存+Cache-First优先（离线可看）
 * - HTTP API（/api/dashboard /api/update）= Network-First + 离线fallback（避免黑洞卡死）
 * - 移动端App打包（Capacitor/WebView file:// 协议）= 直接透传不缓存（WebView本身有文件缓存）
 * ========================================================= */
const CACHE_VER = 'ft-zazao-v2';  // 构建后改此版本号即可强制用户端刷新所有缓存（v2: 修复loadData白屏+统一women入口）
const APP_SHELL_CORE = [
  './',
  './index.html',
  './women.html',
  './manifest.json',
  './icons/icon.svg'
];
const PRECACHE_DATA = [
  './data/dashboard.json',
  './data/dashboard-women.json',
  './data/dashboard-europe.json',
  './data/dashboard-europe-women.json',
  './data/dashboard-asia.json',
  './data/dashboard-asia-women.json',
  './data/dashboard-australia.json',
  './data/dashboard-australia-women.json',
  './data/health.json',
  './data/teams.json',
  './data/push-latest.json',
  './data/push-latest-women.json',
  './data/push-history.json',
  './data/push-history-women.json',
  './data/archive/archive_index.json'
];
const PRECACHE_ALL = APP_SHELL_CORE.concat(PRECACHE_DATA);

const isFileProtocol = () => self.location.protocol === 'file:';

// ① install：预缓存App Shell + 核心JSON（第一次安装PWA/打开App时执行，成功后activate）
self.addEventListener('install', (event) => {
  // file协议（Capacitor本地App壳）：跳过预缓存（直接读本地文件）
  if (isFileProtocol()) { self.skipWaiting(); return; }
  event.waitUntil(
    caches.open(CACHE_VER)
      .then(async (cache) => {
        // 一个一个缓存，失败的跳过（比如还没构建归档文件的情况）
        const results = await Promise.allSettled(
          PRECACHE_ALL.map(url => cache.add(url).catch(err => {
            console.warn('[SW precache skip]', url, err && err.message);
            return Promise.resolve();
          }))
        );
        const ok = results.filter(r => r.status === 'fulfilled').length;
        console.log(`[SW install] CACHE=${CACHE_VER} precached ${ok}/${PRECACHE_ALL.length} resources`);
      })
      .then(() => self.skipWaiting())
      .catch(err => { console.error('[SW install fatal]', err); self.skipWaiting(); })
  );
});

// ② activate：清理过期旧版本缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_VER).map(k => { console.log('[SW activate] delete old cache', k); return caches.delete(k); })
    )).then(() => self.clients.claim())
  );
});

// ③ fetch：按资源类型分策略（CacheFirst / StaleWhileRevalidate / NetworkFirst）
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;  // 只缓存GET请求（POST /api/update不缓存）
  if (isFileProtocol()) return;      // file协议：WebView本地文件，我们不拦

  const url = new URL(req.url);
  const isSameOrigin = url.origin === self.location.origin;
  if (!isSameOrigin) return;         // 第三方资源：透传

  const path = url.pathname;

  // 策略A：HTTP API (/api/*) → NetworkFirst，超时或失败则读cache兜底
  if (path.startsWith('/api/')) {
    event.respondWith((async () => {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 10000);
        try {
          const resp = await fetch(req, { signal: ctrl.signal });
          const cache = await caches.open(CACHE_VER);
          cache.put(req, resp.clone()).catch(()=>{});
          return resp;
        } finally { clearTimeout(timer); }
      } catch (e) {
        const cached = await caches.match(req);
        if (cached) return cached;
        // API兜底：返回空JSON壳，前端tryFetchJson null处理链路接上
        return new Response(JSON.stringify({ error: 'offline-fallback', msg: '离线模式，API暂不可用' }), {
          status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' }
        });
      }
    })());
    return;
  }

  // 策略B：HTML页面（/index.html / women.html 或 根路径 /）→ StaleWhileRevalidate
  const ext = (path.split('.').pop() || '').toLowerCase();
  if (ext === 'html' || path === '/' || !path.includes('.')) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VER);
      const cached = await cache.match(req);
      // 后台同步：fetch最新页面，成功就覆盖cache，给下一次用
      const netPromise = fetch(req).then(async resp => {
        if (resp && resp.ok) cache.put(req, resp.clone()).catch(()=>{});
        return resp;
      }).catch(() => cached || new Response('Offline', { status: 503 }));
      // 先返回cache的版本（秒开），后台悄悄更新
      if (cached) {
        netPromise.then(() => {
          // 通知客户端页面：有新版本，可提示刷新
          self.clients.matchAll().then(cs => cs.forEach(c => {
            try { c.postMessage({ type: 'SW_NEW_VERSION', cache: CACHE_VER }); } catch(_){}
          }));
        }).catch(()=>{});
        return cached;
      }
      return await netPromise;
    })());
    return;
  }

  // 策略C：JSON数据/Manifest/图标 → CacheFirst（离线优先，失败再fallback network）
  if (['json', 'svg', 'png', 'jpg', 'jpeg', 'webp', 'webmanifest'].includes(ext)) {
    event.respondWith((async () => {
      const cached = await caches.match(req);
      if (cached) return cached;
      try {
        const resp = await fetch(req);
        if (resp && resp.ok) {
          const cache = await caches.open(CACHE_VER);
          cache.put(req, resp.clone()).catch(()=>{});
        }
        return resp;
      } catch(e) {
        return new Response('', { status: 408 });
      }
    })());
    return;
  }

  // 策略D：其他静态资源（CSS/JS其实都是内联的）→ StaleWhileRevalidate
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_VER);
    const cached = await cache.match(req);
    const netPromise = fetch(req).then(resp => {
      if (resp && resp.ok) cache.put(req, resp.clone()).catch(()=>{});
      return resp;
    }).catch(() => cached);
    return cached || netPromise;
  })());
});

// ④ message：手动触发SW更新（用户点⚡按钮后可以postMessage）
self.addEventListener('message', (event) => {
  if (!event || !event.data) return;
  if (event.data.type === 'SKIP_WAITING') { self.skipWaiting(); }
  if (event.data.type === 'PING') { event.source && event.source.postMessage && event.source.postMessage({ type:'PONG', ver: CACHE_VER }); }
  if (event.data.type === 'CLEAR_CACHE') {
    caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => event.source && event.source.postMessage && event.source.postMessage({ type:'CLEAR_OK' }));
  }
});
