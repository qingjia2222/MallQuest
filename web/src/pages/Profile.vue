<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api, { clearAuth } from '../api';

const router = useRouter();
const member = ref({ points: 0, level: '普卡', expires_on: '' });
const reservationCount = ref(0);
const assets = ref({ coupons: 0, reservations: 0, tickets: 0, deal_purchases: 0 });
const loading = ref(true);

async function load() {
  loading.value = true;
  try { member.value = await api.memberPoints() || { points: 0 }; } catch (e) {}
  try { assets.value = await api.memberAssets(); reservationCount.value = assets.value.reservations || 0; } catch (e) {}
  loading.value = false;
}

function goCoupon() { router.push('/coupon'); }
function goReserve() { router.push('/reserve'); }
function goPlan() { router.push('/plan'); }
function goChat(q) { localStorage.setItem('prefill', q || '停车还有空位吗'); router.push('/chat'); }
function logout(){clearAuth();router.replace('/login')}
onMounted(load);
</script>

<template>
  <div class="pf-page">
    <div class="pf-hero">
      <div class="pf-avatar">🦸</div>
      <div class="pf-info"><div class="pf-name">会员中心</div><div class="pf-level">{{ member.level }}</div></div>
    </div>

    <div class="card pf-card">
      <div class="pf-points-head"><span>我的积分</span><span class="pf-num">{{ member.points }}</span></div>
      <div class="pf-next">积分有效期至 {{ member.expires_on || '2027-12-31' }} · 规则可随时问我</div>
    </div>

    <div class="pf-assets">
      <div class="pa" @click="goCoupon"><div class="pa-num">{{ assets.coupons }}</div><div class="pa-label">优惠券</div></div>
      <div class="pa" @click="goReserve"><div class="pa-num">{{ reservationCount }}</div><div class="pa-label">预约</div></div>
      <div class="pa" @click="goCoupon"><div class="pa-num">{{ assets.deal_purchases + assets.tickets }}</div><div class="pa-label">订单 / 票券</div></div>
    </div>

    <button class="logout" @click="logout">退出游客 / 会员端</button>
  </div>
</template>

<style scoped>
.pf-page { min-height: 100%; background: var(--bg); padding: 0 18px 80px; }
.pf-hero { margin: 0 -18px; padding: 34px 22px 28px; background: linear-gradient(160deg, #1b1530, #312158 60%, #4c3a8c); display: flex; align-items: center; gap: 16px; color: #fff; }
.pf-avatar { width: 64px; height: 64px; border-radius: 50%; background: rgba(255,255,255,0.16); display: flex; align-items: center; justify-content: center; font-size: 34px; }
.pf-name { font-size: 22px; font-weight: 800; }
.pf-level { font-size: 13px; color: #a78bfa; margin-top: 4px; background: rgba(255,255,255,0.14); display: inline-block; padding: 2px 12px; border-radius: 12px; }
.pf-card { margin-top: 16px; }
.pf-points-head { display: flex; justify-content: space-between; align-items: baseline; }
.pf-num { font-size: 26px; font-weight: 800; color: var(--primary); }
.pf-next { font-size: 12px; color: #9CA3AF; margin-top: 8px; }
.pf-assets { display: flex; gap: 12px; margin-top: 16px; }
.pa { flex: 1; background: #fff; border-radius: 16px; padding: 18px 0; display: flex; flex-direction: column; align-items: center; box-shadow: 0 5px 16px rgba(124,58,237,0.06); cursor: pointer; }
.pa-num { font-size: 24px; font-weight: 800; }
.pa-label { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
.chip-wrap { margin-top: 6px; }
.logout{width:100%;margin-top:24px;padding:12px;border:1px solid var(--border);border-radius:22px;background:#fff;color:var(--muted)}
</style>
