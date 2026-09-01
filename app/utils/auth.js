const { request } = require('./request');

function saveAuth(auth) {
  const app = getApp();
  Object.assign(app.globalData, { token: auth.token, userId: auth.user_id, loginChannel: auth.login_channel });
  wx.setStorageSync('mallAuth', { token: auth.token, userId: auth.user_id, loginChannel: auth.login_channel });
}

async function phoneLogin(phone, password) {
  const auth = await request('/api/auth/phone-login', { method: 'POST', token: '', data: { phone, password } });
  saveAuth(auth);
  return auth;
}

async function phoneRegister(phone, password) {
  const auth = await request('/api/auth/phone-register', { method: 'POST', token: '', data: { phone, password } });
  saveAuth(auth);
  return auth;
}

async function wxLogin() {
  const app = getApp();
  let code = 'mock-demo';
  if (app.globalData.wxOnline && wx.login) {
    const result = await new Promise((resolve, reject) => wx.login({ success: resolve, fail: reject }));
    if (result.code) code = result.code;
  }
  const auth = await request('/api/auth/wx-login', { method: 'POST', token: '', data: { code } });
  saveAuth(auth);
  return auth;
}

async function scan(serviceCode) {
  const app = getApp();
  const data = await request('/api/scan', {
    method: 'POST',
    data: {
      mall_id: serviceCode ? null : app.globalData.mallId,
      service_code: serviceCode || app.globalData.serviceCode || null
    }
  });
  Object.assign(app.globalData, { sessionId: data.session_id, mallId: data.mall_id, serviceCode: data.service_code || '' });
  wx.setStorageSync('mallAuth', { token: app.globalData.token, userId: app.globalData.userId, loginChannel: app.globalData.loginChannel, sessionId: data.session_id, mallId: data.mall_id, serviceCode: data.service_code || '' });
  return data;
}

module.exports = { phoneLogin, phoneRegister, wxLogin, scan };
