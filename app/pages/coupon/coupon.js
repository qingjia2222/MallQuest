// pages/coupon/coupon.js - 今日特惠与优惠券
const mock = require('../../utils/mock');

Page({
  data: {
    deals: mock.deals,
    coupons: mock.coupons.map(c => ({ ...c, claimed: false }))
  },

  claim(e) {
    const coupon = e.detail.coupon;
    const idx = this.data.coupons.findIndex(c => c.id === coupon.id);
    wx.vibrateShort({ type: 'medium' });
    this.setData({ [`coupons[${idx}].claimed`]: true });
    wx.showToast({ title: '领取成功', icon: 'success' });
  },

  buyDeal(e) {
    const id = e.currentTarget.dataset.id;
    wx.showToast({ title: '已下单 ' + id, icon: 'none' });
  }
});
