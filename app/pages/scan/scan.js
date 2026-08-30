// pages/scan/scan.js - 扫码入口页
const mock = require('../../utils/mock');

Page({
  data: {
    playing: true,
    connected: false
  },

  onLoad() {
    // demo：模拟扫码解析 mall_id 成功
    setTimeout(() => {
      // 把商场信息写入全局
      const app = getApp();
      app.globalData.mall = mock.mall;
      this.setData({ connected: true });
      setTimeout(() => this.enterHome(), 1500);
    }, 1200);
  },

  // 支持真机扫码入口（接后端后调用 /api/scan）
  onScan() {
    wx.scanCode({
      success: (res) => {
        // res.result 含 mall_id，解析后进入
        this.enterHome();
      },
      fail: () => this.enterHome()
    });
  },

  onParticleDone() {},

  enterHome() {
    wx.reLaunch({ url: '/pages/chat/chat' });
  }
});
