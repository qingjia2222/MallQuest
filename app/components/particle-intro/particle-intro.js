/**
 * particle-intro 组件：扫码进入时的粒子聚合成「已连接本商场」仪式感。
 * 纯 CSS 粒子 + 渐显，低配兼容。props：play(boolean)、text。
 */
Component({
  properties: {
    play: { type: Boolean, value: false },
    text: { type: String, value: '已连接本商场' }
  },
  data: {
    dots: [],
    show: false
  },
  observers: {
    play(v) {
      if (v) this.animate();
    }
  },
  lifetimes: {
    attached() {
      // 生成 24 个随机粒子
      const dots = Array.from({ length: 24 }, () => ({
        x: Math.random() * 100,
        y: Math.random() * 100,
        delay: Math.random() * 0.8,
        size: 6 + Math.random() * 14
      }));
      this.setData({ dots });
    }
  },
  methods: {
    animate() {
      this.setData({ show: true });
      setTimeout(() => {
        this.setData({ show: true }); // 保持显示 welcome 文案
        this.triggerEvent('done');
      }, 1400);
    }
  }
});
