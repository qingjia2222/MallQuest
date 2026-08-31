// pages/scan/scan.js - 扫码入口页
const { login, scan } = require('../../utils/auth');

Page({
  data: {
    playing: true,
    connected: false
  },

  async onLoad() {
    try {
      await login();
      const data = await scan();
      getApp().globalData.mall = { id: data.mall_id || 'mall_demo', name: data.mall_name || 'QD square' };
      this.setData({ connected: true });
      setTimeout(() => this.enterHome(), 1000);
    } catch (e) {
      wx.showModal({ title: '连接失败', content: e.message || '请确认后端已启动', showCancel: false });
    }
  },

  onParticleDone() {},

  enterHome() {
    wx.reLaunch({ url: '/pages/chat/chat' });
  }
});
