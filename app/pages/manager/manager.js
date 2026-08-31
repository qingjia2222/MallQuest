const { request } = require('../../utils/request');

Page({
  data: { username:'', password:'', token:'', loggingIn:false, granularities:['day','month','year'], grainLabels:['日度','月度','年度'], grainIndex:1, analytics:null, storeName:'', storeCategory:'', storeFloor:1, created:null },
  field(e) { this.setData({[e.currentTarget.dataset.key]:e.detail.value}); },
  pickGrain(e) { this.setData({grainIndex:Number(e.detail.value)},()=>this.loadAnalytics()); },
  logout() { this.setData({token:'',analytics:null,password:''}); wx.reLaunch({url:'/pages/portal/portal'}); },
  async login() {
    const username=String(this.data.username||'').trim(),password=String(this.data.password||'');
    if(!username||!password) return wx.showModal({title:'请填写账号和密码',content:'请输入完整的管理账号与密码。演示账号为 manager / manager123。',showCancel:false});
    this.setData({username,loggingIn:true});
    try { const auth=await request('/api/auth/web-login',{method:'POST',token:'',data:{username,password}}); this.setData({token:auth.token}); await this.loadAnalytics(); }
    catch(e) { wx.showModal({title:'登录失败',content:e.message,showCancel:false}); }
    finally { this.setData({loggingIn:false}); }
  },
  async loadAnalytics() { const analytics=await request(`/api/manager/analytics?mall_id=mall_demo&granularity=${this.data.granularities[this.data.grainIndex]}`,{token:this.data.token}); const max=Math.max(1,...analytics.series.map(item=>item.footfall)); analytics.series=analytics.series.map(item=>({...item,barWidth:Math.round(item.footfall/max*100)})); this.setData({analytics}); },
  async createStore() { try { const created=await request('/api/manager/stores',{method:'POST',token:this.data.token,data:{mall_id:'mall_demo',name:this.data.storeName,category:this.data.storeCategory,floor:Number(this.data.storeFloor),pos_x:680,pos_y:610}}); this.setData({created}); wx.showToast({title:'编码已创建'}); } catch(e) { wx.showModal({title:'创建失败',content:e.message,showCancel:false}); } }
});
