// pages/profile/profile.js - 会员个人中心
const mock = require('../../utils/mock');

Page({
  data: {
    user: mock.user,
    pointsRules: mock.pointsRules,
    myCoupons: 2,
    myReservations: 1
  },

  onLoad() {
    this.setData({ user: getApp().globalData.user || mock.user });
  },

  onPointsRule(e) {
    const text = e.currentTarget.dataset.text;
    wx.showToast({ title: text, icon: 'none' });
  },

  goCoupon() { wx.navigateTo({ url: '/pages/coupon/coupon' }); },
  goReserve() { wx.navigateTo({ url: '/pages/reserve/reserve' }); },
  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); },
  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
