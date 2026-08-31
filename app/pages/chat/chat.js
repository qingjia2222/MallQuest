// Mobile chat mirrors the Web flow: answer -> inline plan -> explicit execution gate -> 3D route.
const { request, BASE_URL } = require('../../utils/request');
const { formatTime } = require('../../utils/format');
const cleanReply = text => String(text || '').replace(/\*/g, '');

function actionLabel(action) {
  const labels = { reserve_restaurant: '餐厅预约', reserve_business_space: '商务空间预约', claim_coupon: '优惠券领取', buy_ticket: '电影票购买', queue: '店铺排号' };
  return `${labels[action.tool] || action.label || action.tool || '服务操作'}：${action.status || '完成'}`;
}
function decoratePlan(plan) {
  if (!plan) return null;
  return {
    ...plan,
    itineraryCard: {
      tag: plan.state === 'DONE' ? '已执行' : '等待确认',
      stops: (plan.itinerary || []).map((s, i) => ({ ...s, time: s.time_label || `第 ${i + 1} 站`, waiting: s.queue_minutes || 0 })),
      actions: (plan.action_results || []).map(a => ({ label: actionLabel(a), ok: !['failed','unavailable'].includes(a.status) })),
      selectedStrategy: plan.route && plan.route.selected_strategy,
      alternatives: ((plan.route && plan.route.alternatives) || []).map(a => ({ strategy: a.strategy, label: a.label,
        estimated_total_minutes: a.metrics.estimated_total_minutes, estimated_distance: a.metrics.estimated_distance,
        estimated_wait_minutes: a.metrics.estimated_wait_minutes }))
    }
  };
}

Page({
  data: {
    messages: [], input: '', loading: false, scrollTop: 0,
    navigation: null, navVisible: false, navStores: [], navInstruction: '',
    showConfirm: false, confirmStep: 1, pendingPlan: null, movieOptions: [], chosenMovie: '', executing: false
  },

  onLoad() {
    const app = getApp();
    const name = (app.globalData.mall && app.globalData.mall.name) || '星河里';
    this.push('ai', `已接入「${name}」私有数据。我是你的 AI 私域助手，问我停车、积分、特惠，或说「帮我规划约会」。`);
  },
  onShow() {
    const app = getApp();
    if (app.globalData.chatPrefill) { this.setData({ input: app.globalData.chatPrefill }); app.globalData.chatPrefill = ''; }
  },
  onInput(e) { this.setData({ input: e.detail.value }); },
  onQuick(e) { this.send(e.currentTarget.dataset.text); },

  async send(text) {
    const content = (typeof text === 'string' ? text : this.data.input).trim();
    if (!content || this.data.loading) return;
    this.setData({ input: '', loading: true }); this.push('user', content);
    try {
      const app = getApp(); await app.ensureSession();
      const data = await request('/api/chat', { method: 'POST', data: { session_id: app.globalData.sessionId, message: content } });
      const idx = this.data.messages.length, navigation = data.navigation || null;
      const plan = decoratePlan(data.plan || null), card = navigation || plan ? null : (data.cards && data.cards[0]) || null;
      this.setData({ [`messages[${idx}]`]: { role: 'ai', text: cleanReply(data.reply || '好的，已为你处理。'), card, plan, time: formatTime(Date.now()) } });
      if (plan) {
        app.setPlanState({ current: plan }); app.globalData.currentPlan = plan;
      }
      if (navigation) await this.openNavigation(navigation);
      this.scrollBottom();
    } catch (e) { this.push('ai', '抱歉，请求后端失败：' + (e.message || '')); }
    finally { this.setData({ loading: false }); }
  },

  push(role, text) {
    const messages = this.data.messages.concat([{ role, text: role === 'ai' ? cleanReply(text) : text, time: formatTime(Date.now()) }]);
    this.setData({ messages }); this.scrollBottom();
  },
  async loadMapStores() {
    if (this.data.navStores.length) return this.data.navStores;
    const scene = await request('/api/maps/mall_demo/scene');
    const stores = (scene.stores || []).map(s => ({ ...s, pos_x: s.pos_x / 10, pos_y: s.pos_y / 7.6 }));
    this.setData({ navStores: stores }); return stores;
  },
  async openNavigation(navigation) {
    await this.loadMapStores();
    const transfers = navigation.transfer_instructions || [];
    const instruction = transfers.length ? `到达换层设施后，${transfers.join('，')}` : '全程同层，沿绿色路线前往目的地';
    this.setData({ navigation, navVisible: true, navInstruction: instruction }, () => this.replayNavigation());
  },
  closeNavigation() { this.setData({ navVisible: false }); },
  replayNavigation() {
    const map = this.selectComponent('#chatRouteMap');
    if (map && map.replayRoute) map.replayRoute();
  },
  async openPlanRoute() {
    const plan = getApp().globalData.currentPlan;
    if (!plan || !plan.route || !(plan.route.nodes || []).length) { wx.showToast({ title: '当前方案暂无路线', icon: 'none' }); return; }
    const last = (plan.itinerary || [])[plan.itinerary.length - 1] || { name: '目的地' };
    const transfer = (plan.route.polyline_segments || []).filter(s => s.transfer_instruction).map(s => s.transfer_instruction);
    await this.openNavigation({ type: 'route_animation', plan_id: plan.plan_id, destination_store: last, nodes: plan.route.nodes,
      floors: [...new Set(plan.route.nodes.map(n=>n.floor))], vertical_mode: plan.route.vertical_mode,
      transfer_instructions: transfer, estimated_distance: plan.route.estimated_distance, replayable: true, dismissible: true });
  },
  async switchTransfer(e){
    const mode=e.currentTarget.dataset.mode,nav=this.data.navigation;if(!nav||!mode)return;
    try{
      if(nav.plan_id){
        const updated=decoratePlan(await request('/api/plan/confirm',{method:'POST',data:{plan_id:nav.plan_id,decision:'modify',modifications:{vertical_mode:mode}}}));
        const app=getApp();app.globalData.currentPlan=updated;app.setPlanState({current:updated});
        const messages=this.data.messages.map(m=>m.plan&&m.plan.plan_id===updated.plan_id?{...m,plan:updated}:m);this.setData({messages});await this.openPlanRoute();
      }else{
        const app=getApp(),name=nav.destination_store.name;
        const updated=await request('/api/navigation/resolve',{method:'POST',data:{session_id:app.globalData.sessionId,query:`怎么走${mode==='escalator'?'扶梯':'直梯'}去${name}？`,current_node:nav.start_node}});
        await this.openNavigation(updated);
      }
    }catch(err){wx.showToast({title:err.message||'切换失败',icon:'none'});}
  },

  openExecuteConfirm() {
    const plan = getApp().globalData.currentPlan;
    if (!plan || plan.state === 'DONE') { this.openPlanRoute(); return; }
    const cinema=(plan.itinerary||[]).find(s=>s.now_showing&&s.now_showing.length), movies=cinema?cinema.now_showing:[];
    this.setData({ showConfirm: true, confirmStep: 1, pendingPlan: plan, movieOptions:movies, chosenMovie:movies[0]||'' });
  },
  chooseMovie(e){this.setData({chosenMovie:e.currentTarget.dataset.movie})},
  cancelExecute() { this.setData({ showConfirm: false, confirmStep: 1, pendingPlan: null }); },
  nextConfirm() { this.setData({ confirmStep: 2 }); },
  async runExecute(e) {
    const booking = String(e.currentTarget.dataset.booking) === 'true', plan = this.data.pendingPlan;
    this.setData({ showConfirm: false, confirmStep: 1, pendingPlan: null });
    if (!plan) return;
    if (!booking) { await this.openPlanRoute(); return; }
    this.setData({ executing: true, loading: true });
    try {
      const modifications=this.data.chosenMovie?{selected_movie:this.data.chosenMovie}:{};
      const done = decoratePlan(await request('/api/plan/confirm', { method: 'POST', data: { plan_id: plan.plan_id, decision: 'confirm', modifications } }));
      const app = getApp(); app.globalData.currentPlan = done; app.setPlanState({ current: done });
      const messages = this.data.messages.map(m => m.plan && m.plan.plan_id === done.plan_id ? { ...m, plan: done } : m);
      this.setData({ messages }); this.push('ai', '方案已确认并执行，预约、排号、领券或演示票务结果已更新。现在为你展示路线。');
      wx.vibrateShort && wx.vibrateShort({ type: 'light' }); await this.openPlanRoute();
    } catch (err) { this.push('ai', '确认失败：' + (err.message || '')); }
    finally { this.setData({ executing: false, loading: false }); }
  },
  onChangePlan() { this.cancelExecute(); this.send('请重新规划约会方案，换一些店铺'); },
  async chooseStrategy(e) {
    const strategy=e.detail.strategy, current=getApp().globalData.currentPlan;
    if(!current||!current.plan_id||!strategy)return;
    try{
      const updated=decoratePlan(await request('/api/plan/confirm',{method:'POST',data:{plan_id:current.plan_id,decision:'modify',modifications:{strategy}}}));
      const app=getApp();app.globalData.currentPlan=updated;app.setPlanState({current:updated});
      const messages=this.data.messages.map(m=>m.plan&&m.plan.plan_id===updated.plan_id?{...m,plan:updated}:m);
      this.setData({messages,pendingPlan:updated});wx.showToast({title:strategy==='fastest'?'已选用时最短':'已选路程最近'});
    }catch(err){wx.showToast({title:err.message||'切换失败',icon:'none'});}
  },
  onInlineStopTap() { this.openPlanRoute(); },
  onPlanTap() { this.openPlanRoute(); },
  goPlanDetail() { this.cancelExecute(); wx.navigateTo({ url: '/pages/plan/plan' }); },
  noop() {},

  onCardTap(e) {
    const { card } = e.detail || {}; if (!card) return;
    if (card.type === 'parking') wx.switchTab({ url: '/pages/map/map' });
    else if (card.type === 'coupon' || card.type === 'deals') wx.navigateTo({ url: '/pages/coupon/coupon' });
    else if (['store', 'list', 'stores', 'queue'].includes(card.type)) wx.switchTab({ url: '/pages/map/map' });
  },
  async speak(e) {
    try { const data = await request('/api/tts', { method: 'POST', data: { text: e.currentTarget.dataset.text || '欢迎来到星河里' } }); const audio = wx.createInnerAudioContext(); audio.src = BASE_URL + data.audio_url; audio.play(); }
    catch (err) { wx.showToast({ title: err.message || '播报失败', icon: 'none' }); }
  },
  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); },
  onVoice(e) { const text = e.detail.text; this.setData({ input: text }); this.send(text); },
  scrollBottom() { this.setData({ scrollTop: (this.data.messages.length + 1) * 10000 }); }
});
