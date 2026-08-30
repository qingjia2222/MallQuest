/**
 * rich-card 组件：结构化结果卡片，按 type 渲染店铺/停车/优惠券/通用。
 * props：card { type, data, title, subtitle, ... }
 */
Component({
  properties: {
    card: { type: Object, value: {} }
  },
  data: { kind: 'generic' },
  observers: {
    'card.type': function (t) {
      this.setData({ kind: t || 'generic' });
    }
  },
  methods: {
    onTap() {
      this.triggerEvent('cardtap', { card: this.data.card });
    }
  }
});
