// pages/map/map.js - 甲方 2.5D 视觉 + 乙方真实商场接口
const { request } = require('../../utils/request');

function decorateStore(store) {
  const category=String(store.category||'');
  const emoji=/咖啡/.test(category)?'☕':/甜品|饮品|茶/.test(category)?'🧋':/餐饮|火锅|料理|面食/.test(category)?'🍽️':/影院/.test(category)?'🎬':'🏬';
  const heroClass=/餐饮|火锅|料理|面食/.test(category)?'food':/甜品|饮品|咖啡|茶/.test(category)?'drink':/服务/.test(category)?'service':'retail';
  const queue=Number(store.queue_minutes||store.waiting||0);
  return {...store,emoji,heroClass,waiting:queue,queueText:queue>0?`${queue} 分钟`:'免排队',statusText:store.open_status==='open'?'营业中':'未营业'};
}

Page({
  data: { stores: [], facilities: [], route: [], routeNodes: [], waypoints: [], activeId: '', focusStore: null, showDetail: false, asking:false, aiReply:'' },
  onLoad(query) { this.focusName = query.focus || ''; },
  async onShow() {
    try {
      const app = getApp(); await app.ensureSession();
      const scene = await request('/api/maps/mall_demo/scene');
      const stores = scene.stores.map(s => decorateStore({ ...s, pos_x: s.pos_x / 10, pos_y: s.pos_y / 7.6, rating: '4.8', waiting: s.queue_minutes || 0, desc: s.service_tags || '商户服务信息待更新' }));
      const current = app.globalData.currentPlan || (app.globalData.planState && app.globalData.planState.current);
      const route = current && current.itinerary ? current.itinerary.map(s => s.store_id || s.id).filter(Boolean) : [];
      const routeNodes = current && ((current.navigation && current.navigation.nodes) || (current.route && current.route.nodes)) || [];
      const waypoints = current && current.route && current.route.waypoints || [];
      const focusStore = this.focusName ? stores.find(s => s.name.indexOf(this.focusName) >= 0 || this.focusName.indexOf(s.name) >= 0) : null;
      this.setData({ stores, facilities:scene.facilities||[], route, routeNodes, waypoints, activeId: focusStore ? focusStore.id : '', focusStore, showDetail: Boolean(focusStore) });
    } catch (e) { wx.showModal({ title: '地图加载失败', content: e.message || '请确认后端已启动', showCancel: false }); }
  },
  async onStoreTap(e) {
    const base = e.detail.store;
    try {
      const live = await request(`/api/stores/${base.id}/public-status?mall_id=mall_demo`);
      this.setData({ activeId: base.id, focusStore: decorateStore({ ...base, ...live, waiting: live.queue_minutes || 0, desc: live.service_tags || base.desc }), showDetail: true, aiReply:'' });
    } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); }
  },
  closeDetail() { this.setData({ showDetail: false, aiReply:'' }); },
  noop() {},
  async askAI() {
    const store=this.data.focusStore;if(!store||this.data.asking)return;
    this.setData({asking:true,aiReply:''});
    try {
      let reply=store.desc||'';
      if(store.recommend&&store.recommend.length) reply+=`${reply?'\n':''}推荐：${store.recommend.join('、')}`;
      if(!reply){const app=getApp();const result=await request('/api/chat',{method:'POST',data:{session_id:app.globalData.sessionId,message:`${store.name}在几层？现在排队和余位怎么样？`}});reply=result.reply||'已查询。';}
      this.setData({aiReply:reply});
    } catch(e){this.setData({aiReply:'查询失败：'+(e.message||'')});}
    finally{this.setData({asking:false});}
  },
  async goNavigate() {
    const store=this.data.focusStore;if(!store)return;
    try{
      const app=getApp();const navigation=await request('/api/navigation/resolve',{method:'POST',data:{session_id:app.globalData.sessionId,query:`怎么去${store.name}`,current_node:'f1_entrance'}});
      this.setData({routeNodes:navigation.nodes||[],activeId:store.id,showDetail:false,aiReply:''});
      wx.showToast({title:`正在导航到${store.name}`,icon:'none'});
    }catch(e){wx.showToast({title:e.message||'路线生成失败',icon:'none'});}
  },
  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); }
});
