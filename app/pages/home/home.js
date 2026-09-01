const { request } = require('../../utils/request');

function decorateStore(store) {
  const category=String(store.category||'');
  const emoji=/咖啡/.test(category)?'☕':/甜品|饮品|茶/.test(category)?'🧋':/餐饮|火锅|料理|面食/.test(category)?'🍽️':/影院/.test(category)?'🎬':'🏬';
  const heroClass=/餐饮|火锅|料理|面食/.test(category)?'food':/甜品|饮品|咖啡|茶/.test(category)?'drink':/服务/.test(category)?'service':'retail';
  const queue=Number(store.queue_minutes||store.waiting||0);
  return {...store,emoji,heroClass,waiting:queue,queueText:queue>0?`${queue} 分钟`:'免排队',statusText:store.open_status==='open'?'营业中':'未营业'};
}

Page({
  data: { stores: [], filteredStores: [], filterByLabels: ['店铺种类', '楼层'], filterByIndex: 0, filterOptions: ['全部'], filterIndex: 0, facilities: [], route: [], routeNodes: [], parking: { areas: [], total_free: 0, total: 0 }, activeId: '', focusStore: null, showDetail: false, loading: true, asking:false, aiReply:'' },
  async onShow() {
    try {
      const app = getApp(); await app.ensureSession();
      const [scene,parking] = await Promise.all([request('/api/maps/mall_demo/scene'),request(`/api/parking?session_id=${app.globalData.sessionId}`)]);
      const stores = (scene.stores || []).map(s => decorateStore({ ...s, pos_x: s.pos_x / 10, pos_y: s.pos_y / 7.6 }));
      const filterOptions = ['全部', ...new Set(stores.map(s => s.category).filter(Boolean))];
      this.setData({ stores, filteredStores: stores, filterByIndex: 0, filterOptions, filterIndex: 0, facilities:scene.facilities||[], parking: {...parking,total:(parking.areas||[]).reduce((sum,a)=>sum+a.total,0)}, loading: false });
    } catch (e) { this.setData({ loading: false }); wx.showToast({ title: e.message || '店铺加载失败', icon: 'none' }); }
  },
  async onStoreTap(e) {
    const base = e.detail && e.detail.store ? e.detail.store : e.currentTarget.dataset.store;
    try {
      const live = await request(`/api/stores/${base.id}/public-status?mall_id=mall_demo`);
      this.setData({ activeId: base.id, focusStore: decorateStore({ ...base, ...live }), showDetail: true, aiReply:'' });
    } catch (err) { wx.showToast({ title: err.message || '查询失败', icon: 'none' }); }
  },
  closeDetail() { this.setData({ showDetail: false, aiReply:'' }); },
  onFilterBy(e) {
    const filterByIndex = Number(e.detail.value);
    const filterOptions = ['全部', ...new Set(this.data.stores.map(s => filterByIndex === 1 ? `${s.floor}F` : s.category).filter(Boolean))];
    this.setData({ filterByIndex, filterOptions, filterIndex: 0, filteredStores: this.data.stores });
  },
  onFilterValue(e) {
    const filterIndex = Number(e.detail.value), value = this.data.filterOptions[filterIndex] || '全部';
    const filteredStores = value === '全部' ? this.data.stores : this.data.stores.filter(s => this.data.filterByIndex === 1 ? `${s.floor}F` === value : s.category === value);
    this.setData({ filterIndex, filteredStores });
  },
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
  goReserve() {
    const store = this.data.focusStore;
    if (!store || Number(store.reservable) !== 1) return;
    this.closeDetail();
    wx.navigateTo({ url: `/pages/reserve/reserve?store=${encodeURIComponent(store.id)}` });
  }
});
