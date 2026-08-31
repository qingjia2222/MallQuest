const { request } = require('../../utils/request');

Page({
  data: { stores: [], route: [], activeId: '', focusStore: null, showDetail: false, loading: true },
  async onShow() {
    try {
      const app = getApp(); await app.ensureSession();
      const scene = await request('/api/maps/mall_demo/scene');
      const stores = (scene.stores || []).map(s => ({ ...s, pos_x: s.pos_x / 10, pos_y: s.pos_y / 7.6, waiting: s.queue_minutes || 0 }));
      this.setData({ stores, loading: false });
    } catch (e) { this.setData({ loading: false }); wx.showToast({ title: e.message || '店铺加载失败', icon: 'none' }); }
  },
  async onStoreTap(e) {
    const base = e.detail && e.detail.store ? e.detail.store : e.currentTarget.dataset.store;
    try {
      const live = await request(`/api/stores/${base.id}/public-status?mall_id=mall_demo`);
      this.setData({ activeId: base.id, focusStore: { ...base, ...live, waiting: live.queue_minutes || 0 }, showDetail: true });
    } catch (err) { wx.showToast({ title: err.message || '查询失败', icon: 'none' }); }
  },
  closeDetail() { this.setData({ showDetail: false }); },
  noop() {},
  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
