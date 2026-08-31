<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import Floors3D from '../components/Floors3D.vue';
import { renderMd } from '../utils/md';

const router = useRouter();
const stores = ref([]);
const loading = ref(false);
const focus = ref(null);        // 店铺详情浮层
const asking = ref(false);
const aiReply = ref('');

onMounted(async () => {
  loading.value = true;
  try {
    await api.ensureSession();
    stores.value = (await api.stores()) || [];
  } catch (e) {
    // session 失效兜底：重新扫一次
    try { const scan = await api.freshScan(); stores.value = (await api.stores()) || []; } catch (e2) {}
  } finally { loading.value = false; }
});

function open(store) { focus.value = store; aiReply.value = ''; }
function close() { focus.value = null; aiReply.value = ''; }
async function askAI() {
  if (!focus.value || asking.value) return;
  asking.value = true; aiReply.value = '';
  try {
    const q = `${focus.value.name} 这家店在几层？是什么类型？现在排队和余位怎么样？`;
    const data = await api.chat(q);
    aiReply.value = data.reply || '已查询。';
  } catch (e) { aiReply.value = '查询失败：' + (e.message || ''); }
  finally { asking.value = false; }
}

const emoji = { '火锅': '🍲', '日料': '🍣', '饮品': '🧋', '影院': '🎬', '甜品': '🍰', '咖啡': '☕', '餐厅': '🍽️' };
function cateEmoji(c) { return emoji[c] || '🏬'; }
function queueText(s) { const q = Number(s.queue_minutes || 0); return q > 0 ? `${q} 分钟` : '免排队'; }
function statusText(s) { return s.open_status === 'open' ? '营业中' : '未营业'; }
</script>

<template>
  <div class="home-page">
    <div class="home-hero">
      <div class="hh-title">星河里 · 购物中心</div>
      <div class="hh-sub">点击店铺查看实时状态 · 规划后在「规划」页看 3D 路线</div>
    </div>

    <!-- 页面中心：商场地图 -->
    <div class="home-map">
      <Floors3D v-if="stores.length" :route="null" :stores="stores" @select="open" />
      <div v-else class="hs-empty">地图店铺数据加载中…</div>
    </div>

    <!-- 下方：店铺详情列表 -->
    <div class="home-stores">
      <div class="hs-head">
        <span class="hs-title">店铺一览</span>
        <span class="hs-count">{{ stores.length }} 家</span>
      </div>
      <div v-if="loading" class="hs-empty">加载中…</div>
      <div v-else-if="!stores.length" class="hs-empty">暂无店铺数据</div>
      <div v-else class="hs-grid">
        <div v-for="s in stores" :key="s.id" class="store-card" @click="open(s)">
          <div class="sc-emoji">{{ cateEmoji(s.category) }}</div>
          <div class="sc-main">
            <div class="sc-name">{{ s.name }}</div>
            <div class="sc-meta"><span class="sc-badge">{{ s.category }}</span><span class="sc-floor">{{ s.floor }}F</span></div>
            <div class="sc-status">
              <span class="sc-tag" :class="{ hot: Number(s.queue_minutes || 0) > 0 }">排 {{ queueText(s) }}</span>
              <span class="sc-tag">余 {{ s.seats_available }}</span>
              <span class="sc-tag ok">{{ statusText(s) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 店铺详情浮层 -->
    <div v-if="focus" class="detail-mask" @click.self="close">
      <div class="detail">
        <div class="d-head">
          <div class="d-emoji">{{ cateEmoji(focus.category) }}</div>
          <div class="d-main">
            <div class="d-name">{{ focus.name }}</div>
            <div class="d-meta">
              <span class="d-badge">{{ focus.category }}</span>
              <span class="d-loc">{{ focus.floor }}F · 编码 {{ focus.store_code || '待分配' }} · {{ focus.avg_price ? '¥' + focus.avg_price + '/人' : '' }}</span>
            </div>
          </div>
          <div class="d-close" @click="close">×</div>
        </div>
        <div class="d-states">
          <div class="ds"><b>{{ queueText(focus) }}</b><span>排队</span></div>
          <div class="ds"><b>{{ focus.seats_available }}</b><span>余位</span></div>
          <div class="ds"><b>{{ statusText(focus) }}</b><span>营业</span></div>
        </div>
        <button class="ic-btn primary" :disabled="asking" @click="askAI">{{ asking ? '查询中…' : '🤖 问问 AI 这家店' }}</button>
        <div v-if="aiReply" class="d-reply" v-html="renderMd(aiReply)"></div>
        <div class="d-actions">
          <button class="ic-btn ghost" @click="close">关闭</button>
          <button class="ic-btn primary" @click="router.push('/chat')">去对话规划</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page { min-height: 100%; background: var(--bg); padding: 0 0 20px; }
.home-hero { padding: 18px 18px 14px; }
.hh-title { font-size: 22px; font-weight: 800; }
.hh-sub { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
.home-map { padding: 0 18px; }
.home-stores { padding: 18px 18px 20px; }
.hs-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.hs-title { font-weight: 800; font-size: 16px; }
.hs-count { font-size: 12px; color: #9CA3AF; }
.hs-empty { text-align: center; color: #9CA3AF; font-size: 13px; padding: 30px 0; }
.hs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.store-card { background: #fff; border-radius: 16px; padding: 14px; display: flex; gap: 12px; align-items: flex-start; box-shadow: 0 5px 16px rgba(124,58,237,0.06); cursor: pointer; }
.sc-emoji { width: 42px; height: 42px; border-radius: 12px; background: #ede9fe; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }
.sc-main { flex: 1; min-width: 0; }
.sc-name { font-size: 14px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sc-meta { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
.sc-badge { background: #f1f5f9; color: #475569; font-size: 11px; padding: 2px 8px; border-radius: 12px; }
.sc-floor { font-size: 11px; color: #9CA3AF; }
.sc-status { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.sc-tag { font-size: 11px; color: #475569; background: #f8fafc; border-radius: 12px; padding: 3px 8px; }
.sc-tag.hot { color: #d97706; background: #fef3c7; }
.sc-tag.ok { color: #059669; background: #ecfdf5; }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 50; display: flex; align-items: flex-end; }
.detail { width: 100%; background: #fff; border-radius: 20px 20px 0 0; padding: 22px; }
.d-head { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.d-emoji { width: 44px; height: 44px; border-radius: 12px; background: #ede9fe; text-align: center; line-height: 44px; font-size: 24px; }
.d-main { flex: 1; }
.d-name { font-weight: 700; font-size: 17px; }
.d-meta { font-size: 13px; color: #9CA3AF; margin-top: 3px; display: flex; gap: 8px; align-items: center; }
.d-badge { background: #ede9fe; color: #7C3AED; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.d-close { font-size: 24px; color: #9CA3AF; cursor: pointer; }
.d-states { display: flex; gap: 10px; margin-bottom: 14px; }
.ds { flex: 1; background: #f8fafc; border-radius: 12px; padding: 10px; text-align: center; }
.ds b { display: block; font-size: 15px; color: var(--primary-dark); }
.ds span { font-size: 11px; color: #9CA3AF; }
.d-reply { background: #f5f3ff; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.6; margin-top: 12px; }
.d-actions { display: flex; gap: 12px; margin-top: 14px; }
.ic-btn { flex: 1; border: none; border-radius: 20px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
