// pages/map/map.js - 2.5D 室内地图 + 路线
const mock = require('../../utils/mock');

// 模拟一条「约会路线」：川渝人家 → 茶颜观色 → 星辰影院 → 甜心甜品
const ROUTE = ['s_01', 's_02', 's_03', 's_04'];

Page({
  data: {
    stores: mock.stores,
    route: ROUTE,
    activeId: '',
    focusStore: null,
    showDetail: false,
    planning: true
  },

  onLoad(query) {
    if (query.focus) {
      const s = { ...mock.stores.find(x => x.name === query.focus) };
      if (s) {
        this.setData({ activeId: s.id, focusStore: s, showDetail: true });
      }
    }
  },

  onStoreTap(e) {
    const store = e.detail.store;
    this.setData({ activeId: store.id, focusStore: store, showDetail: true });
  },

  closeDetail() {
    this.setData({ showDetail: false });
  },

  noop() {},

  reserve() {
    wx.navigateTo({ url: '/pages/reserve/reserve?store=' + (this.data.focusStore && this.data.focusStore.id || '') });
  },

  goPlan() {
    wx.navigateTo({ url: '/pages/plan/plan' });
  }
});
