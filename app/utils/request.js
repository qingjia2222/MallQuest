// utils/request.js - 网络请求封装（统一解包 response_envelope）
// 【接后端提醒】当前 demoMode=true 时，页面直接读 utils/mock 数据；
// 关闭演示模式后，把这些调用切到真实接口即可，见下方 <to-fetch> 注释。

// 真机与电脑必须处于同一 Wi-Fi。当前开发机 WLAN 地址为 172.16.16.202；
// IP 变化时运行项目根目录 configure_mini_lan.ps1 自动刷新此文件。
const BASE_URL = 'http://172.16.16.202:8000';

/**
 * 发起请求并解包 {code, message, data}。
 * 用于“接后端后”替换 mock 的调用。现在先保留，不会被用。
 *
 * @param {string} path  如 '/chat'
 * @param {object} options { method, data, header }
 * @returns {Promise<any>} 解包后的 data
 */
function request(path, { method = 'GET', data = {}, header = {}, token } = {}) {
  return new Promise((resolve, reject) => {
    const activeToken = token === undefined ? getApp().globalData.token : token;
    wx.request({
      url: BASE_URL + path,
      method,
      data,
      header: {
        'content-type': 'application/json',
        ...(activeToken ? { Authorization: `Bearer ${activeToken}` } : {}),
        ...header
      },
      success(res) {
        const body = res.data;
        if (res.statusCode >= 200 && res.statusCode < 300 && body && body.code === 0) {
          resolve(body.data);
        } else {
          const detail = body && body.detail;
          const detailMessage = Array.isArray(detail) && detail[0]
            ? `${(detail[0].loc || []).slice(-1)[0] || '参数'}：${detail[0].msg || '格式不正确'}`
            : (typeof detail === 'string' ? detail : '');
          reject(Object.assign(new Error(body && body.message || detailMessage || '请求失败'), { code: body && body.code }));
        }
      },
      fail: reject
    });
  });
}

// 【接后端提醒】以下为规划好的真实接口，待填：
// 对话：   POST /chat   { mallId, message }             -> reply + cards
// 规划：   POST /plan/date   { mallId, text }           -> plan_state
// 路线：   GET  /plan/route                              -> nodes + segments
// 确认：   POST /plan/confirm { decision }              -> 驱动状态
// 实时：   GET  /plan/live-status (SSE)                 -> store 状态
// 停车：   GET  /parking                                 -> parking
// 积分：   GET  /member/points                           -> points
// 领券：   POST /coupons/claim { couponId }             -> 券码
// 预约：   POST /reservations { storeId, time, seats }  -> 预约单

module.exports = { request, BASE_URL };
