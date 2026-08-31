// app.js - 商场 AI 私域服务助手 全局入口
// 接队友后端(QD square, 8000)：login()/scan() 在 utils/auth.js；demoMode=false 走真实接口
const auth = require('./utils/auth');

App({
  globalData: {
    user: null,
    mall: null,
    mallId: 'mall_demo',
    token: '',
    userId: '',
    sessionId: '',
    demoMode: false,        // false = 接真实后端；true = 纯 mock（无后端演示）
    wxOnline: true,         // 已配置真实小程序 AppID；自动测试仍强制 mock
    planState: null,
    currentPlan: null
  },

  onLaunch() {
    // 恢复登录态
    const saved = wx.getStorageSync('mallAuth');
    if (saved && saved.token) {
      this.globalData.token = saved.token;
      this.globalData.userId = saved.userId;
      this.globalData.sessionId = saved.sessionId;
      this.globalData.mallId = saved.mallId || 'mall_demo';
      this.globalData.user = this.globalData.user || { nickname: '会员' };
    }
  },

  // 确保已登录并建立会话（供页面调用）
  async ensureSession() {
    if (!this.globalData.token) await auth.login();
    if (!this.globalData.sessionId) await auth.scan();
    return this.globalData;
  },

  setPlanState(next) {
    this.globalData.planState = next;
  }
});
