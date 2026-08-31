/**
 * itinerary-card 组件：方案单卡片，按时间轴列出各站店铺、状态与预约/领券结果。
 * props：itinerary { stops: [{time,name,floor,waiting,status}], actions: [{label,ok}] }
 * events：stoptap(点击单站，联动地图), confirm, change
 */
Component({
  properties: {
    itinerary: { type: Object, value: {} }
  },
  methods: {
    onStopTap(e) {
      this.triggerEvent('stoptap', { index: e.currentTarget.dataset.index, stop: e.currentTarget.dataset.stop });
    },
    onConfirm() { this.triggerEvent('confirm'); },
    onChange() { this.triggerEvent('change'); },
    onStrategy(e) { this.triggerEvent('strategy', { strategy: e.currentTarget.dataset.strategy }); }
  }
});
