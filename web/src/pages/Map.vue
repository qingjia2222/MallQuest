<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import ParkingGauge from '../components/ParkingGauge.vue';
import Floors3D from '../components/Floors3D.vue';
import ItineraryCard from '../components/ItineraryCard.vue';
import { planStore, setCurrentPlan } from '../store/plan';
import { renderMd } from '../utils/md';

const router = useRouter();
const floorsRef = ref(null);
const parking = reactive({ free: 0, total: 0, areas: [] });
const focus = reactive({ show: false, store: null, aiReply: '', asking: false });
const live = ref([]);              // 方案中各店实时状态 + 预定情况
const sceneStores = ref([]);       // 后端合并后的甲组 3D 槽位 + 乙组实时店铺主数据
let liveTimer = null;

const hasPlan = computed(() => !!(planStore.current && planStore.current.itinerary && planStore.current.itinerary.length));
const isDone = computed(() => !!planStore.current && planStore.current.state === 'DONE');
const isNavigation = computed(() => !!planStore.current && planStore.current.source === 'navigation');
const activeRoute = computed(() => planStore.current && ((planStore.current.navigation) || (planStore.current.route)) || null);
const isCrossFloor = computed(() => new Set(((activeRoute.value && activeRoute.value.nodes) || []).map(n => n.floor)).size > 1);
const verticalMode = computed(() => activeRoute.value && activeRoute.value.vertical_mode || 'elevator');

// 规划路线直接使用后端走廊节点，不再根据店铺中心猜测连线。
const route3d = computed(() => {
  const plan = planStore.current;
  if (!plan) return null;
  const graphNodes = (plan.navigation && plan.navigation.nodes) || (plan.route && plan.route.nodes) || [];
  if (graphNodes.length) {
    return { stops: graphNodes.map((node, i) => ({
      floor: `F${node.floor || 1}`,
      x: ((Number(node.x || 500) - 500) / 1000) * 50,
      z: ((Number(node.y || 380) - 380) / 760) * 42,
      name: node.label || '', type: node.type || '', seq: i + 1
    })) };
  }
  // 禁止把店铺中心直接连线：旧方案若没有后端走廊节点，不展示可能穿墙的路线。
  return null;
});

async function load() {
  try {
    const [p, scene] = await Promise.all([api.parking(), api.mapScene()]);
    parking.free = p.total_free || 0;
    parking.total = (p.areas || []).reduce((a, x) => a + (x.total || 0), 0);
    parking.areas = p.areas || [];
    sceneStores.value = (scene && scene.stores) || [];
  } catch (e) {}
}

async function loadLive() {
  const plan = planStore.current;
  if (!plan || !plan.plan_id) {
    const destination = plan && plan.navigation && plan.navigation.destination_store;
    live.value = destination ? [{ ...destination, store_id: destination.id, display_name: destination.name }] : [];
    return;
  }
  try { const d = await api.liveStatus(plan.plan_id); live.value = (d && d.status) || []; } catch (e) {}
}
function startLive() {
  stopLive();
  loadLive();
  if (planStore.current && planStore.current.plan_id) liveTimer = setInterval(loadLive, 8000);
}
function stopLive() { if (liveTimer) { clearInterval(liveTimer); liveTimer = null; } }

onMounted(() => {
  load();
  if (hasPlan.value) startLive();
});
onBeforeUnmount(stopLive);
watch(() => planStore.current, (v) => { if (v && v.itinerary && v.itinerary.length) startLive(); else { live.value = []; stopLive(); } });

function onSelect(store) { focus.store = store; focus.aiReply = ''; focus.show = true; }
async function askAI() {
  if (!focus.store || focus.asking) return;
  focus.asking = true;
  try {
    const q = `${focus.store.name} 这家店在第几层？是什么类型的店？`;
    const data = await api.chat(q);
    focus.aiReply = data.reply || '已查询。';
  } catch (e) { focus.aiReply = '查询失败：' + (e.message || ''); }
  finally { focus.asking = false; }
}
function goPlan() {
  // 有方案则聚焦楼层路线；无方案回对话页去规划
  if (!hasPlan.value) { router.push('/chat'); return; }
  if (floorsRef.value && floorsRef.value.focusFloor) floorsRef.value.focusFloor('all');
}
function goChat() { router.push('/chat'); }
function replayRoute() { if (floorsRef.value && floorsRef.value.replayRoute) floorsRef.value.replayRoute(); }
async function switchTransfer(mode) {
  const plan=planStore.current;if(!plan||!isCrossFloor.value)return;
  try{
    if(plan.plan_id){setCurrentPlan(await api.confirmPlan(plan.plan_id,'modify',{vertical_mode:mode}));}
    else if(plan.navigation){
      const name=plan.navigation.destination_store.name;
      const navigation=await api.navigationResolve(`怎么走${mode==='escalator'?'扶梯':'直梯'}去${name}？`,plan.navigation.start_node);
      setCurrentPlan({...plan,navigation,itinerary:[plan.itinerary[0],navigation.destination_store]});
    }
    replayRoute();
  }catch(e){focus.aiReply='路线切换失败：'+(e.message||'');}
}
function formatArea(a) { return `${a.area} ${a.free}/${a.total}`; }
function onFloorsChanged(f) {}

function toStops(it) {
  return (it || []).map((s, i) => { const current=live.value.find(x=>x.store_id===s.id); return { time: s.time_label || `${i + 1}`, name: s.name || '', floor: s.floor ?? '', category: s.category || '', waiting: current ? current.queue_minutes : (s.waiting_time ?? (s.queue_minutes ?? null)), desc: s.desc || '' }; });
}
function actionLabel(a) {
  if (!a) return '';
  if (a.label) return a.label;
  const t = a.tool || a.action || '';
  if (t === 'queue') return `${a.store_id ? '已排号' : '已排队'}${a.queue_minutes ? '（约' + a.queue_minutes + '分钟）' : ''}`;
  const map = { claim_coupon: '领取优惠券', buy_ticket: '购买门票', reserve_restaurant: '预约餐厅', reserve_business_space: '预约商务空间' };
  return map[t] || t;
}
function itineraryView(plan){
  return {tag:plan.source==='online_agent'?'大模型规划':'为你定制',stops:toStops(plan.itinerary),
    actions:(plan.action_results||[]).map(a=>({label:actionLabel(a),ok:!['failed','unavailable'].includes(a.status)})),
    selectedStrategy:plan.route&&plan.route.selected_strategy,
    alternatives:((plan.route&&plan.route.alternatives)||[]).map(a=>({strategy:a.strategy,label:a.label,
      estimated_total_minutes:a.metrics.estimated_total_minutes,estimated_distance:a.metrics.estimated_distance,estimated_wait_minutes:a.metrics.estimated_wait_minutes}))};
}
async function chooseStrategy(strategy){
  const plan=planStore.current;if(!plan||!plan.plan_id)return;
  try{setCurrentPlan(await api.confirmPlan(plan.plan_id,'modify',{strategy}));}catch(e){focus.aiReply='方案切换失败：'+(e.message||'');}
}
</script>

<template>
  <div class="map-page">
    <div class="map-top">
      <div><div class="mt-name">规划</div><div class="mt-sub">即时导航 · 方案路线 · 店铺实时状态 · 预定情况</div></div>
    </div>

    <!-- 方案详情 + 店铺状态/预定情况（同步自 Chat 规划） -->
    <div v-if="hasPlan" class="plan-panel">
      <div class="pp-head">
        <div class="pp-title">{{ isNavigation ? '当前导航' : '当前方案' }}<span v-if="isNavigation" class="pp-nav">播放中</span><span v-else-if="isDone" class="pp-done">已确认</span><span v-else class="pp-wait">待确认</span></div>
        <div class="pp-actions">
          <button class="pp-btn ghost" @click="goChat">{{ isNavigation ? '关闭导航' : '调整方案' }}</button>
          <button class="pp-btn primary" @click="isNavigation ? replayRoute() : goPlan()">{{ isNavigation ? '重播路线' : '看路线' }}</button>
        </div>
      </div>

      <div v-if="isCrossFloor" class="transfer-selector"><span>换层方式</span><button :class="{active:verticalMode==='elevator'}" @click="switchTransfer('elevator')">直梯</button><button :class="{active:verticalMode==='escalator'}" @click="switchTransfer('escalator')">扶梯</button></div>

      <div v-if="isNavigation" class="nav-summary"><span>您当前所在位置</span><i>→</i><strong>{{planStore.current.itinerary[planStore.current.itinerary.length-1].name}}</strong></div>
      <ItineraryCard v-else :itinerary="itineraryView(planStore.current)" @confirm="goChat" @change="goChat" @strategy="chooseStrategy" @stoptap="goChat" />

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
            <template v-else-if="s.arrival_in_minutes != null">
              <span class="pps-line">距离预定时间约 {{ s.arrival_in_minutes }} 分钟</span>
            </template>
            <template v-else>
              <span class="pps-line">未预约 · 到店现等</span>
            </template>
          </div>
        </div>
        <div v-if="!live.length" class="pp-empty">正在加载店铺实时状态…</div>
      </div>
    </div>

    <Floors3D v-if="sceneStores.length" ref="floorsRef" :route="route3d" :stores="sceneStores" @select="onSelect" @floorschanged="onFloorsChanged" />

    <!-- 停车位 -->
    <div class="card parking-card">
      <ParkingGauge :free="parking.free" :total="parking.total" />
      <div class="parking-info">
        <div class="p-title">🚗 实时停车位</div>
        <div class="p-areas">
          <span v-for="a in parking.areas" :key="a.area" class="p-area">{{ formatArea(a) }}</span>
        </div>
      </div>
    </div>

    <!-- 店铺详情弹层 -->
    <div v-if="focus.show && focus.store" class="detail-mask" @click.self="focus.show = false">
      <div class="detail">
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
        <p class="d-desc">{{ focus.store.desc || '品类丰富的优质店铺，值得一逛。' }}</p>
        <div v-if="focus.store.tags && focus.store.tags.length" class="d-tags">
          <span v-for="t in focus.store.tags" :key="t" class="d-tag">{{ t }}</span>
        </div>
        <button class="ic-btn primary" :disabled="focus.asking" @click="askAI">{{ focus.asking ? '查询中…' : '🤖 问问 AI 这家店' }}</button>
        <div v-if="focus.aiReply" class="d-reply" v-html="renderMd(focus.aiReply)"></div>
        <div v-else-if="route3d && route3d.stops.length" class="d-reply">📍 已在楼层上显示规划路线（{{ route3d.stops.length }} 站）</div>
        <div class="d-actions">
          <button class="ic-btn ghost" @click="focus.show = false">关闭</button>
          <button class="ic-btn primary" @click="goChat">进对话</button>
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
.plan-panel { background: #fff; border: 1px solid #ede9fe; border-radius: 18px; padding: 16px; margin-bottom: 14px; box-shadow: 0 8px 24px rgba(124,58,237,0.08); }
.pp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.pp-title { font-weight: 800; font-size: 16px; display: flex; align-items: center; gap: 8px; }
.pp-done { background: #ecfdf5; color: #10B981; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 14px; }
.pp-nav { background:#fee2e2;color:#dc2626;font-size:11px;font-weight:700;padding:2px 10px;border-radius:14px; }
.pp-wait { background: #fef3c7; color: #d97706; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 14px; }
.pp-actions { display: flex; gap: 8px; }
.transfer-selector{display:flex;align-items:center;gap:8px;margin:-2px 0 12px;color:#6b7280;font-size:12px}.transfer-selector button{border:1px solid #ddd6fe;background:#fff;color:#6d28d9;border-radius:16px;padding:5px 14px}.transfer-selector button.active{background:#7c3aed;color:#fff;border-color:#7c3aed}
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
.pp-empty { text-align: center; color: #9CA3AF; font-size: 13px; padding: 12px 0; }
.nav-summary { display:flex;align-items:center;justify-content:center;gap:12px;background:#f5f3ff;border-radius:14px;padding:15px;color:#6b7280; }.nav-summary i{color:#ef4444;font-style:normal;font-size:20px}.nav-summary strong{color:#312e81}
.parking-card { display: flex; align-items: center; gap: 20px; }
.parking-info { flex: 1; }
.p-title { font-weight: 700; font-size: 15px; margin-bottom: 12px; }
.p-areas { display: flex; flex-wrap: wrap; gap: 8px; }
.p-area { background: #f9fafb; border-radius: 8px; padding: 6px 10px; font-size: 12px; color: var(--muted); }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 50; display: flex; align-items: flex-end; }
.detail { width: 100%; background: #fff; border-radius: 20px 20px 0 0; padding: 22px; }
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
.d-close { font-size: 24px; color: #9CA3AF; cursor: pointer; }
.d-reply { background: #f5f3ff; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.6; margin-top: 12px; color: var(--text); }
.d-actions { display: flex; gap: 12px; margin-top: 14px; }
.ic-btn { flex: 1; border: none; border-radius: 20px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
