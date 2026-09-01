// Mobile chat mirrors the Web flow: answer -> inline plan -> explicit execution gate -> 3D route.
const { request, BASE_URL } = require('../../utils/request');
const { formatTime } = require('../../utils/format');
const { actionResultLabel, actionResultOk } = require('../../utils/action-result');
const cleanReply = text => String(text || '').replace(/\*/g, '');
function decoratePlan(plan) {
  if (!plan) return null;
  return {
    ...plan,
    itineraryCard: {
      tag: plan.state === 'DONE' ? '已执行' : '等待确认',
      stops: (plan.itinerary || []).map((s, i) => ({ ...s, time: s.time_label || `第 ${i + 1} 站`, waiting: s.queue_minutes || 0 })),
      actions: (plan.action_results || []).map(a => ({ label: actionResultLabel(a), ok: actionResultOk(a) })),
      selectedStrategy: plan.route && plan.route.selected_strategy,
      alternatives: ((plan.route && plan.route.alternatives) || []).map(a => ({ strategy: a.strategy, label: a.label,
        estimated_total_minutes: a.metrics.estimated_total_minutes, estimated_distance: a.metrics.estimated_distance,
        estimated_wait_minutes: a.metrics.estimated_wait_minutes }))
    }
  };
}

Page({
  data: {
    messages: [], input: '', loading: false, scrollTop: 0, speakingIndex: -1,
    quickActions: ['帮我规划约会','帮我预约沃德面包，2个人，19点','停车还有空位吗','积分多久过期','今日特惠'],
    navigation: null, navVisible: false, navStores: [], navFacilities: [], navInstruction: '',
    showConfirm: false, confirmStep: 1, pendingPlan: null, pendingManagement:false, movieOptions: [], chosenMovie: '', executing: false
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
  onUnload() { this.stopTtsPlayback(false); },
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
    this.setData({ navStores: stores, navFacilities:scene.facilities||[] }); return stores;
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
        const updated=decoratePlan(await request('/api/plan/confirm',{method:'POST',data:{plan_id:nav.plan_id,decision:'modify',modifications:{vertical_mode:mode},expected_revision:nav.revision}}));
        const app=getApp();app.globalData.currentPlan=updated;app.setPlanState({current:updated});
        const messages=this.data.messages.map(m=>m.plan&&m.plan.plan_id===updated.plan_id?{...m,plan:updated}:m);this.setData({messages});await this.openPlanRoute();
      }else{
        const app=getApp(),destinationId=nav.destination_store.id;
        const updated=await request('/api/navigation/resolve',{method:'POST',data:{session_id:app.globalData.sessionId,destination_store_id:destinationId,vertical_mode:mode,current_node:nav.start_node}});
        await this.openNavigation(updated);
      }
    }catch(err){wx.showToast({title:err.message||'切换失败',icon:'none'});}
  },

  openExecuteConfirm() {
    const plan = getApp().globalData.currentPlan;
    if (!plan || plan.state === 'DONE') { this.openPlanRoute(); return; }
    const cinema=(plan.itinerary||[]).find(s=>s.now_showing&&s.now_showing.length), movies=cinema?cinema.now_showing:[];
    const actions=plan.slots&&plan.slots.requested_actions||[],pendingManagement=actions.some(action=>action==='cancel_reservation'||action==='update_reservation');
    this.setData({ showConfirm: true, confirmStep: 1, pendingPlan: plan, pendingManagement, movieOptions:movies, chosenMovie:movies[0]||'' });
  },
  chooseMovie(e){this.setData({chosenMovie:e.currentTarget.dataset.movie})},
  cancelExecute() { this.setData({ showConfirm: false, confirmStep: 1, pendingPlan: null, pendingManagement:false }); },
  nextConfirm() { this.setData({ confirmStep: 2 }); },
  async runExecute(e) {
    const booking = String(e.currentTarget.dataset.booking) === 'true', plan = this.data.pendingPlan, managing=this.data.pendingManagement;
    this.setData({ showConfirm: false, confirmStep: 1, pendingPlan: null, pendingManagement:false });
    if (!plan) return;
    if (!booking) { if(!managing)await this.openPlanRoute(); return; }
    this.setData({ executing: true, loading: true });
    try {
      const modifications=this.data.chosenMovie?{selected_movie:this.data.chosenMovie}:{};
      const done = decoratePlan(await request('/api/plan/confirm', { method: 'POST', data: { plan_id: plan.plan_id, decision: 'confirm', modifications, expected_revision: plan.revision } }));
      const app = getApp(); app.globalData.currentPlan = done; app.setPlanState({ current: done });
      const messages = this.data.messages.map(m => m.plan && m.plan.plan_id === done.plan_id ? { ...m, plan: done } : m);
      this.setData({ messages });
      if(managing)this.push('ai','预约变更已确认并完成，可在“我的预约”中查看最新状态。');
      else this.push('ai', '方案已确认并执行，预约、排号、领券或演示票务结果已更新。现在为你展示路线。');
      wx.vibrateShort && wx.vibrateShort({ type: 'light' }); if(!managing)await this.openPlanRoute();
    } catch (err) { this.push('ai', '确认失败：' + (err.message || '')); }
    finally { this.setData({ executing: false, loading: false }); }
  },
  onChangePlan() { this.cancelExecute(); this.send('请重新规划约会方案，换一些店铺'); },
  async chooseStrategy(e) {
    const strategy=e.detail.strategy, current=getApp().globalData.currentPlan;
    if(!current||!current.plan_id||!strategy)return;
    try{
      const updated=decoratePlan(await request('/api/plan/confirm',{method:'POST',data:{plan_id:current.plan_id,decision:'modify',modifications:{strategy},expected_revision:current.revision}}));
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
  stopTtsPlayback(updateView = true) {
    this._ttsRequestToken = (this._ttsRequestToken || 0) + 1;
    const audio = this._ttsAudio;
    this._ttsAudio = null;
    this._ttsMessageIndex = -1;
    if (audio) {
      try { audio.stop(); } finally { audio.destroy(); }
    }
    if (updateView && this.data.speakingIndex !== -1) this.setData({ speakingIndex: -1 });
  },
  async speak(e) {
    const index = Number(e.currentTarget.dataset.index);
    if (this._ttsMessageIndex === index) { this.stopTtsPlayback(); return; }

    this.stopTtsPlayback();
    this._ttsMessageIndex = index;
    const token = (this._ttsRequestToken || 0) + 1;
    this._ttsRequestToken = token;
    this.setData({ speakingIndex: index });
    try {
      const data = await request('/api/tts', { method: 'POST', data: { text: e.currentTarget.dataset.text || '欢迎来到星河里' } });
      if (this._ttsRequestToken !== token || this._ttsMessageIndex !== index) return;
      const audio = wx.createInnerAudioContext();
      this._ttsAudio = audio;
      const finish = () => {
        if (this._ttsAudio !== audio) return;
        this._ttsAudio = null;
        this._ttsMessageIndex = -1;
        audio.destroy();
        this.setData({ speakingIndex: -1 });
      };
      audio.onEnded(finish);
      audio.onError(finish);
      audio.src = BASE_URL + data.audio_url;
      audio.play();
    } catch (err) {
      if (this._ttsRequestToken !== token) return;
      this.stopTtsPlayback();
      wx.showToast({ title: err.message || '播报失败', icon: 'none' });
    }
  },
  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); },
  onVoice(e) { const text = e.detail.text; this.setData({ input: text }); this.send(text); },
  scrollBottom() { this.setData({ scrollTop: (this.data.messages.length + 1) * 10000 }); }
});
