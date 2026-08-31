// pages/plan/plan.js - 甲方 PlanFlow/行程卡 + 乙方 Planner 状态机
const { request } = require('../../utils/request');
Page({
  data: { step: 1, goalText: '我今天约会', form: {}, questions: [], qIndex: 0, currentQ: {}, options: [], itinerary: {}, generating: false, executing: false, plan: null },
  onLoad() {
    const existing = getApp().globalData.currentPlan || (getApp().globalData.planState && getApp().globalData.planState.current);
    if (existing) { this.present(existing, existing.state === 'DONE' ? 5 : 4); return; }
    const goalText = wx.getStorageSync('planGoal') || '我今天约会'; this.setData({ goalText }); this.startUnderstand();
  },
  startUnderstand() {
    const questions = [
      { key: 'time', label: '大概打算几点开始？', options: ['19:00', '19:30', '20:00'] },
      { key: 'people', label: '一共几个人？', options: ['2人', '3人', '4人'] },
      { key: 'budget', label: '人均预算大概多少？', options: ['150', '250', '350'] },
      { key: 'taste', label: '偏好什么口味？', options: ['川菜', '日料', '西餐'] }
    ];
    this.setData({ questions, currentQ: questions[0], options: questions[0].options, step: 2 });
  },
  pickOption(e) {
    const val = e.currentTarget.dataset.val, q = this.data.currentQ, form = { ...this.data.form, [q.key]: val }, next = this.data.qIndex + 1;
    if (next < this.data.questions.length) this.setData({ form, qIndex: next, currentQ: this.data.questions[next], options: this.data.questions[next].options });
    else { this.setData({ form }); this.generatePlan(form); }
  },
  async generatePlan(form) {
    this.setData({ step: 3, generating: true });
    try {
      const app = getApp(); await app.ensureSession();
      const plan = await request('/api/plan/goal', { method: 'POST', data: { session_id: app.globalData.sessionId, text: this.data.goalText, scene: 'date', slots: { time: form.time || '19:00', people: Number(String(form.people || '2').replace('人','')), budget_per_person: Number(form.budget || 250), cuisine: form.taste || '川菜', want_movie: true } } });
      app.globalData.currentPlan = plan; app.setPlanState({ current: plan }); this.present(plan, 4);
    } catch (e) { wx.showModal({ title: '规划失败', content: e.message, showCancel: false }); this.setData({ step: 2 }); }
    finally { this.setData({ generating: false }); }
  },
  present(plan, step) {
    const time = (plan.slots && plan.slots.time) || '19:00';
    const stops = (plan.itinerary || []).map((s, index) => ({ ...s, time: index ? `第 ${index + 1} 站` : time, waiting: s.queue_minutes || 0 }));
    const labels = { reserve_restaurant: '餐厅预约', reserve_business_space: '商务空间预约', claim_coupon: '优惠券领取', buy_ticket: '电影票购买' };
    const actions = (plan.action_results || []).map(a => ({ label: `${labels[a.tool] || a.tool}：${a.status}`, ok: a.status === 'success' || a.status === 'already_claimed' }));
    this.setData({ plan, step, itinerary: { tag: plan.state === 'DONE' ? '已执行' : '等待确认', stops, actions } });
  },
  onChangePlan() { this.generatePlan(this.data.form); },
  async onConfirm() {
    if (!this.data.plan || this.data.plan.state !== 'CONFIRM') return;
    this.setData({ executing: true });
    try { const plan = await request('/api/plan/confirm', { method: 'POST', data: { plan_id: this.data.plan.plan_id, decision: 'confirm' } }); getApp().globalData.currentPlan = plan; getApp().setPlanState({ current: plan }); this.present(plan, 5); wx.showToast({ title: '规划已执行' }); }
    catch (e) { wx.showModal({ title: '执行失败', content: e.message, showCancel: false }); }
    finally { this.setData({ executing: false }); }
  },
  onStopTap(e) { const name = e.detail && e.detail.stop ? e.detail.stop.name : ''; wx.navigateTo({ url: '/pages/map/map?focus=' + name }); },
  goMap() { wx.switchTab({ url: '/pages/map/map' }); },
  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
