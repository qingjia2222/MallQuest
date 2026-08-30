// pages/plan/plan.js - 需求规划页（理解→采集→生成→确认→执行）
const mock = require('../../utils/mock');
const { mockStream } = require('../../utils/sse');

Page({
  data: {
    step: 1,               // 1理解 2采集 3生成 4确认 5执行
    goalText: '',
    form: {},              // 采集到的槽位
    questions: [],         // 待采集问题
    qIndex: 0,
    currentQ: {},
    options: [],           // 当前问题选项
    itinerary: {},         // 方案
    generating: false,
    executing: false
  },

  onLoad() {
    const goal = wx.getStorageSync('planGoal') || '我今天约会';
    this.setData({ goalText: goal });
    this.startUnderstand();
  },

  // 步骤1-2：理解目标并采集偏好
  startUnderstand() {
    this.setData({ step: 2 });
    const questions = [
      { key: 'time', label: '大概打算几点开始？', options: ['19:00', '19:30', '20:00'] },
      { key: 'people', label: '一共几个人？', options: ['2人', '3人', '4人'] },
      { key: 'budget', label: '人均预算大概多少？', options: ['100-200', '200-300', '300+'] },
      { key: 'taste', label: '偏好什么口味？', options: ['川菜', '火锅', '日料', '西餐'] }
    ];
    this.setData({ questions, currentQ: questions[0], options: questions[0].options, step: 2 });
  },

  pickOption(e) {
    const val = e.currentTarget.dataset.val;
    const q = this.data.currentQ;
    const form = { ...this.data.form, [q.key]: val };
    const next = this.data.qIndex + 1;
    if (next < this.data.questions.length) {
      this.setData({ form, qIndex: next, currentQ: this.data.questions[next], options: this.data.questions[next].options });
    } else {
      this.setData({ form });
      this.generatePlan(form);
    }
  },

  // 步骤3：生成方案（演示动画后给出 itinerary）
  generatePlan(form) {
    this.setData({ step: 3, generating: true });
    const t = form.taste || '川菜';
    const time = form.time || '19:00';
    // demo：按口味拼一站烟火气店家
    const stops = [
      { time, name: t + '推荐 · 川渝人家', floor: 3, category: '川菜', waiting: 12, status: '已预约' },
      { time: '19:40', name: '茶颜观色奶茶', floor: 1, category: '饮品', waiting: 5, status: '领券' },
      { time: '20:10', name: '星辰影院 IMAX', floor: 4, category: '影院', waiting: 0, status: '已购票' },
      { time: '21:50', name: '甜心甜品', floor: 2, category: '甜品', waiting: 3, status: '可预约' }
    ];
    setTimeout(() => {
      this.setData({
        step: 4,
        generating: false,
        itinerary: {
          tag: '专为你定制',
          stops,
          actions: [
            { label: `已为你预订「川渝人家」${time} · ${this.data.form.people || '2人'}`, ok: true }
          ]
        }
      });
    }, 1400);
  },

  onChangePlan() {
    wx.showToast({ title: '为你重排一版', icon: 'none' });
    this.generatePlan(this.data.form);
  },

  onConfirm() {
    this.setData({ step: 5, executing: true });
    const it = { ...this.data.itinerary };
    setTimeout(() => {
      it.actions = [
        ...(it.actions || []),
        { label: '已为你锁定星辰影院 19:30 场次', ok: true },
        { label: '已锁定停车场 B1 层车位', ok: true }
      ];
      this.setData({ itinerary: it, executing: false });
      wx.vibrateShort({ type: 'light' });
      wx.showToast({ title: '规划完成', icon: 'success' });
    }, 1200);
  },

  onStopTap(e) {
    // 联动地图
    const name = e && e.detail && e.detail.stop ? e.detail.stop.name : '';
    wx.navigateTo({ url: '/pages/map/map?focus=' + name });
  },

  goMap() {
    wx.navigateTo({ url: '/pages/map/map' });
  },

  goChat() {
    wx.switchTab({ url: '/pages/chat/chat' });
  }
});
