/**
 * parking-gauge 组件：环形仪表盘实时展示空余车位。
 * props：free(空位数), total(总数)
 */
Component({
  properties: {
    free: { type: Number, value: 0 },
    total: { type: Number, value: 0 }
  },
  data: { pct: 0, ring: '' },
  observers: {
    'free,total'(free, total) {
      const pct = total ? Math.round((free / total) * 100) : 0;
      const deg = pct * 3.6;
      this.setData({ pct, ring: `background: conic-gradient(#06B6D4 ${deg}deg, #eef2ff 0deg);` });
    }
  }
});
