// 数据层：球赛数据、裁判分析、模拟数据生成

// 区域联赛配置
const LEAGUES = {
  europe: [
    { id: 'epl', name: '英超联赛', country: '英格兰', flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿' },
    { id: 'laliga', name: '西甲联赛', country: '西班牙', flag: '🇪🇸' },
    { id: 'bundesliga', name: '德甲联赛', country: '德国', flag: '🇩🇪' },
    { id: 'seriea', name: '意甲联赛', country: '意大利', flag: '🇮🇹' },
    { id: 'ligue1', name: '法甲联赛', country: '法国', flag: '🇫🇷' },
    { id: 'ucl', name: '欧冠联赛', country: '欧洲', flag: '🇪🇺' }
  ],
  asia: [
    { id: 'csl', name: '中超联赛', country: '中国', flag: '🇨🇳' },
    { id: 'jleague', name: 'J联赛', country: '日本', flag: '🇯🇵' },
    { id: 'kleague', name: 'K联赛', country: '韩国', flag: '🇰🇷' },
    { id: 'acl', name: '亚冠联赛', country: '亚洲', flag: '🏆' },
    { id: 'apl', name: '沙特联赛', country: '沙特阿拉伯', flag: '🇸🇦' }
  ],
  australia: [
    { id: 'aleague', name: '澳超联赛', country: '澳大利亚', flag: '🇦🇺' },
    { id: 'nzfootball', name: '新西兰超级联赛', country: '新西兰', flag: '🇳🇿' }
  ]
};

// 球队数据库（模拟）
const TEAMS = {
  epl: ['曼联', '曼城', '利物浦', '阿森纳', '切尔西', '热刺', '纽卡斯尔', '布莱顿', '阿斯顿维拉', '西汉姆', '布伦特福德', '埃弗顿'],
  laliga: ['皇家马德里', '巴塞罗那', '马竞', '塞维利亚', '皇家社会', '比利亚雷亚尔', '毕尔巴鄂', '瓦伦西亚', '皇家贝蒂斯'],
  bundesliga: ['拜仁慕尼黑', '多特蒙德', 'RB莱比锡', '勒沃库森', '柏林联盟', '弗赖堡', '法兰克福', '沃尔夫斯堡'],
  seriea: ['国际米兰', 'AC米兰', '尤文图斯', '那不勒斯', '罗马', '拉齐奥', '亚特兰大', '佛罗伦萨'],
  ligue1: ['巴黎圣日耳曼', '马赛', '摩纳哥', '里昂', '里尔', '尼斯', '雷恩'],
  ucl: ['拜仁慕尼黑', '皇家马德里', '曼城', '巴黎圣日耳曼', '巴塞罗那', '国际米兰', '阿森纳', '多特蒙德'],
  csl: ['上海海港', '山东泰山', '上海申花', '北京国安', '成都蓉城', '武汉三镇', '河南队', '浙江队'],
  jleague: ['川崎前锋', '横滨水手', '鹿岛鹿角', '浦和红钻', '名古屋鲸八', '大阪樱花', '东京FC'],
  kleague: ['全北现代', '蔚山现代', '浦项制铁', '首尔FC', '大邱FC', '仁川联'],
  acl: ['上海海港', '川崎前锋', '全北现代', '蔚山现代', '横滨水手', '山东泰山'],
  apl: ['利雅得新月', '吉达联合', '利雅得胜利', '吉达国民', '利雅得青年'],
  aleague: ['悉尼FC', '墨尔本胜利', '西悉尼流浪者', '布里斯班狮吼', '珀斯光荣', '惠灵顿凤凰'],
  nzfootball: ['奥克兰城', '惠灵顿奥林匹克', '坎特伯雷联', '奥克兰联']
};

// 裁判数据库
const REFEREES = [
  { id: 'r001', name: '安东尼·泰勒', country: '英格兰', age: 45 },
  { id: 'r002', name: '迈克尔·奥利弗', country: '英格兰', age: 39 },
  { id: 'r003', name: '安东尼奥·马特乌', country: '西班牙', age: 47 },
  { id: 'r004', name: '克莱芒·蒂尔潘', country: '法国', age: 41 },
  { id: 'r005', name: '丹妮埃莱·奥萨托', country: '意大利', age: 48 },
  { id: 'r006', name: '费利克斯·茨瓦耶', country: '德国', age: 42 },
  { id: 'r007', name: '丹尼·马克列', country: '荷兰', age: 40 },
  { id: 'r008', name: '阿图尔·迪亚斯', country: '葡萄牙', age: 44 },
  { id: 'r009', name: '傅明', country: '中国', age: 40 },
  { id: 'r010', name: '马宁', country: '中国', age: 45 },
  { id: 'r011', name: '佐藤隆治', country: '日本', age: 43 },
  { id: 'r012', name: '金希坤', country: '韩国', age: 42 },
  { id: 'r013', name: '克里斯·比斯', country: '澳大利亚', age: 41 }
];

function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pickN(arr, n) {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

function getYesterday() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d;
}

function getToday() {
  return new Date();
}

function formatDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

// 生成裁判历史记录（前5场）
function generateRefereeHistory(referee, count = 5) {
  const history = [];
  for (let i = 0; i < count; i++) {
    const yellowCards = rand(2, 8);
    const redCards = rand(0, 2);
    const penalties = rand(0, 2);
    const fouls = rand(15, 35);
    const varChecks = rand(0, 5);
    
    // 发牌倾向指数 (黄牌+红牌*3) / 比赛场次基准
    const cardIndex = yellowCards + redCards * 3;
    
    history.push({
      matchNumber: count - i,
      date: formatDate(new Date(getYesterday().getTime() - (i + 1) * 86400000)),
      league: pick(LEAGUES.europe.concat(LEAGUES.asia)).name,
      yellowCards,
      redCards,
      penalties,
      fouls,
      varChecks,
      cardIndex
    });
  }
  return history;
}

// 分析裁判风格
function analyzeRefereeStyle(referee, history) {
  const avgYellow = history.reduce((s, h) => s + h.yellowCards, 0) / history.length;
  const avgRed = history.reduce((s, h) => s + h.redCards, 0) / history.length;
  const avgFouls = history.reduce((s, h) => s + h.fouls, 0) / history.length;
  const avgPenalties = history.reduce((s, h) => s + h.penalties, 0) / history.length;
  const avgCardIndex = history.reduce((s, h) => s + h.cardIndex, 0) / history.length;
  const avgVar = history.reduce((s, h) => s + h.varChecks, 0) / history.length;
  
  // 严格度评分 0-100
  let strictnessScore = 0;
  if (avgYellow >= 5) strictnessScore += 35;
  else if (avgYellow >= 4) strictnessScore += 25;
  else if (avgYellow >= 3) strictnessScore += 15;
  else strictnessScore += 5;
  
  if (avgRed >= 0.8) strictnessScore += 25;
  else if (avgRed >= 0.4) strictnessScore += 15;
  else if (avgRed >= 0.2) strictnessScore += 8;
  else strictnessScore += 2;
  
  if (avgFouls >= 28) strictnessScore += 20;
  else if (avgFouls >= 22) strictnessScore += 12;
  else if (avgFouls >= 18) strictnessScore += 6;
  else strictnessScore += 2;
  
  if (avgPenalties >= 0.8) strictnessScore += 20;
  else if (avgPenalties >= 0.4) strictnessScore += 12;
  else strictnessScore += 5;
  
  let style, styleDesc, keyTraits;
  
  if (strictnessScore >= 75) {
    style = '严格型';
    styleDesc = '该裁判倾向于严格执法，对犯规零容忍。比赛中频繁出示黄牌，红牌概率较高。球队需注意动作规范，避免过激对抗。';
    keyTraits = ['出牌频率高', '对恶意犯规零容忍', '点球判罚果断', 'VAR介入频繁'];
  } else if (strictnessScore >= 55) {
    style = '偏严格型';
    styleDesc = '该裁判执法相对严格，对明显犯规会及时出牌。在关键场次或强强对话中尺度可能收紧。';
    keyTraits = ['关键战出牌多', '对危险动作敏感', '偶有点球判罚', '中规中矩的执法'];
  } else if (strictnessScore >= 35) {
    style = '平衡型';
    styleDesc = '该裁判执法尺度平衡，既保证比赛流畅性又不会纵容犯规。鼓励合理对抗，出牌较为克制。';
    keyTraits = ['鼓励对抗', '出牌谨慎', '比赛流畅度高', '点球判罚较少'];
  } else {
    style = '鼓励对抗型';
    styleDesc = '该裁判倾向于让比赛流畅进行，对身体对抗容忍度高。出牌非常克制，比赛节奏快，对抗激烈。';
    keyTraits = ['极少出牌', '鼓励身体对抗', '比赛中断少', '极少判罚点球'];
  }
  
  return {
    referee,
    history,
    statistics: {
      avgYellow: avgYellow.toFixed(1),
      avgRed: avgRed.toFixed(2),
      avgFouls: avgFouls.toFixed(1),
      avgPenalties: avgPenalties.toFixed(2),
      avgCardIndex: avgCardIndex.toFixed(1),
      avgVar: avgVar.toFixed(1),
      strictnessScore: Math.round(strictnessScore)
    },
    style,
    styleDesc,
    keyTraits
  };
}

// 生成比赛对比数据（Opta/StatsBomb风格）
function generateMatchStats(homeTeam, awayTeam) {
  const homeScore = rand(0, 4);
  const awayScore = rand(0, 3);
  const homePossession = rand(35, 68);
  
  return {
    score: { home: homeScore, away: awayScore },
    possession: { home: homePossession, away: 100 - homePossession },
    shots: { home: rand(6, 22), away: rand(5, 18) },
    shotsOnTarget: { home: rand(2, 9), away: rand(1, 7) },
    xG: { 
      home: (rand(5, 30) / 10).toFixed(2), 
      away: (rand(4, 28) / 10).toFixed(2) 
    },
    passes: { 
      home: rand(280, 650), 
      away: rand(250, 580) 
    },
    passAccuracy: {
      home: `${rand(72, 90)}%`,
      away: `${rand(70, 88)}%`
    },
    tackles: { home: rand(12, 28), away: rand(10, 25) },
    interceptions: { home: rand(6, 20), away: rand(5, 18) },
    fouls: { home: rand(8, 22), away: rand(7, 20) },
    corners: { home: rand(2, 10), away: rand(2, 9) },
    yellowCards: { home: rand(0, 4), away: rand(0, 4) },
    redCards: { home: rand(0, 1), away: rand(0, 1) },
    offsides: { home: rand(1, 6), away: rand(0, 5) },
    saves: { home: rand(1, 6), away: rand(1, 5) }
  };
}

// 生成关键事件
function generateKeyEvents(homeTeam, awayTeam, stats) {
  const events = [];
  let minute = 1;
  
  // 进球事件
  for (let i = 0; i < stats.score.home; i++) {
    minute = rand(minute, Math.min(90, minute + 20));
    events.push({
      minute,
      type: 'goal',
      team: 'home',
      teamName: homeTeam,
      description: `${homeTeam} 进球！精彩射门得分`
    });
    minute = Math.min(90, minute + 5);
  }
  minute = 1;
  for (let i = 0; i < stats.score.away; i++) {
    minute = rand(minute, Math.min(90, minute + 20));
    events.push({
      minute,
      type: 'goal',
      team: 'away',
      teamName: awayTeam,
      description: `${awayTeam} 进球！扳平/反超比分`
    });
    minute = Math.min(90, minute + 5);
  }
  
  // 黄牌事件
  const totalYellow = stats.yellowCards.home + stats.yellowCards.away;
  for (let i = 0; i < totalYellow; i++) {
    const isHome = Math.random() < stats.yellowCards.home / totalYellow;
    events.push({
      minute: rand(1, 90),
      type: 'yellow',
      team: isHome ? 'home' : 'away',
      teamName: isHome ? homeTeam : awayTeam,
      description: `${isHome ? homeTeam : awayTeam} 球员犯规吃到黄牌`
    });
  }
  
  // 红牌事件
  if (stats.redCards.home > 0) {
    events.push({
      minute: rand(30, 85),
      type: 'red',
      team: 'home',
      teamName: homeTeam,
      description: `${homeTeam} 球员严重犯规直接红牌罚下`
    });
  }
  if (stats.redCards.away > 0) {
    events.push({
      minute: rand(30, 85),
      type: 'red',
      team: 'away',
      teamName: awayTeam,
      description: `${awayTeam} 球员两黄变一红被罚下`
    });
  }
  
  return events.sort((a, b) => a.minute - b.minute);
}

// 生成比赛分析结论
function generateMatchAnalysis(homeTeam, awayTeam, stats, refereeAnalysis) {
  const insights = [];
  
  // 结果分析
  if (stats.score.home > stats.score.away) {
    insights.push(`${homeTeam} 主场取胜，实际进球 ${stats.score.home} vs xG ${stats.xG.home}，${parseFloat(stats.xG.home) < stats.score.home ? '把握机会能力超强' : '进攻效率符合预期'}`);
  } else if (stats.score.home < stats.score.away) {
    insights.push(`${awayTeam} 客场奏凯，反击效率极高，xG ${stats.xG.away} 支撑了最终比分`);
  } else {
    insights.push(`双方握手言和，${parseFloat(stats.xG.home) + parseFloat(stats.xG.away) > 2.5 ? '创造出大量机会但临门一脚欠佳' : '场面胶着机会寥寥'}`);
  }
  
  // 控球分析
  if (stats.possession.home >= 60) {
    insights.push(`${homeTeam} 控球率达到 ${stats.possession.home}%，主导了比赛节奏，但${stats.shotsOnTarget.home < 5 ? '射门转化率偏低' : '有效射门质量不错'}`);
  } else if (stats.possession.away >= 60) {
    insights.push(`${awayTeam} 反客为主掌控场面，传球 ${stats.passes.away} 次展现了传控功底`);
  } else {
    insights.push(`双方控球率相对均衡，场面开放对攻激烈`);
  }
  
  // 裁判影响分析
  if (refereeAnalysis.statistics.strictnessScore >= 70) {
    insights.push(`裁判执法偏严（严格度 ${refereeAnalysis.statistics.strictnessScore}分），全场共出示 ${stats.yellowCards.home + stats.yellowCards.away} 黄${stats.redCards.home + stats.redCards.away}红，直接影响了比赛节奏`);
  } else if (refereeAnalysis.statistics.strictnessScore <= 35) {
    insights.push(`裁判鼓励对抗（严格度 ${refereeAnalysis.statistics.strictnessScore}分），比赛流畅度高，犯规 ${stats.fouls.home + stats.fouls.away} 次仅出示 ${stats.yellowCards.home + stats.yellowCards.away} 张黄牌`);
  } else {
    insights.push(`裁判执法尺度平衡，比赛中规中矩`);
  }
  
  // 犯规与对抗
  if (stats.fouls.home + stats.fouls.away >= 32) {
    insights.push(`本场比赛对抗激烈，双方共计 ${stats.fouls.home + stats.fouls.away} 次犯规，拼抢强度拉满`);
  }
  
  return insights;
}

// 生成T-1赛事（昨日赛事）
function generateYesterdayMatches() {
  const matches = [];
  const allLeagues = [
    ...LEAGUES.europe.map(l => ({ ...l, region: 'europe' })),
    ...LEAGUES.asia.map(l => ({ ...l, region: 'asia' })),
    ...LEAGUES.australia.map(l => ({ ...l, region: 'australia' }))
  ];
  
  // 从每个区域选一些联赛，每个联赛生成1-2场
  const selectedLeagues = pickN(allLeagues, 8);
  
  selectedLeagues.forEach(league => {
    const teams = TEAMS[league.id] || TEAMS[Object.keys(TEAMS)[0]];
    const matchCount = rand(1, 2);
    
    for (let m = 0; m < matchCount; m++) {
      const [homeTeam, awayTeam] = pickN(teams, 2);
      const referee = pick(REFEREES);
      const stats = generateMatchStats(homeTeam, awayTeam);
      const refHistory = generateRefereeHistory(referee, 5);
      const refAnalysis = analyzeRefereeStyle(referee, refHistory);
      const keyEvents = generateKeyEvents(homeTeam, awayTeam, stats);
      const analysis = generateMatchAnalysis(homeTeam, awayTeam, stats, refAnalysis);
      
      const hour = rand(19, 22);
      const minute = [0, 15, 30, 45][rand(0, 3)];
      
      matches.push({
        id: `y-${Date.now()}-${matches.length}`,
        date: formatDate(getYesterday()),
        time: `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`,
        league: league,
        region: league.region,
        homeTeam,
        awayTeam,
        venue: `${homeTeam}主场`,
        stats,
        refereeAnalysis: refAnalysis,
        keyEvents,
        analysis
      });
    }
  });
  
  return matches;
}

// 生成今日预告
function generateTodayPreviews() {
  const previews = [];
  const allLeagues = [
    ...LEAGUES.europe.map(l => ({ ...l, region: 'europe' })),
    ...LEAGUES.asia.map(l => ({ ...l, region: 'asia' })),
    ...LEAGUES.australia.map(l => ({ ...l, region: 'australia' }))
  ];
  
  const selectedLeagues = pickN(allLeagues, 10);
  
  selectedLeagues.forEach(league => {
    const teams = TEAMS[league.id] || TEAMS[Object.keys(TEAMS)[0]];
    const matchCount = rand(1, 2);
    
    for (let m = 0; m < matchCount; m++) {
      const [homeTeam, awayTeam] = pickN(teams, 2);
      const referee = pick(REFEREES);
      const refHistory = generateRefereeHistory(referee, 5);
      const refAnalysis = analyzeRefereeStyle(referee, refHistory);
      
      const hour = rand(18, 22);
      const minute = [0, 15, 30, 45][rand(0, 3)];
      
      // 生成比赛特点/看点
      const features = [];
      const featurePool = [
        '强强对话，争夺联赛榜首',
        '保级关键战，双方抢分心切',
        '德比大战，历史恩怨看点十足',
        '主场龙对阵客场龙，谁能更胜一筹',
        '近期状态火热，连胜势头能否延续',
        '欧战资格关键六分战',
        '新援首秀，期待磨合效果',
        '主帅对决，战术博弈引人关注',
        '进攻大战，双方防守皆有漏洞',
        '防守对决，预测低比分收场'
      ];
      const selectedFeatures = pickN(featurePool, rand(2, 3));
      features.push(...selectedFeatures);
      
      // 根据裁判风格添加裁判相关看点
      if (refAnalysis.style === '严格型') {
        features.push(`裁判${referee.name}执法偏严，双方需注意动作规范`);
      } else if (refAnalysis.style === '鼓励对抗型') {
        features.push(`裁判${referee.name}鼓励对抗，比赛预计节奏快拼抢激烈`);
      } else {
        features.push(`裁判${referee.name}执法平衡，比赛流畅度值得期待`);
      }
      
      previews.push({
        id: `t-${Date.now()}-${previews.length}`,
        date: formatDate(getToday()),
        time: `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`,
        league: league,
        region: league.region,
        homeTeam,
        awayTeam,
        venue: `${homeTeam}主场`,
        refereeAnalysis: refAnalysis,
        features,
        predictedDifficulty: rand(1, 5), // 1-5星难度/激烈程度
        homeRecentForm: pickN(['胜', '平', '负', '胜', '平', '负', '胜'], 5),
        awayRecentForm: pickN(['胜', '平', '负', '胜', '平', '负', '胜'], 5),
        h2hLast5: {
          homeWins: rand(0, 4),
          draws: rand(0, 3),
          awayWins: rand(0, 4)
        }
      });
    }
  });
  
  return previews;
}

// 生成推送消息摘要
function generatePushDigest(yesterdayMatches, todayPreviews) {
  const regions = { europe: '欧洲', asia: '亚洲', australia: '澳洲' };
  
  // 昨日精彩赛事
  const yesterdaySummary = yesterdayMatches.slice(0, 3).map(m => {
    const winner = m.stats.score.home > m.stats.score.away ? m.homeTeam :
                   m.stats.score.home < m.stats.score.away ? m.awayTeam : '平局';
    return `${m.league.flag} ${m.league.name}：${m.homeTeam} ${m.stats.score.home}-${m.stats.score.away} ${m.awayTeam}（${winner === '平局' ? '战平' : winner + '获胜'}）`;
  }).join('；');
  
  // 今日焦点
  const todaySummary = todayPreviews.slice(0, 3).map(m => {
    return `${m.league.flag} ${m.homeTeam} vs ${m.awayTeam}（${m.features[0]}）`;
  }).join('；');
  
  return {
    title: `⚽ 足球赛道日报 - ${formatDate(getToday())}`,
    yesterdaySummary,
    todaySummary,
    yesterdayCount: yesterdayMatches.length,
    todayCount: todayPreviews.length,
    fullReport: true
  };
}

module.exports = {
  LEAGUES,
  REFEREES,
  formatDate,
  getYesterday,
  getToday,
  generateYesterdayMatches,
  generateTodayPreviews,
  generateRefereeHistory,
  analyzeRefereeStyle,
  generatePushDigest
};
