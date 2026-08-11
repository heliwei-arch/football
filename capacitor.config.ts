import type { CapacitorConfig } from '@capacitor/cli';

/**
 * FT早知道 · Capacitor 移动端打包配置
 * - 壳：纯WebView加载 file://android_asset/public/index.html （本地静态资源，离线可用）
 * - ⚡立即更新按钮会在file协议下被前端代码自动隐藏（无后端API）
 * - 数据更新：每日9点重新运行 python3 generate_static.py → npm run cap:sync → 重新编译App（或发布新版本到应用市场）
 */
const config: CapacitorConfig = {
  appId: 'com.bytedance.ft.zazao',
  appName: 'FT早知道',
  webDir: 'public',
  bundledWebRuntime: false,
  // server: 不配置！直接打包本地public资源进APK/IPA（离线可用）
  // 如果想要"联网看最新Pages数据"，把下面注释取消（App壳变浏览器，首次需要联网）：
  // server: {
  //   url: 'https://heliwei-arch.github.io/football/',
  //   cleartext: false,
  //   allowNavigation: ['heliwei-arch.github.io', '*.dongqiudi.com']
  // },
  android: {
    allowMixedContent: true,
    androidXEnabled: true,
    minSdkVersion: 24,
    buildOptions: {
      signingType: 'apk'
    }
  },
  ios: {
    contentInset: 'automatic',
    scheme: 'ftzazao'
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      launchAutoHide: true,
      backgroundColor: '#0f172a',
      showSpinner: false,
      splashFullScreen: true
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0f172a'
    },
    CapacitorCookies: { enabled: true },
    CapacitorHttp: { enabled: true }
  }
};

export default config;
