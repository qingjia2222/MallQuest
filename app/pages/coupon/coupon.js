// pages/coupon/coupon.js - 精修优惠展示 + 真实私域接口
const { request } = require('../../utils/request');
Page({
  data: { deals: [], coupons: [] },
  async onShow() {
    try { const app = getApp(); await app.ensureSession(); const [deals,coupons] = await Promise.all([request(`/api/deals?session_id=${app.globalData.sessionId}`),request(`/api/coupons?session_id=${app.globalData.sessionId}`)]); this.setData({ deals: deals.map(d => ({ ...d, original: Math.round(d.price * 1.3), tag: d.purchased_quantity ? `已购 ${d.purchased_quantity} 份` : '今日私域特惠' })), coupons: coupons.map((c,i) => ({...c,scope:c.store_name||'星河里',color:['#7C3AED','#06B6D4','#F59E0B'][i%3]})) }); }
    catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  async claim(e) {
    const coupon = e.detail.coupon;
    try { const app = getApp(); await request('/api/coupons/claim', { method: 'POST', data: { session_id: app.globalData.sessionId, coupon_id: coupon.id, confirmed: true } }); const idx = this.data.coupons.findIndex(c => c.id === coupon.id); this.setData({ [`coupons[${idx}].claimed`]: true }); wx.showToast({ title: '领取成功' }); }
    catch (err) { wx.showToast({ title: err.message, icon: 'none' }); }
  },
  async buyDeal(e) { try { const app=getApp(); await request('/api/deals/purchase',{method:'POST',data:{session_id:app.globalData.sessionId,deal_id:e.currentTarget.dataset.id,quantity:1,confirmed:true}}); wx.showToast({title:'抢购成功'}); await this.onShow(); } catch(err){wx.showToast({title:err.message,icon:'none'})} }
});
