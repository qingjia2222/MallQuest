// pages/map/map.js - 甲方 2.5D 视觉 + 乙方真实商场接口
const { request } = require('../../utils/request');

Page({
  data: { stores: [], route: [], parking: { areas: [], total_free: 0, total: 0 }, activeId: '', focusStore: null, showDetail: false },
  onLoad(query) { this.focusName = query.focus || ''; },
  async onShow() {
    try {
      const app = getApp(); await app.ensureSession();
      const [scene, parking] = await Promise.all([request('/api/maps/mall_demo/scene'), request(`/api/parking?session_id=${app.globalData.sessionId}`)]);
      const stores = scene.stores.map(s => ({ ...s, pos_x: s.pos_x / 10, pos_y: s.pos_y / 7.6, rating: '4.8', waiting: s.queue_minutes || 0, desc: s.service_tags || '商户服务信息待更新' }));
      const current = app.globalData.currentPlan || (app.globalData.planState && app.globalData.planState.current);
      const route = current && current.itinerary ? current.itinerary.map(s => s.id) : [];
      const total = parking.areas.reduce((sum, area) => sum + area.total, 0);
      const focusStore = this.focusName ? stores.find(s => s.name.indexOf(this.focusName) >= 0 || this.focusName.indexOf(s.name) >= 0) : null;
      this.setData({ stores, route, parking: { ...parking, total }, activeId: focusStore ? focusStore.id : '', focusStore, showDetail: Boolean(focusStore) });
    } catch (e) { wx.showModal({ title: '地图加载失败', content: e.message || '请确认后端已启动', showCancel: false }); }
  },
  async onStoreTap(e) {
    const base = e.detail.store;
    try {
      const live = await request(`/api/stores/${base.id}/public-status?mall_id=mall_demo`);
      this.setData({ activeId: base.id, focusStore: { ...base, ...live, waiting: live.queue_minutes || 0, desc: live.service_tags || base.desc }, showDetail: true });
    } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); }
  },
  closeDetail() { this.setData({ showDetail: false }); },
  noop() {},
  reserve() { wx.navigateTo({ url: '/pages/reserve/reserve?store=' + (this.data.focusStore && this.data.focusStore.id || '') }); },
  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); }
});
