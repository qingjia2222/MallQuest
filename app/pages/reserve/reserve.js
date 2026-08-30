// pages/reserve/reserve.js - 对话式预约
const mock = require('../../utils/mock');

Page({
  data: {
    stores: mock.stores.filter(s => s.category === '川菜' || s.category === '火锅'),
    form: { store: '', time: '19:00', people: 2 },
    confirmed: false,
    reservation: null
  },

  onLoad(query) {
    if (query.store) {
      const s = mock.stores.find(x => x.id === query.store);
      this.setData({ 'form.store': s ? s.id : '' });
    }
  },

  onStore(e) { this.setData({ 'form.store': e.currentTarget.dataset.id }); },
  onTime(e) { this.setData({ 'form.time': e.currentTarget.dataset.t }); },
  onPeople(e) { this.setData({ 'form.people': Number(e.currentTarget.dataset.n) }); },

  submit() {
    if (!this.data.form.store) {
      wx.showToast({ title: '请先选餐厅', icon: 'none' });
      return;
    }
    const store = mock.stores.find(s => s.id === this.data.form.store);
    this.setData({
      confirmed: true,
      reservation: { store: store.name, floor: store.floor, time: this.data.form.time, people: this.data.form.people }
    });
    wx.vibrateShort({ type: 'light' });
  },

  cancelReserve() {
    this.setData({ confirmed: false, reservation: null });
  },

  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
