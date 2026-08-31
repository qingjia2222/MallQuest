<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import Floors3D from '../components/Floors3D.vue';
import ParkingGauge from '../components/ParkingGauge.vue';
import { planStore, setNavigateTarget } from '../store/plan';
import { renderMd } from '../utils/md';

const router = useRouter();
const stores = ref([]);
const loading = ref(false);
const focus = ref(null);        // 店铺详情浮层
const floorsRef = ref(null);
const asking = ref(false);
const aiReply = ref('');
const parking = ref({ total_free: 0, total: 0, areas: [] });

onMounted(async () => {
  loading.value = true;
  let qd = [];
  try {
    await api.ensureSession();
    qd = (await api.stores()) || [];
  } catch (e) {
    try { const scan = await api.freshScan(); qd = (await api.stores()) || []; } catch (e2) {}
  }
  stores.value = qd;
  try { const p = await api.parking(); parking.value = { ...p, total: (p.areas || []).reduce((sum, area) => sum + area.total, 0) }; } catch (e) {}
  loading.value = false;
});

const filterBy = ref('category');        // 分类维度：category | floor
const activeCat = ref('');               // 当前选中的具体分类（'' = 全部）
const catOptions = computed(() => { const s = new Set(); stores.value.forEach(x => { if (x.category) s.add(x.category); }); return ['全部', ...s]; });
const floorOptions = computed(() => { const s = new Set(); stores.value.forEach(x => { if (x.floor) s.add(String(x.floor) + 'F'); }); return ['全部', ...s]; });
const filteredStores = computed(() => {
  if (!activeCat.value) return stores.value;
  return stores.value.filter(s => filterBy.value === 'floor' ? (String(s.floor || '') + 'F') === activeCat.value : s.category === activeCat.value);
});
function setFilter(k) { filterBy.value = k; activeCat.value = ''; }

function open(store) { const live=stores.value.find((item) => item.id === store.id || item.name === store.name) || {}; focus.value = { ...store, ...live }; aiReply.value = ''; }
function close() { focus.value = null; aiReply.value = ''; }
function getGeoloc() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) { resolve(false); return; }
    navigator.geolocation.getCurrentPosition(() => resolve(true), () => resolve(false), { timeout: 6000, maximumAge: 60000 });
  });
}
async function goNavigate() {
  const s = focus.value;
  if (!s) return;
  let start = { name: '主入口', floor: 1, x: 1.69, z: 6.73 };
  try { const loc = await api.location(); if (loc) start = { name: loc.name || '主入口', floor: loc.floor || 1, x: loc.x, z: loc.z }; } catch (e) {}
  const geoloc = await getGeoloc();
  setNavigateTarget({ name: s.name, floor: s.floor || 1, pos_x: s.pos_x, pos_y: s.pos_y, start, geoloc, vertical_mode: 'elevator' });
  close();
  // 导航路线直接显示在首页的 3D 地图上，不跳转
}
function switchVertical(mode) {
  if (planStore.navigateTarget) setNavigateTarget({ ...planStore.navigateTarget, vertical_mode: mode });
}
async function askAI() {
  const s = focus.value;
  if (!s || asking.value) return;
  asking.value = true; aiReply.value = '';
  try {
    if (s.desc || (s.recommend && s.recommend.length)) {
      let t = (s.desc || '');
      if (s.recommend && s.recommend.length) t += '<br>🍽️ 推荐：' + s.recommend.join('、');
      if (s.now_showing && s.now_showing.length) t += '<br>🎬 正在热映：' + s.now_showing.join('、');
      aiReply.value = t;
      return;
    }
    const q = `${s.name} 这家店在几层？是什么类型？现在排队和余位怎么样？`;
    const data = await api.chat(q);
    aiReply.value = data.reply || '已查询。';
  } catch (e) { aiReply.value = '查询失败：' + (e.message || ''); }
  finally { asking.value = false; }
}
function heroBg(store) {
  const c = (store && store.category) || '';
  const map = { '餐饮': 'linear-gradient(135deg,#FFD9C7,#FFB3A7)', '饮品甜品': 'linear-gradient(135deg,#E4D6FF,#C9B6EE)', '零售': 'linear-gradient(135deg,#C9D9FF,#A9BFF0)', '影院': 'linear-gradient(135deg,#D0C3F2,#9B8BDE)', '服务设施': 'linear-gradient(135deg,#E4E8EF,#CBD3E0)' };
  return map[c] || 'linear-gradient(135deg,#F3E7FF,#D9CBF2)';
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
      <div class="hh-sub">点击店铺查看实时状态 · 规划后在「规划」页看路线</div>
    </div>

    <!-- 导航提示（首页内直接导航） -->
    <div v-if="planStore.navigateTarget" class="nav-bar">
      <span class="nb-text">🧭 正在导航到 <b>{{ planStore.navigateTarget.name }}</b>{{ planStore.navigateTarget.geoloc ? '（已定位）' : '' }}</span>
      <span v-if="planStore.navigateTarget.floor === 2" class="transfer-buttons"><button :class="{ active: planStore.navigateTarget.vertical_mode !== 'escalator' }" @click="switchVertical('elevator')">直梯</button><button :class="{ active: planStore.navigateTarget.vertical_mode === 'escalator' }" @click="switchVertical('escalator')">扶梯</button></span>
      <button class="nb-clear" @click="setNavigateTarget(null)">×</button>
    </div>

    <!-- 页面中心：商场地图 -->
    <div class="home-map">
      <Floors3D ref="floorsRef" :route="null" :navigate="planStore.navigateTarget ? { name: planStore.navigateTarget.name, floor: planStore.navigateTarget.floor, vertical_mode: planStore.navigateTarget.vertical_mode || 'elevator' } : null" @select="open" />
    </div>

    <div class="card home-parking">
      <ParkingGauge :free="parking.total_free" :total="parking.total" />
      <div><div class="hp-title">实时停车位</div><div class="hp-areas"><span v-for="a in parking.areas" :key="a.area">{{ a.area }} {{ a.free }}/{{ a.total }}</span></div></div>
    </div>

    <!-- 下方：店铺详情列表 -->
    <div class="home-stores">
      <div class="hs-head">
        <span class="hs-title">店铺一览</span>
        <span class="hs-count">{{ filteredStores.length }} 家</span>
      </div>
      <div class="filter-bar">
        <div class="fb-row">
          <div class="fb-label">按</div>
          <select class="fb-select" v-model="filterBy" @change="activeCat = ''">
            <option value="category">店铺种类</option>
            <option value="floor">楼层</option>
          </select>
        </div>
        <div class="fb-row">
          <div class="fb-label">分类</div>
          <select class="fb-select" v-model="activeCat">
            <option value="">全部</option>
            <option v-for="c in (filterBy === 'category' ? catOptions : floorOptions).slice(1)" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
      <div v-if="loading" class="hs-empty">加载中…</div>
      <div v-else-if="!stores.length" class="hs-empty">暂无店铺数据</div>
      <div v-else class="hs-grid">
        <div v-for="s in filteredStores" :key="s.name" class="store-card" @click="open(s)">
          <div class="sc-emoji">{{ s.hero || '🏬' }}</div>
          <div class="sc-main">
            <div class="sc-name">{{ s.name }}</div>
            <div class="sc-meta"><span class="sc-badge">{{ s.category }}</span><span v-if="s.floor" class="sc-floor">{{ s.floor }}F</span></div>
            <div class="sc-status">
              <span v-if="s.queue_minutes !== null" class="sc-tag" :class="{ hot: Number(s.queue_minutes || 0) > 0 }">排 {{ queueText(s) }}</span>
              <span v-if="s.seats_available !== null" class="sc-tag">余 {{ s.seats_available }}</span>
              <span class="sc-tag" :class="{ off: s.open_status !== 'open' }">{{ statusText(s) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 店铺详情浮层 -->
    <div v-if="focus" class="detail-mask" @click.self="close">
      <div class="detail">
        <div class="d-hero" :style="{ background: heroBg(focus) }">
          <span class="dh-emoji">{{ focus.hero || '🏬' }}</span>
          <span class="dh-name">{{ focus.name }}</span>
        </div>
        <div class="d-head">
          <div class="d-emoji">{{ cateEmoji(focus.category) }}</div>
          <div class="d-main">
            <div class="d-name">{{ focus.name }}</div>
            <div class="d-meta">
              <span class="d-badge">{{ focus.category }}</span>
              <span class="d-loc">{{ focus.floor }}F · {{ focus.avg_price ? '¥' + focus.avg_price + '/人' : '' }}</span>
            </div>
          </div>
          <div class="d-close" @click="close">×</div>
        </div>
        <div class="d-states">
          <div class="ds"><b>{{ queueText(focus) }}</b><span>排队</span></div>
          <div class="ds"><b>{{ focus.seats_available }}</b><span>余位</span></div>
          <div class="ds"><b>{{ statusText(focus) }}</b><span>营业</span></div>
        </div>
        <div v-if="focus.desc" class="d-desc">{{ focus.desc }}</div>
        <div v-if="focus.recommend && focus.recommend.length" class="d-reco">
          <div class="d-reco-title">🍽️ 推荐</div>
          <div class="d-reco-list"><span v-for="r in focus.recommend" :key="r" class="d-reco-item">{{ r }}</span></div>
        </div>
        <div v-if="focus.now_showing && focus.now_showing.length" class="d-reco">
          <div class="d-reco-title">🎬 正在热映</div>
          <div class="d-reco-list"><span v-for="m in focus.now_showing" :key="m" class="d-reco-item">{{ m }}</span></div>
        </div>
        <button class="ic-btn primary" :disabled="asking" @click="askAI">{{ asking ? '查询中…' : '🤖 问问 AI 这家店' }}</button>
        <div v-if="aiReply" class="d-reply" v-html="renderMd(aiReply)"></div>
        <div class="d-actions">
          <button class="ic-btn ghost" @click="close">关闭</button>
          <button class="ic-btn primary" @click="goNavigate">🧭 导航到此店铺</button>
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
.home-parking { margin: 14px 18px 0; display: flex; align-items: center; gap: 18px; }
.hp-title { font-weight: 800; margin-bottom: 8px; }
.hp-areas { display: flex; flex-wrap: wrap; gap: 6px; color: #64748b; font-size: 12px; }
.hp-areas span { background: #f8fafc; border-radius: 10px; padding: 4px 8px; }
.nav-bar { display: flex; align-items: center; justify-content: space-between; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 10px 14px; margin: 0 18px 12px; }
.nb-text { font-size: 14px; color: #047857; }
.nb-text b { font-weight: 700; }
.transfer-buttons { display: flex; gap: 5px; margin-left: auto; margin-right: 8px; }
.transfer-buttons button { border: 1px solid #a7f3d0; background: #fff; color: #047857; border-radius: 14px; padding: 4px 9px; cursor: pointer; }
.transfer-buttons button.active { background: #059669; color: #fff; }
.nb-clear { border: none; background: #fff; color: #047857; width: 26px; height: 26px; border-radius: 50%; font-size: 16px; cursor: pointer; line-height: 1; }
.home-stores { padding: 18px 18px 20px; }
.hs-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.hs-title { font-weight: 800; font-size: 16px; }
.hs-count { font-size: 12px; color: #9CA3AF; }
.hs-empty { text-align: center; color: #9CA3AF; font-size: 13px; padding: 30px 0; }
.filter-bar { background: #fff; border-radius: 14px; padding: 12px 14px; margin-bottom: 14px; box-shadow: 0 4px 14px rgba(124,58,237,0.06); }
.fb-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.fb-row:last-child { margin-bottom: 0; }
.fb-label { font-size: 12px; color: #9CA3AF; flex-shrink: 0; width: 26px; }
.fb-select { flex: 1; padding: 9px 12px; border: 1px solid var(--border); border-radius: 10px; background: #fff; font-size: 14px; color: var(--text); outline: none; }
.fb-select:focus { border-color: var(--primary); }
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
.sc-tag.off { color: #dc2626; background: #fee2e2; }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 50; display: flex; align-items: flex-end; }
.detail { width: 100%; background: #fff; border-radius: 20px 20px 0 0; padding: 22px; }
.d-hero { height: 130px; border-radius: 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; margin-bottom: 14px; }
.dh-emoji { font-size: 56px; line-height: 1; }
.dh-name { font-size: 16px; font-weight: 800; color: #3A3550; }
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
.d-desc { font-size: 13px; color: #6b7280; line-height: 1.6; margin-bottom: 12px; }
.d-reco { margin-bottom: 12px; }
.d-reco-title { font-size: 12px; font-weight: 700; color: #9CA3AF; margin-bottom: 6px; }
.d-reco-list { display: flex; flex-wrap: wrap; gap: 6px; }
.d-reco-item { background: #f5f3ff; color: #7C3AED; font-size: 12px; padding: 4px 12px; border-radius: 14px; }
.d-reply { background: #f5f3ff; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.6; margin-top: 12px; }
.d-actions { display: flex; gap: 12px; margin-top: 14px; }
.ic-btn { flex: 1; border: none; border-radius: 20px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
