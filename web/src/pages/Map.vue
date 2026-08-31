<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import ParkingGauge from '../components/ParkingGauge.vue';
import { planStore } from '../store/plan';

const router = useRouter();
const floor = ref(1);
const floorUrl = ref('');
const parking = reactive({ free: 0, total: 0, areas: [] });
const focus = reactive({ show: false, detail: null });
const routeMeta = ref('');
const loading = ref(true);
const stores = ref([]);

// 从共享 store 取当前方案
const plan = computed(() => planStore.current);

// 路线节点换算到 SVG viewBox(1000x760)
const pts = computed(() => {
  const nodes = plan.value && plan.value.route && plan.value.route.nodes;
  if (!nodes) return '';
  return nodes.filter(n => (n.floor || 1) === floor.value).map(n => `${n.x},${n.y}`).join(' ');
});

function loadFloor(f) {
  floor.value = f;
  floorUrl.value = api.mapFloorUrl(f);
}

async function load() {
  loading.value = true;
  try {
    const [p, scene] = await Promise.all([api.parking(), api.mapScene()]);
    parking.free = p.total_free || 0;
    parking.total = (p.areas || []).reduce((a, x) => a + (x.total || 0), 0);
    parking.areas = p.areas || [];
    stores.value = scene.stores || [];
  } catch (e) {}
  // 同步共享方案的路线元信息
  if (plan.value && plan.value.route && plan.value.route.estimated_distance) {
    routeMeta.value = `Dijkstra 估算距离 ${plan.value.route.estimated_distance}`;
  }
  loading.value = false;
}

onMounted(() => { loadFloor(1); load(); });

function goPlan() { router.push('/plan'); }
function goReserve() { router.push('/reserve'); }
function closeDetail() { focus.show = false; }
async function openStore(store) { try { focus.detail = await api.publicStore(store.id); focus.show = true; } catch(e) {} }

function formatArea(a) { return `${a.area} ${a.free}/${a.total}`; }
</script>

<template>
  <div class="map-page">
    <div class="map-top">
      <div><div class="mt-name">室内导览地图</div><div class="mt-sub">紫青连线为规划路线 · 后端 SVG 楼图</div></div>
      <button class="mt-btn" @click="goPlan">帮我规划</button>
    </div>

    <!-- 楼图 + 路线 -->
    <div class="map-wrap">
      <div class="floor-tabs">
        <span v-for="f in [1,2]" :key="f" class="floor-tab" :class="{ active: floor === f }" @click="loadFloor(f)">{{ f }}F</span>
      </div>
      <img :src="floorUrl" alt="楼层图" class="floor-img" />
      <svg v-if="pts" viewBox="0 0 1000 760" class="route-svg">
        <polyline :points="pts" class="route-line" />
      </svg>
      <button v-for="s in stores.filter(x=>x.floor===floor)" :key="s.id" class="store-dot" :style="{left:(s.pos_x/10)+'%',top:(s.pos_y/7.6)+'%'}" @click="openStore(s)" :title="s.name"><i></i><span>{{s.name}}</span></button>
      <p class="route-meta">{{ routeMeta || '扫描二维码或规划后，这里显示 Dijkstra 路线' }}</p>
    </div>

    <div v-if="focus.show && focus.detail" class="detail-mask" @click="closeDetail"><div class="detail" @click.stop><button class="close" @click="closeDetail">×</button><h2>{{focus.detail.name}}</h2><p>{{focus.detail.floor}}F · {{focus.detail.category}} · {{focus.detail.business_hours}}</p><div class="live"><span>营业 {{focus.detail.open_status}}</span><span>排队 {{focus.detail.queue_minutes}} 分钟</span><span>座位 {{focus.detail.seats_available}}</span></div><strong v-if="focus.detail.deal_title">当前优惠：{{focus.detail.deal_title}} · ¥{{focus.detail.deal_price}}</strong></div></div>

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

    <div class="card hint">💡 提示：先在对话里说「帮我规划约会」生成方案，再回到这里查看路线；或点右下角按钮直接去规划。</div>
  </div>
</template>

<style scoped>
.map-page { min-height: 100%; background: var(--bg); padding: 16px 18px; }
.map-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.mt-name { font-size: 20px; font-weight: 800; }
.mt-sub { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
.mt-btn { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border: none; border-radius: 24px; padding: 8px 18px; font-size: 13px; font-weight: 600; cursor: pointer; }
.map-wrap { position: relative; background: #fff; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 24px rgba(124,58,237,0.08); }
.floor-tabs { position: absolute; top: 12px; left: 12px; z-index: 5; display: flex; flex-direction: column; gap: 6px; }
.floor-tab { width: 34px; height: 30px; border-radius: 8px; background: rgba(255,255,255,0.92); color: var(--muted); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.08); cursor: pointer; }
.floor-tab.active { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.floor-img { width: 100%; display: block; }
.route-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.route-line { fill: none; stroke: #EF4444; stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; }
.store-dot{position:absolute;z-index:4;transform:translate(-50%,-50%);border:0;background:none;color:#312e81;font-size:10px;font-weight:700}.store-dot i{display:block;margin:auto;width:15px;height:15px;border-radius:50%;background:#7c3aed;border:3px solid #fff;box-shadow:0 3px 8px #4c1d9577}.detail-mask{position:fixed;z-index:20;inset:0;background:#11182766;display:flex;align-items:flex-end;justify-content:center}.detail{position:relative;width:min(720px,100%);padding:26px;background:#fff;border-radius:24px 24px 0 0}.close{position:absolute;right:18px;top:14px;border:0;background:none;font-size:28px}.detail p{color:#6b7280}.live{display:flex;gap:12px;margin:16px 0}.live span{background:#f5f3ff;color:#6d28d9;padding:7px 11px;border-radius:16px}.detail strong{color:#c2410c}
.route-meta { text-align: center; font-size: 12px; color: #9CA3AF; padding: 9px; }
.parking-card { display: flex; align-items: center; gap: 20px; }
.parking-info { flex: 1; }
.p-title { font-weight: 700; font-size: 15px; margin-bottom: 12px; }
.p-areas { display: flex; flex-wrap: wrap; gap: 8px; }
.p-area { background: #f9fafb; border-radius: 8px; padding: 6px 10px; font-size: 12px; color: var(--muted); }
.hint { font-size: 13px; color: var(--muted); }
</style>
