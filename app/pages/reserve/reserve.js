// pages/reserve/reserve.js - 对话式预约 + 后端确认事务
const { request } = require('../../utils/request');
Page({
  data: { stores: [], filteredStores: [], floorOptions: ['全部楼层'], floorIndex: 0, searchKeyword: '', storeLoading: true, reservationList: [], form: { store: '', time: '19:00', people: 2 }, confirmed: false, reservation: null, editVisible:false, editReservation:null, editTime:'19:00', editPeople:2 },
  onLoad(query) { this.initialStore = query.store || ''; },
  async onShow() {
    try {
      const app = getApp(); await app.ensureSession();
      // 与 Web 和对话共用后端的可预约店铺读模型，前端不再自行推断资格。
      const stores = (await request(`/api/stores?session_id=${app.globalData.sessionId}&reservable_only=true`)).map(s => ({ ...s, rating: '4.8', waiting: s.queue_minutes || 0 }));
      const requested = this.data.form.store || this.initialStore || '';
      const selected = stores.some(s => s.id === requested) ? requested : (stores[0] ? stores[0].id : '');
      const floorOptions = ['全部楼层', ...new Set(stores.map(s => `${s.floor}F`).filter(v => v !== 'undefinedF' && v !== 'nullF'))];
      this.setData({ stores, filteredStores: stores, floorOptions, floorIndex: 0, searchKeyword: '', storeLoading: false, 'form.store': selected });
      await this.loadReservations();
    }
    catch (e) { this.setData({storeLoading:false}); wx.showToast({ title: e.message, icon: 'none' }); }
  },
  onStore(e) { this.setData({ 'form.store': e.currentTarget.dataset.id }); },
  onFloorFilter(e) { this.setData({ floorIndex: Number(e.detail.value) }, () => this.applyStoreFilters()); },
  onSearch(e) { this.setData({ searchKeyword: e.detail.value || '' }, () => this.applyStoreFilters()); },
  clearSearch() { this.setData({ searchKeyword: '' }, () => this.applyStoreFilters()); },
  applyStoreFilters() {
    const floor = this.data.floorOptions[this.data.floorIndex] || '全部楼层';
    const keyword = String(this.data.searchKeyword || '').trim().toLocaleLowerCase();
    const filteredStores = this.data.stores.filter(s => {
      const matchesFilter = floor === '全部楼层' || `${s.floor}F` === floor;
      const haystack = `${s.name || ''} ${s.category || ''} ${s.floor || ''}F`.toLocaleLowerCase();
      return matchesFilter && (!keyword || haystack.includes(keyword));
    });
    this.setData({ filteredStores });
  },
  onTime(e) { this.setData({ 'form.time': e.currentTarget.dataset.t }); },
  onCustomTime(e) { this.setData({ 'form.time': e.detail.value }); },
  onPeople(e) { this.setData({ 'form.people': Number(e.currentTarget.dataset.n) }); },
  onPeopleInput(e) { this.setData({ 'form.people': Number(e.detail.value) }); },
  async submit() {
    if (!this.data.form.store) return wx.showToast({ title: '请先选餐厅', icon: 'none' });
    if (!Number.isInteger(this.data.form.people) || this.data.form.people < 1 || this.data.form.people > 50) return wx.showToast({ title: '人数请填写 1 到 50', icon: 'none' });
    try {
      const app = getApp(), store = this.data.stores.find(s => s.id === this.data.form.store);
      if (!store) return wx.showToast({ title: '该店暂不支持餐厅预约', icon: 'none' });
      const data = await request('/api/reservations', { method: 'POST', data: { session_id: app.globalData.sessionId, store_id: store.id, reserved_for: `今晚 ${this.data.form.time}`, people: this.data.form.people, confirmed: true } });
      this.setData({ confirmed: true, reservation: { id: data.reservation_id, store: store.name, floor: store.floor, time: this.data.form.time, people: this.data.form.people } });
      await this.loadReservations();
    } catch (e) { wx.showModal({ title: '预约失败', content: e.message, showCancel: false }); }
  },
  async loadReservations() {
    try {
      const rows = await request('/api/reservations');
      const labels = { confirmed: '已预约', queued: '已排号', cancelled: '已取消' };
      this.setData({ reservationList: (rows || []).map(item => ({ ...item, statusText: labels[item.status] || item.status })) });
    } catch (e) { wx.showToast({ title: e.message || '预约记录加载失败', icon: 'none' }); }
  },
  editExisting(e) {
    const item=this.data.reservationList.find(row=>row.id===e.currentTarget.dataset.id);if(!item)return;
    const match=String(item.reserved_for||'').match(/(\d{1,2})(?::|点)(\d{2})?/);
    const time=match?`${String(Number(match[1])).padStart(2,'0')}:${String(Number(match[2]||0)).padStart(2,'0')}`:'19:00';
    this.setData({editVisible:true,editReservation:item,editTime:time,editPeople:Number(item.people)||2});
  },
  closeEdit(){this.setData({editVisible:false,editReservation:null});},
  onEditTime(e){this.setData({editTime:e.detail.value});},
  onEditPeople(e){this.setData({editPeople:Number(e.detail.value)});},
  async saveEdit(){
    const item=this.data.editReservation,people=this.data.editPeople;if(!item)return;
    if(!Number.isInteger(people)||people<1||people>50)return wx.showToast({title:'人数请填写 1 到 50',icon:'none'});
    try{await request(`/api/reservations/${item.id}`,{method:'PATCH',data:{reserved_for:`今晚 ${this.data.editTime}`,people,confirmed:true}});this.closeEdit();await this.loadReservations();wx.showToast({title:'预约已修改'});}
    catch(e){wx.showModal({title:'修改失败',content:e.message,showCancel:false});}
  },
  cancelExisting(e){
    const item=this.data.reservationList.find(row=>row.id===e.currentTarget.dataset.id);if(!item)return;
    wx.showModal({title:'取消预约？',content:`确认取消 ${item.store_name||item.store_id} 的预约吗？`,success:async res=>{if(!res.confirm)return;try{await request(`/api/reservations/${item.id}`,{method:'DELETE'});await this.loadReservations();wx.showToast({title:'预约已取消'});}catch(err){wx.showModal({title:'取消失败',content:err.message,showCancel:false});}}});
  },
  noop(){},
  cancelReserve() { const item=this.data.reservation;if(!item)return;wx.showModal({title:'取消预约？',content:`确认取消 ${item.store} 的预约吗？`,success:async res=>{if(!res.confirm)return;try { await request(`/api/reservations/${item.id}`, { method: 'DELETE' }); this.setData({ confirmed: false, reservation: null }); await this.loadReservations(); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }}}); },
  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
