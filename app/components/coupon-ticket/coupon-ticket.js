/**
 * coupon-ticket 组件：可撕式券卡 + 领取动效。
 * props：coupon { id,title,scope,expire,color }
 * events：claim
 */
Component({
  properties: {
    coupon: { type: Object, value: {} },
    claimed: { type: Boolean, value: false }
  },
  methods: {
    onClaim() {
      if (this.data.claimed) return;
      wx.vibrateShort({ type: 'light' });
      this.triggerEvent('claim', { coupon: this.data.coupon });
    }
  }
});
