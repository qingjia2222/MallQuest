<script setup>
import { reactive, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import { planStore } from '../store/plan';

const router = useRouter();
const form = reactive({ store_id: '', time: '19:00', reserved_for: '今晚 19:00', people: 2, notes: '' });
const confirmed = ref(false);
const resultId = ref('');
const reservationList = ref([]);
const loading = ref(true);
const err = ref('');

// 餐厅列表：优先取共享方案 itinerary 里的店铺（后端真实数据，含 store_id 与可预约标记）
const restaurants = computed(() => {
  const it = planStore.current && planStore.current.itinerary;
  if (Array.isArray(it) && it.length) return it;
  return [];
});
const hasStores = computed(() => restaurants.value.length > 0);

function submit() {
  if (!form.store_id) { err.value = '请先选餐厅'; return; }
  err.value = '';
  api.reserve({ store_id: form.store_id, reserved_for: form.reserved_for || '今晚 19:00', people: form.people, notes: form.notes })
    .then(r => {
      resultId.value = r.reservation_id || '';
      confirmed.value = true;
      if (navigator.vibrate) navigator.vibrate(30);
    })
    .catch(e => { err.value = '预约失败：' + (e.message || ''); });
}
function cancel() { confirmed.value = false; }

async function loadReservations() {
  try { const rs = await api.reservations(); reservationList.value = Array.isArray(rs) ? rs : []; }
  catch (e) {}
}
onMounted(() => { loadReservations(); loading.value = false; });
function nameOf(s) { return s.name || s.store_name || ''; }
</script>

<template>
  <div class="rs-page">
    <!-- 成功态 -->
    <div v-if="confirmed" class="rs-success">
      <div class="rs-check">✓</div>
      <div class="rs-suc-t">预约成功</div>
      <div class="card">
        <div class="rs-row"><span class="rs-k">餐厅</span><span class="rs-v">{{ nameOf(restaurants.find(r => r.id === form.store_id)) }}</span></div>
        <div class="rs-row"><span class="rs-k">时间</span><span class="rs-v">{{ form.reserved_for }}</span></div>
        <div class="rs-row"><span class="rs-k">人数</span><span class="rs-v">{{ form.people }} 人</span></div>
        <div v-if="resultId" class="rs-row"><span class="rs-k">预约号</span><span class="rs-v">{{ resultId }}</span></div>
      </div>
      <button class="ic-btn ghost" @click="cancel">取消预约</button>
      <button class="ic-btn primary" @click="router.push('/chat')">继续对话</button>
    </div>

    <!-- 表单 -->
    <div v-else>
      <div class="rs-hero"><div class="rs-title">🍽️ 预约餐厅</div><div class="rs-sub">从你的规划方案中选择，提交真实预约</div></div>

      <div class="section-title">选餐厅</div>
      <p v-if="!hasStores" class="empty">暂无方案店铺。请先在对话里说「帮我规划约会」，生成方案后再来预约。</p>
      <div v-for="s in restaurants" :key="s.id" class="rs-store" :class="{ active: form.store_id === s.id }" @click="form.store_id = s.id">
        <div class="rs-store-n">{{ nameOf(s) }}</div>
        <div class="rs-store-m">{{ s.category || '' }} · {{ s.floor ?? '' }}F</div>
      </div>

      <div class="section-title">时间</div>
      <div class="rs-chips">
        <span v-for="t in ['今晚 18:00','今晚 19:00','今晚 19:30','今晚 20:00']" :key="t" class="chip" :class="{ active: form.reserved_for === t }" @click="form.reserved_for = t">{{ t }}</span>
      </div>

      <div class="section-title">人数</div>
      <div class="rs-chips">
        <span v-for="n in [1,2,4,6]" :key="n" class="chip" :class="{ active: form.people === n }" @click="form.people = n">{{ n }}人</span>
      </div>

      <p v-if="err" class="err">{{ err }}</p>
      <button class="btn rs-submit" @click="submit">确认预约</button>

      <div class="section-title">📋 我的预约（{{ reservationList.length }}）</div>
      <div class="card">
        <div v-if="!reservationList.length" class="empty">暂无预约记录</div>
        <div v-for="r in reservationList" :key="r.id" class="rs-row"><span class="rs-k">{{ r.reserved_for }}</span><span class="rs-v">{{ r.status }}</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rs-page { min-height: 100%; background: var(--bg); padding: 0 18px 80px; }
.rs-hero { margin: 0 -18px; padding: 28px 20px 22px; background: linear-gradient(160deg, #1b1530, #312158 60%, #4c3a8c); color: #fff; }
.rs-title { font-size: 20px; font-weight: 800; } .rs-sub { font-size: 13px; color: rgba(255,255,255,0.75); margin-top: 4px; }
.rs-store { background: #fff; border-radius: 14px; padding: 14px 16px; border: 1px solid transparent; box-shadow: 0 4px 14px rgba(124,58,237,0.05); margin-bottom: 10px; cursor: pointer; }
.rs-store.active { border-color: var(--primary); background: #f5f3ff; }
.rs-store-n { font-weight: 700; font-size: 15px; } .rs-store-m { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
.rs-chips { display: flex; flex-wrap: wrap; }
.rs-submit { width: 100%; margin-top: 24px; }
.err { color: var(--danger); font-size: 13px; margin-top: 12px; }
.empty { color: var(--muted); font-size: 13px; }
.rs-success { padding-top: 60px; display: flex; flex-direction: column; align-items: center; }
.rs-check { width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, var(--success), var(--cyan)); color: #fff; font-size: 40px; display: flex; align-items: center; justify-content: center; animation: pop .4s ease; }
@keyframes pop { 0% { transform: scale(0.4); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
.rs-suc-t { font-size: 20px; font-weight: 800; margin: 18px 0 6px; }
.rs-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); }
.rs-k { color: #9CA3AF; font-size: 14px; } .rs-v { font-size: 14px; font-weight: 600; }
.ic-btn { width: 100%; border: none; border-radius: 20px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 12px; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
