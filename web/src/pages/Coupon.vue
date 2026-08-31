<script setup>
import { ref, onMounted } from 'vue';
import CouponTicket from '../components/CouponTicket.vue';
import api from '../api';

const deals = ref([]);
const loading = ref(true);
const coupons = ref([]);

async function load() {
  loading.value = true;
  try { const data = await Promise.all([api.deals(), api.coupons()]); deals.value = data[0] || []; coupons.value = (data[1] || []).map((c, i) => ({ ...c, scope: c.store_name || '星河里', expire: '有效期以券面为准', color: ['#7C3AED','#06B6D4','#F59E0B'][i % 3] })); } catch (e) {}
  loading.value = false;
}

async function claim(coupon) {
  try {
    await api.claimCoupon(coupon.id);
    coupon.claimed = true;
    if (navigator.vibrate) navigator.vibrate(30);
    alert('领取成功');
  } catch (e) { alert('领取失败：' + (e.message || '')); }
}
async function buy(deal) {
  try { await api.purchaseDeal(deal.id); await load(); alert('抢购成功，已加入会员资产'); }
  catch (e) { alert('抢购失败：' + (e.message || '')); }
}
function price(s) { return s.promo_price ?? s.price ?? s; }
onMounted(load);
</script>

<template>
  <div class="cp-page">
    <div class="cp-hero"><div class="cp-hero-t">今日特惠</div><div class="cp-hero-s">会员专属 · 先领券再下单</div></div>

    <div class="section-title">🔥 限时抢购</div>
    <div v-for="d in deals" :key="d.id" class="card deal">
      <div class="deal-info">
        <div class="deal-t">{{ d.title }}</div>
        <div class="deal-tag">今日特惠</div>
        <div class="deal-price"><span class="dp-cur">¥{{ d.price }}</span><span class="dp-stock">剩 {{ d.stock }} 份</span></div>
      </div>
      <button class="deal-buy" :class="{ purchased: d.purchased_quantity > 0 }" @click="buy(d)">{{ d.purchased_quantity > 0 ? `已购${d.purchased_quantity}` : '抢' }}</button>
    </div>
    <p v-if="!loading && !deals.length" class="empty">暂无特惠</p>

    <div class="section-title">🎫 优惠券</div>
    <CouponTicket v-for="c in coupons" :key="c.id" :coupon="c" :claimed="c.claimed" @claim="claim" />
  </div>
</template>

<style scoped>
.cp-page { min-height: 100%; background: var(--bg); padding: 0 18px 80px; }
.cp-hero { margin: 0 -18px; padding: 30px 20px 24px; background: linear-gradient(160deg, #1b1530, #312158 60%, #4c3a8c); color: #fff; }
.cp-hero-t { font-size: 22px; font-weight: 800; } .cp-hero-s { font-size: 13px; color: rgba(255,255,255,0.75); margin-top: 4px; }
.deal { display: flex; align-items: center; }
.deal-info { flex: 1; } .deal-t { font-weight: 700; font-size: 15px; }
.deal-tag { display: inline-block; font-size: 11px; color: var(--primary); background: #ede9fe; padding: 2px 10px; border-radius: 12px; margin: 6px 0; }
.deal-price { display: flex; align-items: baseline; gap: 10px; }
.dp-cur { font-size: 19px; font-weight: 800; color: var(--danger); } .dp-stock { font-size: 12px; color: #9CA3AF; }
.deal-buy { width: 54px; height: 54px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border: none; font-size: 17px; font-weight: 700; cursor: pointer; box-shadow: 0 6px 16px rgba(124,58,237,0.3); }
.empty { text-align: center; color: var(--muted); font-size: 14px; margin: 20px 0; }
</style>
