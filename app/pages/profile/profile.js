// pages/profile/profile.js - 精修会员中心 + 真实私域数据
const mock = require('../../utils/mock');
const { request } = require('../../utils/request');

Page({
  data: { user: { nickname: '会员', level: '会员', points: 0, nextLevelPoints: 1000, expires_on: '--' }, pointsRules: mock.pointsRules, myCoupons: 0, myReservations: 0, myOrders: 0 },
  async onShow() {
    try {
      const app = getApp(); await app.ensureSession();
      const [member, assets] = await Promise.all([
        request(`/api/member/points?session_id=${app.globalData.sessionId}`),
        request('/api/member/assets')
      ]);
      this.setData({ user: { nickname: '微信会员', level: member.level, points: member.points, nextLevelPoints: Math.max(1000, member.points + 500), expires_on: member.expires_on }, myCoupons: assets.coupons, myReservations: assets.reservations, myOrders: assets.deal_purchases + assets.tickets });
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  onPointsRule(e) { wx.showToast({ title: e.currentTarget.dataset.text, icon: 'none' }); },
  logout() { wx.removeStorageSync('mallAuth'); Object.assign(getApp().globalData, { token: '', userId: '', sessionId: '', currentPlan: null, planState: null }); wx.reLaunch({ url: '/pages/portal/portal' }); },
  goCoupon() { wx.navigateTo({ url: '/pages/coupon/coupon' }); },
  goReserve() { wx.navigateTo({ url: '/pages/reserve/reserve' }); },
  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); }
});
