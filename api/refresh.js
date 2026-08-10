// Vercel Cron Job 定时调用：每天 UTC 1:00 = Asia/Shanghai 9:00
// 触发 Deploy Hook 重新构建项目，从而刷新所有足球数据静态JSON
export default async function handler(req, res) {
  const hookUrl = process.env.VERCEL_DEPLOY_HOOK_URL;

  if (!hookUrl) {
    return res.status(500).json({
      success: false,
      error: "VERCEL_DEPLOY_HOOK_URL 环境变量未配置，请在 Vercel 项目 Settings -> Environment Variables 中添加"
    });
  }

  try {
    const resp = await fetch(hookUrl, { method: "POST" });
    const status = resp.status;

    // Deploy Hook 返回 200/201/202 都算成功（触发构建）
    if (status >= 200 && status < 300) {
      let body = "";
      try { body = await resp.text(); } catch (_) {}
      return res.status(200).json({
        success: true,
        message: "✅ 每日9点数据刷新已触发（Deploy Hook），Vercel 正在后台重新构建，约2分钟后访问到新数据",
        buildStatus: status,
        ts: new Date().toISOString()
      });
    } else {
      return res.status(502).json({
        success: false,
        error: `Deploy Hook 调用失败: HTTP ${status}`,
        ts: new Date().toISOString()
      });
    }
  } catch (e) {
    return res.status(500).json({
      success: false,
      error: "调用 Deploy Hook 异常: " + e.message,
      ts: new Date().toISOString()
    });
  }
}
