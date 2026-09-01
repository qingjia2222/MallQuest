<script setup>
import { reactive, ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api';

const router = useRouter();
const route = useRoute();
const form = reactive({ store_id: '', time: '19:00', reserved_for: '今晚 19:00', people: 2, notes: '' });
const confirmed = ref(false);
const resultId = ref('');
const reservationList = ref([]);
const loading = ref(true);
const err = ref('');
const restaurants = ref([]);
const editing = ref(null);
const editForm = reactive({ time: '19:00', people: 2 });
const activeFloor = ref('');
const searchKeyword = ref('');
const floorOptions = computed(() => ['全部', ...new Set(restaurants.value.map(s => `${s.floor}F`).filter(v => v !== 'undefinedF' && v !== 'nullF'))]);
const filteredRestaurants = computed(() => {
  const keyword = searchKeyword.value.trim().toLocaleLowerCase();
  return restaurants.value.filter((s) => {
    const matchesFilter = !activeFloor.value || `${s.floor}F` === activeFloor.value;
    const haystack = `${s.name || s.store_name || ''} ${s.category || ''} ${s.floor || ''}F`.toLocaleLowerCase();
    return matchesFilter && (!keyword || haystack.includes(keyword));
  });
});

async function loadRestaurants() {
  await api.ensureSession();
  restaurants.value = (await api.reservableStores()) || [];
  const requestedStore = String(route.query.store || form.store_id || '');
  form.store_id = restaurants.value.some(s => s.id === requestedStore) ? requestedStore : (restaurants.value[0]?.id || '');
}

function submit() {
  if (!form.store_id) { err.value = '请先选餐厅'; return; }
  if (!form.time) { err.value = '请选择预约时间'; return; }
  if (!Number.isInteger(Number(form.people)) || Number(form.people) < 1 || Number(form.people) > 50) { err.value = '人数请填写 1 到 50'; return; }
  err.value = '';
  form.reserved_for = `今晚 ${form.time}`;
  api.reserve({ store_id: form.store_id, reserved_for: form.reserved_for, people: Number(form.people), notes: form.notes })
    .then(r => {
      resultId.value = r.reservation_id || '';
      confirmed.value = true;
      if (navigator.vibrate) navigator.vibrate(30); loadReservations();
    })
    .catch(e => { err.value = '预约失败：' + (e.message || ''); });
}
async function cancel() { if(!resultId.value || !window.confirm('确认取消刚创建的预约吗？'))return; await api.cancelReservation(resultId.value); confirmed.value = false; resultId.value=''; await loadReservations(); }

async function loadReservations() {
  try { const rs = await api.reservations(); reservationList.value = Array.isArray(rs) ? rs : []; }
  catch (e) {}
}
function timeOf(value) { const m=String(value||'').match(/(\d{1,2}):(\d{2})|(?:上午|下午|晚上|今晚|明晚)?\s*(\d{1,2})点(\d{1,2})?/); return m ? `${String(Number(m[1]||m[3])).padStart(2,'0')}:${String(Number(m[2]||m[4]||0)).padStart(2,'0')}` : '19:00'; }
function openEdit(r) { editing.value=r; editForm.time=timeOf(r.reserved_for); editForm.people=Number(r.people)||2; }
function closeEdit() { editing.value=null; }
async function saveEdit() { if(!editing.value)return; if(!editForm.time || !Number.isInteger(Number(editForm.people)) || Number(editForm.people)<1 || Number(editForm.people)>50){err.value='请填写有效时间，人数须为 1 到 50';return;} try { await api.updateReservation(editing.value.id,{reserved_for:`今晚 ${editForm.time}`,people:Number(editForm.people)}); closeEdit(); await loadReservations(); } catch(e){ err.value='修改失败：'+(e.message||''); } }
async function cancelItem(r) { if(!window.confirm(`确认取消 ${r.store_name || r.store_id} 的预约吗？`))return; try { await api.cancelReservation(r.id); await loadReservations(); } catch(e){ err.value='取消失败：'+(e.message||''); } }
onMounted(async () => { try { await Promise.all([loadRestaurants(),loadReservations()]); } catch(e){ err.value='预约服务加载失败：'+(e.message||''); } finally { loading.value=false; } });
function nameOf(s = {}) { return s.name || s.store_name || ''; }
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
      <div class="rs-hero"><div class="rs-title">🍽️ 预约餐厅</div><div class="rs-sub">开放预约服务 · 可自由选择餐厅、时间与人数</div></div>

      <div class="section-title">选餐厅（{{ filteredRestaurants.length }}/{{ restaurants.length }} 家）</div>
      <div class="store-tools">
        <label class="tool-row"><span>楼层</span><select v-model="activeFloor"><option value="">全部楼层</option><option v-for="item in floorOptions.slice(1)" :key="item" :value="item">{{ item }}</option></select></label>
        <label class="search-row"><span>🔎</span><input v-model.trim="searchKeyword" type="search" placeholder="输入餐厅名称手动搜索" /></label>
      </div>
      <p v-if="loading" class="empty">正在加载可预约餐厅…</p>
      <p v-else-if="!restaurants.length" class="empty">当前没有开放预约的店铺</p>
      <p v-else-if="!filteredRestaurants.length" class="empty">没有符合筛选或搜索条件的餐厅</p>
      <div v-else class="rs-store-list">
        <div v-for="s in filteredRestaurants" :key="s.id" class="rs-store" :class="{ active: form.store_id === s.id }" @click="form.store_id = s.id">
          <div class="rs-store-n">{{ nameOf(s) }}</div>
          <div class="rs-store-m">{{ s.category || '' }} · {{ s.floor ?? '' }}F</div>
        </div>
      </div>

      <div class="section-title">时间</div>
      <div class="rs-chips">
        <span v-for="t in ['18:00','19:00','19:30','20:00']" :key="t" class="chip" :class="{ active: form.time === t }" @click="form.time = t">{{ t }}</span>
      </div>
      <label class="custom-field"><span>自定义时间</span><input v-model="form.time" type="time" /></label>

      <div class="section-title">人数</div>
      <div class="rs-chips">
        <span v-for="n in [1,2,4,6]" :key="n" class="chip" :class="{ active: form.people === n }" @click="form.people = n">{{ n }}人</span>
      </div>
      <label class="custom-field"><span>自定义人数</span><input v-model.number="form.people" type="number" min="1" max="50" /></label>

      <p v-if="err" class="err">{{ err }}</p>
      <button class="btn rs-submit" @click="submit">确认预约</button>

    </div>

    <div class="section-title">📋 我的预约（{{ reservationList.length }}）</div>
    <div class="card reservation-list">
      <div v-if="!reservationList.length" class="empty">暂无预约记录</div>
      <div v-for="r in reservationList" :key="r.id" class="reservation-item">
        <div><div class="reservation-name">{{ r.store_name || r.store_id }}</div><div class="rs-k">{{ r.reserved_for }} · {{ r.people }}人 · {{ r.status }}</div></div>
        <div v-if="r.status !== 'cancelled'" class="reservation-actions"><button @click="openEdit(r)">改时间/人数</button><button class="danger" @click="cancelItem(r)">取消</button></div>
      </div>
    </div>

    <div v-if="editing" class="edit-mask" @click.self="closeEdit">
      <div class="edit-dialog"><h3>修改 {{ editing.store_name || editing.store_id }} 的预约</h3><label class="custom-field"><span>预约时间</span><input v-model="editForm.time" type="time" /></label><label class="custom-field"><span>预约人数</span><input v-model.number="editForm.people" type="number" min="1" max="50" /></label><div class="edit-actions"><button @click="closeEdit">暂不修改</button><button class="save" @click="saveEdit">确认修改</button></div></div>
    </div>
  </div>
</template>

<style scoped>
.rs-page { min-height: 100%; background: var(--bg); padding: 0 18px 80px; }
.rs-hero { margin: 0 -18px; padding: 28px 20px 22px; background: linear-gradient(160deg, #1b1530, #312158 60%, #4c3a8c); color: #fff; }
.rs-title { font-size: 20px; font-weight: 800; } .rs-sub { font-size: 13px; color: rgba(255,255,255,0.75); margin-top: 4px; }
.rs-store { background: #fff; border-radius: 14px; padding: 14px 16px; border: 1px solid transparent; box-shadow: 0 4px 14px rgba(124,58,237,0.05); margin-bottom: 10px; cursor: pointer; }
.rs-store-list { max-height: min(440px, 45vh); overflow-y: auto; padding: 1px 4px 1px 1px; }
.rs-store.active { border-color: var(--primary); background: #f5f3ff; }
.rs-store-n { font-weight: 700; font-size: 15px; } .rs-store-m { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
.rs-chips { display: flex; flex-wrap: wrap; }
.rs-submit { width: 100%; margin-top: 24px; }
.err { color: var(--danger); font-size: 13px; margin-top: 12px; }
.empty { color: var(--muted); font-size: 13px; }
.store-tools { margin-bottom: 12px; padding: 12px 14px; border-radius: 14px; background: #fff; box-shadow: 0 4px 14px rgba(124,58,237,.06); }
.tool-row, .search-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; color: #9ca3af; font-size: 12px; }
.tool-row:last-of-type { margin-bottom: 10px; }
.tool-row > span { width: 34px; flex-shrink: 0; }
.tool-row select, .search-row input { box-sizing: border-box; flex: 1; min-width: 0; padding: 9px 12px; border: 1px solid var(--border); border-radius: 10px; background: #fff; color: var(--text); font: inherit; outline: none; }
.search-row { margin-bottom: 0; }
.search-row input { font-size: 14px; }
.tool-row select:focus, .search-row input:focus { border-color: var(--primary); }
.custom-field { margin-top: 12px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 11px 14px; border: 1px solid var(--border); border-radius: 12px; background: #fff; font-size: 13px; }.custom-field input{min-width:140px;border:0;background:#f8fafc;border-radius:9px;padding:9px 12px;font:inherit}
.reservation-list{margin-top:0}.reservation-item{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 0;border-bottom:1px solid var(--border)}.reservation-item:last-child{border-bottom:0}.reservation-name{font-weight:700;margin-bottom:5px}.reservation-actions{display:flex;gap:8px;flex-shrink:0}.reservation-actions button{border:1px solid var(--border);background:#fff;color:var(--primary);border-radius:16px;padding:7px 11px;cursor:pointer}.reservation-actions .danger{color:#dc2626}
.edit-mask{position:fixed;inset:0;z-index:100;background:rgba(15,23,42,.48);display:flex;align-items:center;justify-content:center;padding:20px}.edit-dialog{width:min(420px,100%);padding:24px;border-radius:20px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.25)}.edit-dialog h3{margin:0 0 18px}.edit-actions{display:flex;gap:12px;margin-top:20px}.edit-actions button{flex:1;border:1px solid var(--border);border-radius:20px;padding:11px;background:#fff;cursor:pointer}.edit-actions .save{border:0;color:#fff;background:linear-gradient(135deg,var(--primary),var(--cyan))}
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
