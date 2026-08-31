<script setup>
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import Floors3D from '../components/Floors3D.vue';
import ItineraryCard from '../components/ItineraryCard.vue';
import { planStore, setCurrentPlan, setNavigateTarget } from '../store/plan';
import { renderMd } from '../utils/md';
import oakPlan from '../store/oakwood_plan.json';

const router = useRouter();
const floorsRef = ref(null);
const previewFloorsRef = ref(null);
const availableStores = ref([]);
const focus = reactive({ show: false, store: null, aiReply: '', asking: false });
const routePreviewOpen = ref(false);
const editSaving = ref(false);
const editNotice = ref('');
const editError = ref('');
const live = ref([]);              // 方案中各店实时状态 + 预定情况
let liveTimer = null;

const hasPlan = computed(() => !!(planStore.current && planStore.current.itinerary && planStore.current.itinerary.length));
const isDone = computed(() => !!planStore.current && planStore.current.state === 'DONE');

// 规划路线：按后端 itinerary 店名，在 oakwood 对应层找同名店的精确矩形坐标(cx/cz)
const route3d = computed(() => {
  const plan = planStore.current;
  if (!plan || !plan.itinerary || !plan.itinerary.length) return null;
  const st = (planStore.navigateTarget && planStore.navigateTarget.start) || { name: '当前位置', x: 1.69, z: 6.73 };
  const startFloor = Number(st.floor) || 1;
  const stops = [{ floor: startFloor, x: st.x ?? 1.69, z: st.z ?? 6.73, name: st.name || '当前位置', seq: 1 }];
  plan.itinerary.forEach((s, i) => {
    const floor = Number(s.floor) || 1;
    const pool = floor === 1 ? oakPlan.gd : oakPlan.up;
    const slot = pool.find(r => r.name === s.name);
    let px = 0, pz = 0;
    if (slot) { px = slot.cx; pz = slot.cz; }
    else { px = ((s.pos_x || 500) - 500) / 1000 * 30; pz = ((s.pos_y || 500) - 500) / 1000 * 30; }
    stops.push({ floor, x: px, z: pz, name: s.name, seq: i + 2 });
  });
  return { stops, vertical_mode: (plan.route && plan.route.vertical_mode) || 'elevator' };
});
// 导航到单店：起点（同层出入口/电梯）→ 目标店铺，绿色路线
const navRoute = computed(() => {
  const t = planStore.navigateTarget;
  if (!t || !t.name) return null;
  const floor = t.floor ? 'F' + t.floor : 'F1';
  const pool = floor === 'F1' ? oakPlan.gd : oakPlan.up;
  const slot = pool.find(r => r.name === t.name);
  let tx, tz;
  if (slot) { tx = slot.cx; tz = slot.cz; }
  else { tx = ((t.pos_x || 500) - 500) / 1000 * 30; tz = ((t.pos_y || 500) - 500) / 1000 * 30; }
  const st = (t.start && typeof t.start.x === 'number') ? t.start
    : (floor === 'F1'
       ? (oakPlan.gd_core && oakPlan.gd_core.find(r => r.type === 'entrance')) || { x: 1.69, z: 6.73 }
       : (oakPlan.up_core && oakPlan.up_core.find(r => r.type === 'lift')) || { x: 0.9, z: 3.22 });
  const sX = st.x, sZ = st.z;
  return { stops: [
    { floor, x: sX, z: sZ, name: '起点', seq: 1 },
    { floor, x: tx, z: sZ, name: '走廊', seq: 2 },
    { floor, x: tx, z: tz, name: t.name, seq: 3 }
  ] };
});
const displayRoute = computed(() => planStore.navigateTarget ? (navRoute.value || route3d.value) : route3d.value);
const isCrossFloorRoute = computed(() => route3d.value && new Set(route3d.value.stops.map((stop) => Number(stop.floor))).size > 1);

async function load() {
  try {
    availableStores.value = await api.stores() || [];
  } catch (e) {}
}

async function loadLive() {
  const plan = planStore.current;
  if (!plan || !plan.plan_id) { live.value = []; return; }
  try { const d = await api.liveStatus(plan.plan_id); live.value = (d && d.status) || []; } catch (e) {}
}
function startLive() {
  stopLive();
  loadLive();
  liveTimer = setInterval(loadLive, 8000);
}
function stopLive() { if (liveTimer) { clearInterval(liveTimer); liveTimer = null; } }

onMounted(() => {
  load();
  if (hasPlan.value) startLive();
});
onBeforeUnmount(stopLive);
watch(() => planStore.current, (v) => { if (v && v.itinerary && v.itinerary.length) startLive(); else { live.value = []; stopLive(); } });

function onSelect(store) { focus.store = availableStores.value.find((item) => item.id === store.id || item.name === store.name) || store; focus.aiReply = ''; focus.show = true; }
async function askAI() {
  const s = focus.store;
  if (!s || focus.asking) return;
  focus.asking = true;
  try {
    if (s.desc || (s.recommend && s.recommend.length)) {
      let t = (s.desc || '');
      if (s.recommend && s.recommend.length) t += '<br>🍽️ 推荐：' + s.recommend.join('、');
      if (s.now_showing && s.now_showing.length) t += '<br>🎬 正在热映：' + s.now_showing.join('、');
      focus.aiReply = t;
      return;
    }
    const q = `${s.name} 这家店在第几层？是什么类型的店？`;
    const data = await api.chat(q);
    focus.aiReply = data.reply || '已查询。';
  } catch (e) { focus.aiReply = '查询失败：' + (e.message || ''); }
  finally { focus.asking = false; }
}
function heroBg(store) {
  const c = (store && store.category) || '';
  const map = { '餐饮': 'linear-gradient(135deg,#FFD9C7,#FFB3A7)', '饮品甜品': 'linear-gradient(135deg,#E4D6FF,#C9B6EE)', '零售': 'linear-gradient(135deg,#C9D9FF,#A9BFF0)', '影院': 'linear-gradient(135deg,#D0C3F2,#9B8BDE)', '服务设施': 'linear-gradient(135deg,#E4E8EF,#CBD3E0)' };
  return map[c] || 'linear-gradient(135deg,#F3E7FF,#D9CBF2)';
}
function fmStatus(s) { return s.open_status === 'open' ? '营业中' : '未营业'; }
function fmQ(s) { const q = Number(s.queue_minutes || 0); return q > 0 ? q + ' 分钟' : '免排队'; }
function goPlan() {
  // 无方案回对话页去规划；有方案则弹出可重播的沉浸式路线预览。
  if (!hasPlan.value) { router.push('/chat'); return; }
  if (planStore.navigateTarget) setNavigateTarget(null);
  routePreviewOpen.value = true;
  nextTick(() => previewFloorsRef.value && previewFloorsRef.value.replayRoute());
}
function goChat() { router.push('/chat'); }
// —— 手动编辑推荐方案（规划页内直接调整顺序/删除/添加店铺）——
const editMode = ref(false);
const addSel = ref('');
const editOptions = computed(() => availableStores.value.filter((store) => store.open_status === 'open'));
function normalizeClock(value) {
  const match = String(value || '').match(/(\d{1,2})(?::|点)(\d{2})?/);
  if (!match) return '';
  let hour = Number(match[1]);
  if (/下午|晚上|晚/.test(String(value)) && hour < 12) hour += 12;
  return `${String(hour).padStart(2, '0')}:${String(Number(match[2] || 0)).padStart(2, '0')}`;
}
function defaultClock(index) {
  const base = normalizeClock(planStore.current && planStore.current.slots && planStore.current.slots.time) || '18:00';
  const [hour, minute] = base.split(':').map(Number);
  const total = hour * 60 + minute + index * 45;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}
function startEdit() {
  editNotice.value = ''; editError.value = '';
  if (isDone.value) { editError.value = '该方案已确认并执行，事务快照不能覆盖；请点“换一版”生成可编辑的新方案。'; return; }
  planStore.current.itinerary.forEach((stop, index) => { stop.time_label = normalizeClock(stop.time_label) || defaultClock(index); });
  editMode.value = true;
}
async function finishEdit() {
  if (!planStore.current || !planStore.current.plan_id) { editMode.value = false; return; }
  if (!planStore.current.itinerary.length) { editError.value = '方案至少保留一个店铺。'; return; }
  editSaving.value = true; editError.value = ''; editNotice.value = '';
  try {
    const itinerary = planStore.current.itinerary.map((s) => ({ id: s.id, time_label: s.time_label || '' }));
    setCurrentPlan(await api.updatePlan(planStore.current.plan_id, { itinerary }));
    editMode.value = false; await loadLive();
    editNotice.value = '方案已保存，路线已按新顺序重新生成。';
    goPlan();
  } catch (e) { editError.value = '方案保存失败：' + (e.message || ''); }
  finally { editSaving.value = false; }
}
function removeStop(i) { if (planStore.current) planStore.current.itinerary.splice(i, 1); }
function moveStop(i, d) {
  const arr = planStore.current ? planStore.current.itinerary : null;
  if (!arr) return;
  const j = i + d;
  if (j >= 0 && j < arr.length) { const t = arr[i]; arr[i] = arr[j]; arr[j] = t; }
}
function addStopSel() {
  const id = addSel.value; addSel.value = ''; if (!id) return;
  const store = availableStores.value.find((item) => item.id === id); if (!store) return;
  planStore.current.itinerary.push({ ...store, time_label: '' });
}
// 换一版：把当前方案引用发到对话，让 agent 换一版
function goRevise() {
  const plan = planStore.current;
  const stores = ((plan && plan.itinerary) || []).map((s) => s.name || s.title).join('、');
  localStorage.setItem('plan_ref', stores);
  localStorage.setItem('prefill', '请根据上面这份方案换一版，重新排一条更优的路线');
  router.push('/chat');
}
function getGeoloc() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) { resolve(false); return; }
    navigator.geolocation.getCurrentPosition(() => resolve(true), () => resolve(false), { timeout: 6000, maximumAge: 60000 });
  });
}
async function goNavigate() {
  const s = focus.store;
  if (!s) return;
  let start = { name: '主入口', floor: 1, x: 1.69, z: 6.73 };
  try { const loc = await api.location(); if (loc) start = { name: loc.name || '主入口', floor: loc.floor || 1, x: loc.x, z: loc.z }; } catch (e) {}
  const geoloc = await getGeoloc();
  setNavigateTarget({ name: s.name, floor: s.floor || 1, pos_x: s.pos_x, pos_y: s.pos_y, start, geoloc });
  focus.show = false;
}
function formatArea(a) { return `${a.area} ${a.free}/${a.total}`; }
function onFloorsChanged(f) {}
function replayRoute() {
  if (floorsRef.value && floorsRef.value.focusFloor) floorsRef.value.focusFloor('all');
  if (floorsRef.value && floorsRef.value.drawRoute) floorsRef.value.drawRoute(route3d.value);
}
function replayPreview() {
  if (previewFloorsRef.value && previewFloorsRef.value.replayRoute) previewFloorsRef.value.replayRoute();
}
async function switchPlanVertical(mode) {
  if (!planStore.current || !planStore.current.plan_id || (planStore.current.route && planStore.current.route.vertical_mode === mode)) { replayPreview(); return; }
  try {
    setCurrentPlan(await api.updatePlan(planStore.current.plan_id, { vertical_mode: mode }));
    editNotice.value = `已切换为${mode === 'escalator' ? '扶梯' : '直梯'}路线。`;
    await nextTick(); replayPreview();
  } catch (e) { editError.value = '换层路线切换失败：' + (e.message || ''); }
}
function switchNavVertical(mode) {
  if (!planStore.navigateTarget) return;
  setNavigateTarget({ ...planStore.navigateTarget, vertical_mode: mode });
}

function toStops(it) {
  const people = (planStore.current && planStore.current.slots && planStore.current.slots.people) || 2;
  return (it || []).map((s, i) => {
    const info = availableStores.value.find((item) => item.id === s.id || item.name === s.name) || {};
    return { time: s.time_label || `${i + 1}`, name: s.name || '', floor: s.floor ?? '', category: s.category || '', waiting: s.waiting_time ?? (s.queue_minutes ?? null), desc: info.desc || s.desc || '', recommend: info.recommend || [], now_showing: info.now_showing || [], people };
  });
}
function storeReco(name) { const info = availableStores.value.find((item) => item.name === name) || {}; return (info.recommend || []).join('、'); }
function actionLabel(a) {
  if (!a) return '';
  if (a.label) return a.label;
  const t = a.tool || a.action || '';
  if (t === 'queue') return `${a.store_id ? '已排号' : '已排队'}${a.queue_minutes ? '（约' + a.queue_minutes + '分钟）' : ''}`;
  const map = { claim_coupon: '领取优惠券', buy_ticket: '购买门票', reserve_restaurant: '预约餐厅', reserve_business_space: '预约商务空间' };
  return map[t] || t;
}
</script>

<template>
  <div class="map-page">
    <div class="map-top">
      <div><div class="mt-name">规划</div><div class="mt-sub">方案路线 · 店铺实时状态 · 预定情况</div></div>
    </div>

    <!-- 导航提示（从首页"导航到此店铺"跳转而来） -->
    <div v-if="planStore.navigateTarget" class="nav-bar">
      <span class="nb-text">🧭 正在导航到 <b>{{ planStore.navigateTarget.name }}</b>（{{ planStore.navigateTarget.geoloc ? '已定位' : '当前位置' }} · {{ planStore.navigateTarget.floor === 2 ? (planStore.navigateTarget.vertical_mode === 'escalator' ? '乘扶梯至2F' : '乘直梯至2F') : '从主入口' }}）</span>
      <span v-if="planStore.navigateTarget.floor === 2" class="transfer-buttons"><button :class="{ active: planStore.navigateTarget.vertical_mode !== 'escalator' }" @click="switchNavVertical('elevator')">直梯</button><button :class="{ active: planStore.navigateTarget.vertical_mode === 'escalator' }" @click="switchNavVertical('escalator')">扶梯</button></span>
      <button class="nb-clear" @click="setNavigateTarget(null)">×</button>
    </div>

    <!-- 方案详情 + 店铺状态/预定情况（同步自 Chat 规划） -->
    <div v-if="hasPlan" class="plan-panel">
      <div class="pp-head">
        <div class="pp-title">🎯 当前方案<span v-if="isDone" class="pp-done">已确认</span><span v-else class="pp-wait">待确认</span></div>
        <div class="pp-actions">
          <button class="pp-btn ghost" @click="startEdit">调整方案</button>
          <button class="pp-btn primary" @click="goPlan">看路线</button>
        </div>
      </div>
      <p v-if="editNotice" class="edit-notice">{{ editNotice }}</p>
      <p v-if="editError" class="edit-error">{{ editError }}</p>

      <ItineraryCard v-if="!editMode" :itinerary="{
          tag: planStore.current.source === 'online_agent' ? '大模型规划' : '为你定制',
          stops: toStops(planStore.current.itinerary),
          actions: (planStore.current.action_results || []).map(a => ({ label: actionLabel(a), ok: a.status !== 'failed' }))
        }" hide-confirm @change="goRevise" @stoptap="goChat" />

      <!-- 手动编辑推荐方案（规划页内直接调整顺序/删除/添加店铺） -->
      <div v-else class="plan-editor">
        <div class="pe-title">✏️ 编辑推荐方案（调整顺序 / 删除 / 添加店铺）</div>
        <div v-for="(s, idx) in planStore.current.itinerary" :key="idx" class="pe-row">
          <span class="pe-idx">{{ idx + 1 }}</span>
          <span class="pe-name">{{ s.name }}</span>
          <input v-model="s.time_label" class="pe-time" type="time" aria-label="到店时间" />
          <span class="pe-ops">
            <button class="pe-btn" @click="moveStop(idx, -1)">↑</button>
            <button class="pe-btn" @click="moveStop(idx, 1)">↓</button>
            <button class="pe-btn del" @click="removeStop(idx)">×</button>
          </span>
        </div>
        <div class="pe-add">
          <select v-model="addSel" class="pe-select"><option value="">＋ 添加店铺</option><option v-for="s in editOptions" :key="s.id" :value="s.id">{{ s.name }} · {{ s.floor }}F</option></select>
          <button class="pe-btn add" @click="addStopSel">添加</button>
        </div>
        <button class="ic-btn primary pe-done" :disabled="editSaving" @click="finishEdit">{{ editSaving ? '保存并重算路线中…' : '完成编辑' }}</button>
      </div>

      <!-- 各店实时状态 + 预定情况 -->
      <div class="pp-status">
        <div class="pp-status-title">店铺实时状态 · 预定情况</div>
        <div v-for="s in live" :key="s.store_id" class="pp-store">
          <div class="pps-name">{{ s.display_name || s.store_id }}</div>
          <div class="pps-tags">
            <span class="pps-tag" :class="{ hot: Number(s.queue_minutes || 0) > 0 }">排 {{ s.queue_minutes }} 分钟</span>
            <span class="pps-tag">余 {{ s.seats_available }}</span>
            <span class="pps-tag" :class="{ off: s.open_status !== 'open' }">{{ s.open_status === 'open' ? '营业' : '未营业' }}</span>
          </div>
          <div class="pps-booking">
            <template v-if="s.reservation_status">
              <span class="pps-line" :class="{ ok: s.can_dine_on_time }">
                {{ s.reservation_status === 'queued' ? '已排号' : '已预约' }}
                · 前面约 {{ s.ahead_tables }} 桌
                · {{ s.can_dine_on_time ? '可准时' : '需等待' }}
              </span>
            </template>
            <template v-else-if="s.arrival_in_minutes !== null">
              <span class="pps-line">距离预定时间约 {{ s.arrival_in_minutes }} 分钟</span>
            </template>
            <template v-else>
              <span class="pps-line">未预约 · 到店现等</span>
            </template>
          </div>
          <div v-if="storeReco(s.display_name)" class="pps-reco">🍽️ {{ (planStore.current.slots && planStore.current.slots.people) || 2 }}人推荐：{{ storeReco(s.display_name) }}</div>
        </div>
        <div v-if="!live.length" class="pp-empty">正在加载店铺实时状态…</div>
      </div>
    </div>

    <div id="plan-map">
      <Floors3D ref="floorsRef" :route="route3d" :navigate="planStore.navigateTarget ? { name: planStore.navigateTarget.name, floor: planStore.navigateTarget.floor, vertical_mode: planStore.navigateTarget.vertical_mode || 'elevator' } : null" @select="onSelect" @floorschanged="onFloorsChanged" />
    </div>

    <div v-if="routePreviewOpen && route3d" class="route-preview-mask">
      <div class="route-preview-card">
        <div class="route-preview-head">
          <div><b>路线预览</b><span>红点从当前位置沿走廊依次前往方案店铺</span></div>
          <button @click="routePreviewOpen = false">×</button>
        </div>
        <Floors3D ref="previewFloorsRef" :route="route3d" />
        <div class="route-preview-actions">
          <template v-if="isCrossFloorRoute"><button class="pp-btn" :class="route3d.vertical_mode === 'elevator' ? 'primary' : 'ghost'" @click="switchPlanVertical('elevator')">直梯路线</button><button class="pp-btn" :class="route3d.vertical_mode === 'escalator' ? 'primary' : 'ghost'" @click="switchPlanVertical('escalator')">扶梯路线</button></template>
          <button class="pp-btn ghost" @click="replayPreview">重播</button>
          <button class="pp-btn primary" @click="routePreviewOpen = false">完成预览</button>
        </div>
      </div>
    </div>

    <!-- 店铺详情弹层 -->
    <div v-if="focus.show && focus.store" class="detail-mask" @click.self="focus.show = false">
      <div class="detail">
        <div class="d-hero" :style="{ background: heroBg(focus.store) }">
          <span class="dh-emoji">{{ focus.store.hero || '🏬' }}</span>
          <span class="dh-name">{{ focus.store.name }}</span>
        </div>
        <div class="d-head">
          <div class="d-emoji">📍</div>
          <div class="d-main">
            <div class="d-name">{{ focus.store.name }}</div>
            <div class="d-meta">
              <span class="d-badge">{{ focus.store.category || focus.store.cat }}</span>
              <span class="d-loc">{{ focus.store.loc || focus.store.floor }} · 编码 {{ focus.store.store_code || '待分配' }}</span>
            </div>
          </div>
          <div class="d-close" @click="focus.show = false">×</div>
        </div>
        <div class="d-states">
          <div class="ds"><b>{{ fmQ(focus.store) }}</b><span>排队</span></div>
          <div class="ds"><b>{{ focus.store.seats_available ?? '--' }}</b><span>余位</span></div>
          <div class="ds"><b>{{ fmStatus(focus.store) }}</b><span>营业</span></div>
        </div>
        <p class="d-desc">{{ focus.store.desc || '品类丰富的优质店铺，值得一逛。' }}</p>
        <div v-if="focus.store.tags && focus.store.tags.length" class="d-tags">
          <span v-for="t in focus.store.tags" :key="t" class="d-tag">{{ t }}</span>
        </div>
        <div v-if="focus.store.recommend && focus.store.recommend.length" class="d-reco">
          <div class="d-reco-title">🍽️ 推荐</div>
          <div class="d-reco-list"><span v-for="r in focus.store.recommend" :key="r" class="d-reco-item">{{ r }}</span></div>
        </div>
        <div v-if="focus.store.now_showing && focus.store.now_showing.length" class="d-reco">
          <div class="d-reco-title">🎬 正在热映</div>
          <div class="d-reco-list"><span v-for="m in focus.store.now_showing" :key="m" class="d-reco-item">{{ m }}</span></div>
        </div>
        <button class="ic-btn primary" :disabled="focus.asking" @click="askAI">{{ focus.asking ? '查询中…' : '🤖 问问 AI 这家店' }}</button>
        <div v-if="focus.aiReply" class="d-reply" v-html="renderMd(focus.aiReply)"></div>
        <div v-else-if="route3d && route3d.stops.length" class="d-reply">📍 已在楼层上显示规划路线（{{ route3d.stops.length }} 站）</div>
        <div class="d-actions">
          <button class="ic-btn ghost" @click="focus.show = false">关闭</button>
          <button class="ic-btn primary" @click="goNavigate">🧭 导航到此店铺</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-page { min-height: 100%; background: var(--bg); padding: 16px 18px; }
.map-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.mt-name { font-size: 20px; font-weight: 800; }
.mt-sub { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
.nav-bar { display: flex; align-items: center; justify-content: space-between; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 10px 14px; margin-bottom: 12px; }
.nb-text { font-size: 14px; color: #047857; }
.nb-text b { font-weight: 700; }
.nb-clear { border: none; background: #fff; color: #047857; width: 26px; height: 26px; border-radius: 50%; font-size: 16px; cursor: pointer; line-height: 1; }
.transfer-buttons { display: flex; gap: 5px; margin-left: auto; }
.transfer-buttons button { border: 1px solid #a7f3d0; background: #fff; color: #047857; border-radius: 14px; padding: 4px 9px; cursor: pointer; }
.transfer-buttons button.active { background: #059669; color: #fff; }
.plan-panel { background: #fff; border: 1px solid #ede9fe; border-radius: 18px; padding: 16px; margin-bottom: 14px; box-shadow: 0 8px 24px rgba(124,58,237,0.08); }
.pp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.pp-title { font-weight: 800; font-size: 16px; display: flex; align-items: center; gap: 8px; }
.pp-done { background: #ecfdf5; color: #10B981; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 14px; }
.pp-wait { background: #fef3c7; color: #d97706; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 14px; }
.edit-notice,.edit-error { margin: 0 0 10px; padding: 9px 12px; border-radius: 10px; font-size: 13px; }
.edit-notice { color: #047857; background: #ecfdf5; }
.edit-error { color: #b91c1c; background: #fef2f2; }
.pp-actions { display: flex; gap: 8px; }
.pp-btn { border: none; border-radius: 18px; padding: 7px 14px; font-size: 12px; font-weight: 600; cursor: pointer; }
.pp-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.pp-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.pp-status { margin-top: 14px; }
.pp-status-title { font-weight: 700; font-size: 13px; color: var(--muted); margin-bottom: 10px; }
.pp-store { border: 1px solid var(--border); border-radius: 14px; padding: 12px 14px; margin-bottom: 10px; }
.pps-name { font-size: 14px; font-weight: 700; }
.pps-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pps-tag { font-size: 12px; color: #475569; background: #f8fafc; border-radius: 12px; padding: 3px 10px; }
.pps-tag.hot { color: #d97706; background: #fef3c7; }
.pps-tag.off { color: #dc2626; background: #fee2e2; }
.pps-booking { margin-top: 10px; }
.pps-line { font-size: 13px; color: var(--text); display: inline-flex; background: #ede9fe; padding: 5px 12px; border-radius: 16px; }
.pps-line.ok { background: #ecfdf5; color: #059669; }
.pps-reco { font-size: 12px; color: #7C3AED; margin-top: 8px; line-height: 1.5; }
.pp-empty { text-align: center; color: #9CA3AF; font-size: 13px; padding: 12px 0; }
.plan-editor { background: #fff; border: 1px solid var(--border); border-radius: 14px; padding: 14px; margin-top: 12px; }
.pe-title { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
.pe-row { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 10px; background: #f8fafc; margin-bottom: 6px; }
.pe-idx { width: 20px; height: 20px; border-radius: 50%; background: #ede9fe; color: #7C3AED; font-size: 12px; font-weight: 700; text-align: center; flex-shrink: 0; }
.pe-name { flex: 1; font-size: 14px; font-weight: 600; }
.pe-time { width: 92px; border: 1px solid var(--border); border-radius: 8px; padding: 5px 7px; color: var(--text); background: #fff; }
.pe-ops { display: flex; gap: 5px; }
.pe-btn { width: 26px; height: 26px; border-radius: 8px; border: none; background: #fff; color: #7C3AED; font-size: 14px; cursor: pointer; }
.pe-btn.del { color: #dc2626; }
.pe-add { display: flex; gap: 8px; margin-top: 8px; }
.pe-select { flex: 1; padding: 9px 10px; border: 1px solid var(--border); border-radius: 10px; font-size: 14px; }
.pe-btn.add { width: auto; padding: 0 14px; background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.pe-done { margin-top: 12px; width: 100%; }
.route-preview-mask { position: fixed; inset: 0; z-index: 120; background: rgba(15,23,42,.72); display: flex; align-items: center; justify-content: center; padding: 18px; box-sizing: border-box; }
.route-preview-card { width: min(760px,100%); max-height: calc(100vh - 36px); overflow: auto; background: #f8fafc; border-radius: 22px; padding: 16px; box-sizing: border-box; box-shadow: 0 24px 80px rgba(0,0,0,.35); }
.route-preview-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.route-preview-head div { display: flex; flex-direction: column; gap: 3px; }
.route-preview-head b { font-size: 18px; }
.route-preview-head span { color: #64748b; font-size: 12px; }
.route-preview-head button { border: 0; background: #e2e8f0; width: 34px; height: 34px; border-radius: 50%; font-size: 21px; cursor: pointer; }
.route-preview-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
.parking-card { display: flex; align-items: center; gap: 20px; }
.parking-info { flex: 1; }
.p-title { font-weight: 700; font-size: 15px; margin-bottom: 12px; }
.p-areas { display: flex; flex-wrap: wrap; gap: 8px; }
.p-area { background: #f9fafb; border-radius: 8px; padding: 6px 10px; font-size: 12px; color: var(--muted); }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 50; display: flex; align-items: flex-end; }
.detail { width: 100%; background: #fff; border-radius: 20px 20px 0 0; padding: 22px; }
.d-hero { height: 130px; border-radius: 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; margin-bottom: 14px; }
.dh-emoji { font-size: 56px; line-height: 1; }
.dh-name { font-size: 16px; font-weight: 800; color: #3A3550; }
.d-states { display: flex; gap: 10px; margin-bottom: 14px; }
.ds { flex: 1; background: #f8fafc; border-radius: 12px; padding: 10px; text-align: center; }
.ds b { display: block; font-size: 15px; color: #4A3F6B; }
.ds span { font-size: 11px; color: #9CA3AF; }
.d-head { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.d-emoji { width: 44px; height: 44px; border-radius: 12px; background: #ede9fe; display: flex; align-items: center; justify-content: center; font-size: 24px; }
.d-main { flex: 1; }
.d-name { font-weight: 700; font-size: 17px; }
.d-meta { font-size: 13px; color: #9CA3AF; margin-top: 3px; display: flex; align-items: center; gap: 8px; }
.d-badge { background: #ede9fe; color: #7C3AED; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.d-loc { font-size: 12px; }
.d-desc { font-size: 14px; color: var(--text); margin: 12px 0 8px; line-height: 1.6; }
.d-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.d-tag { background: #f1f5f9; color: #475569; font-size: 12px; padding: 4px 12px; border-radius: 16px; }
.d-reco { margin-bottom: 12px; }
.d-reco-title { font-size: 12px; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
.d-reco-list { display: flex; flex-wrap: wrap; gap: 6px; }
.d-reco-item { background: #f5f3ff; color: var(--primary); font-size: 12px; padding: 4px 12px; border-radius: 14px; }
.d-close { font-size: 24px; color: #9CA3AF; cursor: pointer; }
.d-reply { background: #f5f3ff; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.6; margin-top: 12px; color: var(--text); }
.d-actions { display: flex; gap: 12px; margin-top: 14px; }
.ic-btn { flex: 1; border: none; border-radius: 20px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
