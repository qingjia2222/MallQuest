const { phoneLogin, phoneRegister, scan } = require('../../utils/auth');

Page({
  data: {
    phone: '11111111111',
    password: '123456',
    authMode: 'login',
    serviceCode: '',
    qrDetected: false,
    connecting: false,
    connected: false,
    playing: false,
    mallName: '星河里',
    sourceText: ''
  },

  onLoad(options) {
    const app = getApp();
    const scene = options && options.scene ? decodeURIComponent(options.scene).trim().toUpperCase() : '';
    const serviceCode = scene || app.globalData.serviceCode || '';
    app.globalData.serviceCode = serviceCode;
    this.setData({ serviceCode, qrDetected: Boolean(serviceCode) });
  },

  field(e) { this.setData({ [e.currentTarget.dataset.key]: e.detail.value }); },
  switchAuth(e) { this.setData({ authMode: e.currentTarget.dataset.mode }); },

  async submitLogin() {
    if (!/^1\d{10}$/.test(this.data.phone)) {
      wx.showToast({ title: '请输入11位手机号', icon: 'none' });
      return;
    }
    if (!this.data.password) {
      wx.showToast({ title: '请输入密码', icon: 'none' });
      return;
    }
    this.setData({ connecting: true, playing: true });
    try {
      const authorize = this.data.authMode === 'register' ? phoneRegister : phoneLogin;
      await authorize(this.data.phone, this.data.password);
      const data = await scan(this.data.serviceCode);
      getApp().globalData.mall = { id: data.mall_id, name: data.mall_name };
      const sourceText = ((data.datasource_connection && data.datasource_connection.sources) || []).map(item => item.label).join(' · ');
      this.setData({ connected: true, mallName: data.mall_name || '星河里', sourceText });
      setTimeout(() => this.enterHome(), 1400);
    } catch (e) {
      this.setData({ connecting: false, playing: false });
      wx.showModal({ title: this.data.authMode === 'register' ? '注册或连接失败' : '登录或连接失败', content: e.message || '请确认后端已启动', showCancel: false });
    }
  },

  onParticleDone() {},
  enterHome() { if (this.data.connected) wx.reLaunch({ url: '/pages/home/home' }); }
});
