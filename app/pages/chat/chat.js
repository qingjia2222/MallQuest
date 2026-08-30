// pages/chat/chat.js - 对话主页（接队友后端 /api/chat，含 Qwen agent + 卡片）
const mock = require('../../utils/mock');
const { request } = require('../../utils/request');
const { formatTime } = require('../../utils/format');

Page({
  data: {
    messages: [],
    input: '',
    quickActions: ['停车场还有空位吗？', '积分多久过期？', '今天有什么特惠？', '有什么好吃的推荐？', '帮我规划约会'],
    loading: false
  },

  onLoad() {
    const app = getApp();
    const name = (app.globalData.mall && app.globalData.mall.name) || 'QD square';
    this.push('ai', `已接入「${name}」私有数据。我是你的 AI 私域助手，问我停车、积分、特惠，或说「帮我规划约会」。`);
  },

  onInput(e) { this.setData({ input: e.detail.value }); },
  onQuick(e) { this.send(e.currentTarget.dataset.text); },

  async send(text) {
    const content = (text || this.data.input).trim();
    if (!content || this.data.loading) return;
    this.setData({ input: '', loading: true });
    this.push('user', content);

    try {
      const app = getApp();
      await app.ensureSession();
      const data = await request('/api/chat', {
        method: 'POST',
        data: { session_id: app.globalData.sessionId, message: content }
      });
      const idx = this.data.messages.length;
      const card = (data.cards && data.cards[0]) || null;
      const plan = data.plan || null;
      this.setData({
        [`messages[${idx}]`]: { role: 'ai', text: data.reply || '好的，已为你处理。', card, plan, time: formatTime(Date.now()) }
      });
      // 保存方案供地图/预约页使用
      if (plan) { app.setPlanState({ current: plan }); }
      this.scrollBottom();
    } catch (e) {
      this.push('ai', '抱歉，请求后端失败：' + (e.message || ''));
    } finally {
      this.setData({ loading: false });
    }
  },

  push(role, text) {
    const msgs = this.data.messages;
    msgs.push({ role, text, time: formatTime(Date.now()) });
    this.setData({ messages: msgs });
    this.scrollBottom();
  },

  onCardTap(e) {
    const { card } = e.detail || {};
    if (!card) return;
    if (card.type === 'parking') wx.switchTab({ url: '/pages/map/map' });
    else if (card.type === 'coupon') wx.navigateTo({ url: '/pages/coupon/coupon' });
    else if (card.type === 'store' || card.type === 'list') wx.switchTab({ url: '/pages/map/map' });
  },

  onPlanTap() { wx.navigateTo({ url: '/pages/plan/plan' }); },

  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); },
  onVoice(e) { const text = e.detail.text; this.setData({ input: text }); this.send(text); },

  scrollBottom() {
    wx.createSelectorQuery().select('#chat-scroll').node(res => {
      if (res) res.scrollTo({ top: res.scrollHeight + 500, duration: 200 });
    }).exec();
  }
});
