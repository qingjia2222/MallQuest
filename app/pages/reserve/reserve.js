// pages/reserve/reserve.js - 对话式预约 + 后端确认事务
const { request } = require('../../utils/request');
Page({
  data: { stores: [], form: { store: '', time: '19:00', people: 2 }, confirmed: false, reservation: null },
  onLoad(query) { this.initialStore = query.store || ''; },
  async onShow() {
    try { const app = getApp(); await app.ensureSession(); const scene = await request('/api/maps/mall_demo/scene'); const dining = ['川菜','日料','西餐','亲子餐','高端中餐']; const stores = scene.stores.filter(s => dining.indexOf(s.category) >= 0).map(s => ({ ...s, rating: '4.8', waiting: s.queue_minutes || 0 })); this.setData({ stores, 'form.store': this.data.form.store || this.initialStore || '' }); }
    catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  onStore(e) { this.setData({ 'form.store': e.currentTarget.dataset.id }); },
  onTime(e) { this.setData({ 'form.time': e.currentTarget.dataset.t }); },
  onPeople(e) { this.setData({ 'form.people': Number(e.currentTarget.dataset.n) }); },
  async submit() {
    if (!this.data.form.store) return wx.showToast({ title: '请先选餐厅', icon: 'none' });
    try {
      const app = getApp(), store = this.data.stores.find(s => s.id === this.data.form.store);
      if (!store) return wx.showToast({ title: '该店暂不支持餐厅预约', icon: 'none' });
      const data = await request('/api/reservations', { method: 'POST', data: { session_id: app.globalData.sessionId, store_id: store.id, reserved_for: `今晚 ${this.data.form.time}`, people: this.data.form.people, confirmed: true } });
      this.setData({ confirmed: true, reservation: { id: data.reservation_id, store: store.name, floor: store.floor, time: this.data.form.time, people: this.data.form.people } });
    } catch (e) { wx.showModal({ title: '预约失败', content: e.message, showCancel: false }); }
  },
  async cancelReserve() { try { await request(`/api/reservations/${this.data.reservation.id}`, { method: 'DELETE' }); this.setData({ confirmed: false, reservation: null }); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } },
  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
