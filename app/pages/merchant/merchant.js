const { request } = require('../../utils/request');

Page({
  data: { storeCode:'', password:'123456', authMode:'login', token:'', store:null, loggingIn:false, statuses:['open','busy','closed'], statusLabels:['正常营业','客流繁忙','暂停营业'], statusIndex:0, queueMinutes:0, seatsAvailable:0, offerType:'deal', dealTitle:'', dealPrice:'', dealStock:'', couponTitle:'', couponValue:'', couponMinimum:'', couponStock:'' },
  code(e) { this.setData({ storeCode:e.detail.value }); },
  field(e) { this.setData({ [e.currentTarget.dataset.key]:e.detail.value }); },
  switchAuth(e) { this.setData({authMode:e.currentTarget.dataset.mode}); },
  pickStatus(e) { this.setData({ statusIndex:Number(e.detail.value) }); },
  chooseOfferType(e) { this.setData({ offerType:e.currentTarget.dataset.type }); },
  logout() { this.setData({token:'',store:null,storeCode:''}); wx.reLaunch({url:'/pages/portal/portal'}); },
  async login() {
    const storeCode=String(this.data.storeCode||'').trim().toUpperCase();
    if(!storeCode) return wx.showModal({title:'请填写店铺编码',content:'请输入商场管理者创建的店铺编码，例如 QD-S01-DEMO。',showCancel:false});
    if(String(this.data.password||'').length<6) return wx.showModal({title:'请填写密码',content:'密码长度至少为6位。',showCancel:false});
    this.setData({storeCode,loggingIn:true});
    try { const path=this.data.authMode==='register'?'/api/merchant/auth/register':'/api/merchant/auth/store-code'; const auth=await request(path,{method:'POST',data:{store_code:storeCode,password:this.data.password},token:''}); this.setData({token:auth.token}); await this.load(); }
    catch(e) { wx.showModal({title:this.data.authMode==='register'?'注册失败':'登录失败',content:e.message,showCancel:false}); }
    finally { this.setData({loggingIn:false}); }
  },
  async load() { const store=await request('/api/merchant/store',{token:this.data.token}),index=Math.max(0,this.data.statuses.indexOf(store.live_open_status)); this.setData({store,statusIndex:index,queueMinutes:store.live_queue_minutes,seatsAvailable:store.live_seats_available}); },
  async updateStatus() { try { const store=await request('/api/merchant/store/status',{method:'PATCH',token:this.data.token,data:{open_status:this.data.statuses[this.data.statusIndex],queue_minutes:Number(this.data.queueMinutes),seats_available:Number(this.data.seatsAvailable)}}); this.setData({store}); wx.showToast({title:'状态已同步'}); } catch(e) { wx.showModal({title:'更新失败',content:e.message,showCancel:false}); } },
  async publishOffer() {
    const isCoupon=this.data.offerType==='coupon';
    const path=isCoupon?'/api/merchant/store/coupons':'/api/merchant/store/deals';
    const data=isCoupon
      ? {title:this.data.couponTitle,face_value:Number(this.data.couponValue),min_spend:Number(this.data.couponMinimum||0),stock:Number(this.data.couponStock)}
      : {title:this.data.dealTitle,price:Number(this.data.dealPrice),stock:Number(this.data.dealStock)};
    if(!String(data.title||'').trim()) return wx.showModal({title:'请填写标题',content:'活动标题不能为空。',showCancel:false});
    try {
      await request(path,{method:'PUT',token:this.data.token,data});
      await this.load();
      this.setData(isCoupon?{couponTitle:'',couponValue:'',couponMinimum:'',couponStock:''}:{dealTitle:'',dealPrice:'',dealStock:''});
      wx.showToast({title:isCoupon?'代金券已发布':'套餐已发布'});
    } catch(e) { wx.showModal({title:'发布失败',content:e.message,showCancel:false}); }
  }
});
