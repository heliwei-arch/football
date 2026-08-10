const express = require('express');
const cron = require('node-cron');
const path = require('path');
const fs = require('fs');

const {
  LEAGUES,
  formatDate,
  getToday,
  generateYesterdayMatches,
  generateTodayPreviews,
  generatePushDigest
} = require('./data.js');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// 内存缓存数据
let cacheData = {
  lastUpdate: null,
  yesterdayMatches: [],
  todayPreviews: [],
  pushDigest: null,
  pushHistory: []
};

// 数据存储文件
const DATA_FILE = path.join(__dirname, 'cache.json');

// 从磁盘加载缓存
function loadCache() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      const raw = fs.readFileSync(DATA_FILE, 'utf8');
      cacheData = JSON.parse(raw);
      console.log(`[缓存加载] 已加载历史数据，上次更新: ${cacheData.lastUpdate || '无'}`);
    }
  } catch (e) {
    console.error('[缓存加载] 失败:', e.message);
  }
}

// 保存缓存到磁盘
function saveCache() {
  try {
    fs.writeFileSync(DATA_FILE, JSON.stringify(cacheData, null, 2), 'utf8');
  } catch (e) {
    console.error('[缓存保存] 失败:', e.message);
  }
}

// 核心数据更新函数
function updateDashboardData(manualTrigger = false) {
  const now = new Date();
  const timestamp = now.toISOString();
  
  console.log(`[数据更新] ${manualTrigger ? '手动触发' : '定时任务'} 开始 - ${timestamp}`);
  
  try {
    const yesterdayMatches = generateYesterdayMatches();
    const todayPreviews = generateTodayPreviews();
    const pushDigest = generatePushDigest(yesterdayMatches, todayPreviews);
    
    cacheData.lastUpdate = timestamp;
    cacheData.yesterdayMatches = yesterdayMatches;
    cacheData.todayPreviews = todayPreviews;
    cacheData.pushDigest = pushDigest;
    
    // 记录推送历史
    cacheData.pushHistory.unshift({
      timestamp,
      manual: manualTrigger,
      digest: pushDigest
    });
    if (cacheData.pushHistory.length > 30) {
      cacheData.pushHistory = cacheData.pushHistory.slice(0, 30);
    }
    
    saveCache();
    
    console.log(`[数据更新] 完成 - T-1赛事: ${yesterdayMatches.length}场, 今日预告: ${todayPreviews.length}场`);
    console.log(`[推送摘要] ${pushDigest.title}`);
    console.log(`  昨日精选: ${pushDigest.yesterdaySummary}`);
    console.log(`  今日焦点: ${pushDigest.todaySummary}`);
    
    return { success: true, timestamp, counts: { yesterday: yesterdayMatches.length, today: todayPreviews.length } };
  } catch (e) {
    console.error('[数据更新] 出错:', e);
    return { success: false, error: e.message };
  }
}

// ========== API 路由 ==========

// 健康检查
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    lastUpdate: cacheData.lastUpdate,
    hasData: cacheData.yesterdayMatches.length > 0
  });
});

// 获取全部仪表盘数据
app.get('/api/dashboard', (req, res) => {
  const { region } = req.query;
  let yesterdayMatches = cacheData.yesterdayMatches;
  let todayPreviews = cacheData.todayPreviews;
  
  if (region && region !== 'all') {
    yesterdayMatches = yesterdayMatches.filter(m => m.region === region);
    todayPreviews = todayPreviews.filter(m => m.region === region);
  }
  
  res.json({
    lastUpdate: cacheData.lastUpdate,
    generatedAt: new Date().toISOString(),
    leagues: LEAGUES,
    yesterdayMatches,
    todayPreviews,
    pushDigest: cacheData.pushDigest
  });
});

// 获取昨日赛事（T-1）
app.get('/api/matches/yesterday', (req, res) => {
  const { region, id } = req.query;
  let data = cacheData.yesterdayMatches;
  if (region && region !== 'all') data = data.filter(m => m.region === region);
  if (id) data = data.find(m => m.id === id) || null;
  res.json({
    lastUpdate: cacheData.lastUpdate,
    data
  });
});

// 获取今日预告
app.get('/api/matches/today', (req, res) => {
  const { region, id } = req.query;
  let data = cacheData.todayPreviews;
  if (region && region !== 'all') data = data.filter(m => m.region === region);
  if (id) data = data.find(m => m.id === id) || null;
  res.json({
    lastUpdate: cacheData.lastUpdate,
    data
  });
});

// 手动触发数据更新
app.post('/api/update', (req, res) => {
  const result = updateDashboardData(true);
  res.json(result);
});

// 获取最新推送摘要
app.get('/api/push/latest', (req, res) => {
  res.json({
    lastUpdate: cacheData.lastUpdate,
    latest: cacheData.pushDigest,
    history: cacheData.pushHistory.slice(0, 5)
  });
});

// 获取推送历史
app.get('/api/push/history', (req, res) => {
  res.json({
    history: cacheData.pushHistory
  });
});

// ========== 定时任务：每日 9:00 上午更新 ==========
// Cron 格式：秒 分 时 日 月 星期
// 每天 09:00:00 执行
const CRON_SCHEDULE = '0 0 9 * * *';

function setupCron() {
  const task = cron.schedule(CRON_SCHEDULE, () => {
    console.log(`\n⏰ [定时任务触发] 每日9点更新 - ${new Date().toLocaleString('zh-CN')}`);
    updateDashboardData(false);
  }, {
    scheduled: true,
    timezone: 'Asia/Shanghai'
  });
  
  console.log(`✅ [定时任务已注册] 每日上午9:00 (Asia/Shanghai) 自动更新数据`);
  console.log(`   Cron表达式: ${CRON_SCHEDULE}`);
  
  return task;
}

// ========== 启动服务 ==========
function start() {
  // 1. 加载缓存
  loadCache();
  
  // 2. 如果没有数据，立即生成一次
  if (!cacheData.lastUpdate || cacheData.yesterdayMatches.length === 0) {
    console.log('[启动] 首次运行，正在生成初始数据...');
    updateDashboardData(true);
  }
  
  // 3. 设置定时任务
  setupCron();
  
  // 4. 启动HTTP服务
  app.listen(PORT, () => {
    console.log('\n' + '='.repeat(60));
    console.log(`🚀 足球赛道分析仪表盘已启动`);
    console.log(`📅 今日日期: ${formatDate(getToday())}`);
    console.log(`🌐 网页访问: http://localhost:${PORT}/`);
    console.log(`📡 API 接口: http://localhost:${PORT}/api/dashboard`);
    console.log(`🔄 下次更新: 明日上午 9:00 (Asia/Shanghai)`);
    console.log('='.repeat(60) + '\n');
    console.log('提示: 如需立即更新数据，可访问 POST /api/update');
  });
}

start();
