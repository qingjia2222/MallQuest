// pages/coupon/coupon.js - 精修优惠展示 + 真实私域接口
const { request } = require('../../utils/request');
const COUPONS = [
  { id: 'c1', title: '蜀香小院满 200 减 30', scope: '蜀香小院', color: '#7C3AED' },
  { id: 'c2', title: '礼物研究所满 300 减 50', scope: '礼物研究所', color: '#06B6D4' },
  { id: 'c6', title: '奶茶第二杯半价', scope: '茉语奶茶', color: '#F59E0B' }
];
Page({
  data: { deals: [], coupons: COUPONS.map(c => ({ ...c, claimed: false })) },
  async onShow() {
    try { const app = getApp(); await app.ensureSession(); const deals = await request(`/api/deals?session_id=${app.globalData.sessionId}`); this.setData({ deals: deals.map(d => ({ ...d, original: Math.round(d.price * 1.3), tag: '今日私域特惠' })) }); }
    catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  async claim(e) {
    const coupon = e.detail.coupon;
    try { const app = getApp(); await request('/api/coupons/claim', { method: 'POST', data: { session_id: app.globalData.sessionId, coupon_id: coupon.id, confirmed: true } }); const idx = this.data.coupons.findIndex(c => c.id === coupon.id); this.setData({ [`coupons[${idx}].claimed`]: true }); wx.showToast({ title: '领取成功' }); }
    catch (err) { wx.showToast({ title: err.message, icon: 'none' }); }
  },
  buyDeal(e) { wx.showToast({ title: '演示订单：' + e.currentTarget.dataset.id, icon: 'none' }); }
});
