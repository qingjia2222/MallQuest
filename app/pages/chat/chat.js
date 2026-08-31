// pages/chat/chat.js - 对话主页（接队友后端 /api/chat，含 Qwen agent + 卡片）
const mock = require('../../utils/mock');
const { request } = require('../../utils/request');
const { formatTime } = require('../../utils/format');
const cleanReply = text => String(text || '').replace(/\*/g, '');

Page({
  data: {
    messages: [],
    input: '',
    loading: false,
    navigation: null,
    navVisible: false,
    navFloor: 1,
    navMapUrl: '',
    navStep: 0,
    scrollTop: 0
  },

  onLoad() {
    const app = getApp();
    const name = (app.globalData.mall && app.globalData.mall.name) || 'QD square';
    this.push('ai', `已接入「${name}」私有数据。我是你的 AI 私域助手，问我停车、积分、特惠，或说「帮我规划约会」。`);
  },

  onInput(e) { this.setData({ input: e.detail.value }); },
  onQuick(e) { this.send(e.currentTarget.dataset.text); },

  async send(text) {
    const content = (typeof text === 'string' ? text : this.data.input).trim();
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
      const navigation = data.navigation || null;
      const card = navigation ? null : (data.cards && data.cards[0]) || null;
      const plan = data.plan || null;
      this.setData({
        [`messages[${idx}]`]: { role: 'ai', text: cleanReply(data.reply || '好的，已为你处理。'), card, plan, time: formatTime(Date.now()) }
      });
      // 保存方案供地图/预约页使用
      if (plan) { app.setPlanState({ current: plan }); app.globalData.currentPlan = plan; }
      if (navigation) this.setData({ navigation, navVisible: true, navStep: 0 }, () => this.replayNavigation());
      this.scrollBottom();
    } catch (e) {
      this.push('ai', '抱歉，请求后端失败：' + (e.message || ''));
    } finally {
      this.setData({ loading: false });
    }
  },

  push(role, text) {
    const msgs = this.data.messages;
    msgs.push({ role, text: role === 'ai' ? cleanReply(text) : text, time: formatTime(Date.now()) });
    this.setData({ messages: msgs });
    this.scrollBottom();
  },

  onCardTap(e) {
    const { card } = e.detail || {};
    if (!card) return;
    if (card.type === 'parking') wx.switchTab({ url: '/pages/map/map' });
    else if (card.type === 'coupon') wx.navigateTo({ url: '/pages/coupon/coupon' });
    else if (['store', 'list', 'stores', 'queue'].includes(card.type)) wx.switchTab({ url: '/pages/map/map' });
  },

  onPlanTap() { wx.navigateTo({ url: '/pages/plan/plan' }); },

  async speak(e) {
    try {
      const text = e.currentTarget.dataset.text || '欢迎来到 QD square';
      const data = await request('/api/tts', { method: 'POST', data: { text } });
      const audio = wx.createInnerAudioContext(); audio.src = 'http://127.0.0.1:8000' + data.audio_url; audio.play();
    } catch (err) { wx.showToast({ title: err.message || '播报失败', icon: 'none' }); }
  },

  closeNavigation() {
    if (this.navTimer) clearTimeout(this.navTimer);
    this.setData({ navVisible: false });
  },

  replayNavigation() {
    if (this.navTimer) clearTimeout(this.navTimer);
    const navigation = this.data.navigation;
    if (!navigation || !navigation.nodes || !navigation.nodes.length) return;
    this.setData({ navVisible: true, navStep: 0 }, () => this.playNavigationStep(0));
  },

  playNavigationStep(step) {
    const nodes = this.data.navigation.nodes;
    if (step >= nodes.length) return;
    const floor = nodes[step].floor;
    this.setData({
      navStep: step,
      navFloor: floor,
      navMapUrl: `http://127.0.0.1:8000/api/maps/mall_demo/floor_${floor}.svg`
    }, () => this.drawNavigation());
    if (step < nodes.length - 1) this.navTimer = setTimeout(() => this.playNavigationStep(step + 1), 520);
  },

  drawNavigation() {
    const navigation = this.data.navigation;
    const floorNodes = navigation.nodes.filter(node => node.floor === this.data.navFloor);
    const currentNode = navigation.nodes[this.data.navStep];
    const ctx = wx.createCanvasContext('navCanvas', this);
    const width = wx.getSystemInfoSync().windowWidth - 56, height = width * .76;
    const drawLine = (points, color, lineWidth) => {
      if (!points.length) return;
      ctx.setLineCap('round'); ctx.setStrokeStyle(color); ctx.setLineWidth(lineWidth);
      ctx.moveTo(points[0].x * width / 1000, points[0].y * height / 760);
      points.slice(1).forEach(node => ctx.lineTo(node.x * width / 1000, node.y * height / 760));
      ctx.stroke();
    };
    drawLine(floorNodes, 'rgba(124,58,237,.30)', 5);
    drawLine(navigation.nodes.slice(0, this.data.navStep + 1).filter(node => node.floor === this.data.navFloor), '#EF4444', 8);
    if (currentNode && currentNode.floor === this.data.navFloor) {
      const x = currentNode.x * width / 1000, y = currentNode.y * height / 760;
      ctx.setFillStyle('#fff'); ctx.beginPath(); ctx.arc(x, y, 13, 0, Math.PI * 2); ctx.fill();
      ctx.setFillStyle('#EF4444'); ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fill();
    }
    ctx.draw();
  },

  goPlan() { wx.navigateTo({ url: '/pages/plan/plan' }); },
  onVoice(e) { const text = e.detail.text; this.setData({ input: text }); this.send(text); },

  scrollBottom() { this.setData({ scrollTop: (this.data.messages.length + 1) * 10000 }); },

  onUnload() { if (this.navTimer) clearTimeout(this.navTimer); }
});
