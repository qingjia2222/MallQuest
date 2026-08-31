<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import PlanFlow from '../components/PlanFlow.vue';
import ItineraryCard from '../components/ItineraryCard.vue';

// 规划浮层：悬浮在对话页上方，不跳转独立页
// props.initialPlan：若对话已带方案则直接进入确认；否则从选场景开始
const props = defineProps({ show: Boolean, initialPlan: Object });
const emit = defineEmits(['close']);
const router = useRouter();

const SCENES = [
  { scene: 'date', name: '约会', slots: { time: '今晚7点', people: 2, budget_per_person: 250, cuisine: '川菜', want_movie: true } },
  { scene: 'banquet', name: '家宴', slots: { time: '周末6点', people: 8, total_budget: 1500, cuisine: '川菜', private_room: true } },
  { scene: 'gift', name: '礼物', slots: { recipient: '22岁女生', budget: 500, preferences: '香氛', occasion: '生日' } },
  { scene: 'family_day', name: '带娃', slots: { child_age: 6, duration: 4, budget: 600, interests: '游乐', meal_preference: '亲子餐' } },
  { scene: 'business', name: '商务', slots: { time: '明天下午3点', people: 4, total_budget: 2000, level: '高端', quiet: true, meal_preference: '中餐' } }
];

const step = ref(1);
const selected = ref(SCENES[0]);
const generating = ref(false);
const plan = ref(null);
const resultText = ref('');
const stepNames = ['理解目标', '采集偏好', '生成方案', '确认方案', '执行'];

watch(() => props.show, (v) => { if (v) { plan.value = props.initialPlan || null; step.value = plan.value ? 4 : 1; } });
function choose(s) { selected.value = s; step.value = 2; generate(); }

async function generate() {
  generating.value = true;
  try {
    const p = await api.createPlan(selected.value.scene, selected.value.slots);
    if (p.missing_slots && p.missing_slots.length) { resultText.value = '还需补充：' + JSON.stringify(p.missing_slots); step.value = 3; }
    else { plan.value = p; resultText.value = ''; step.value = 4; }
  } catch (e) { resultText.value = '生成失败：' + (e.message || ''); }
  finally { generating.value = false; }
}

async function onConfirm() {
  if (!plan.value) return;
  try {
    plan.value = await api.confirmPlan(plan.value.plan_id, 'confirm');
    if (navigator.vibrate) navigator.vibrate(30);
    step.value = 5;
  } catch (e) { resultText.value = '确认失败：' + (e.message || ''); }
}
function onChange() { generate(); }
function stopPlan() { router.push('/map'); emit('close'); }
function toStops(it) {
  if (!Array.isArray(it)) return [];
  return it.map((s, i) => ({ time: s.time_label || `${i + 1}`, name: s.name || '', floor: s.floor ?? '', category: s.category || '', waiting: s.waiting_time ?? null, desc: s.desc || '' }));
}

// 可编辑槽位选项（按场景）：用户在悬浮窗里点选即改并重新生成
const EDIT_FIELDS = {
  date: [
    { key: 'time', label: '时间', options: ['今晚 18:00', '今晚 19:00', '今晚 20:00'], parse: v => v },
    { key: 'people', label: '人数', options: ['1人', '2人', '3人', '4人'], parse: v => Number(v.match(/\d+/)[0]) },
    { key: 'budget_per_person', label: '人均', options: ['人均150', '人均250', '人均350'], parse: v => Number(v.match(/\d+/)[0]) },
    { key: 'cuisine', label: '口味', options: ['川菜', '火锅', '日料', '西餐'], parse: v => v }
  ],
  banquet: [
    { key: 'people', label: '人数', options: ['6人', '8人', '10人'], parse: v => Number(v.match(/\d+/)[0]) },
    { key: 'cuisine', label: '菜系', options: ['川菜', '粤菜', '中餐'], parse: v => v }
  ],
  gift: [
    { key: 'budget', label: '预算', options: ['¥200', '¥300', '¥500'], parse: v => Number(v.match(/\d+/)[0]) }
  ],
  family_day: [
    { key: 'duration', label: '时长', options: ['2小时', '4小时', '6小时'], parse: v => Number(v.match(/\d+/)[0]) }
  ],
  business: [
    { key: 'level', label: '档次', options: ['高端', '商务', '中端'], parse: v => v }
  ]
};
const editFields = ref([]);
const renderSlots = ref({});
watch(() => plan.value, (p) => {
  if (p && p.slots) { renderSlots.value = { ...p.slots }; editFields.value = EDIT_FIELDS[p.scene] || []; }
});
function adjustField(field, opt) {
  const key = field.key;
  renderSlots.value[key] = field.parse(opt);
  plan.value.slots = { ...renderSlots.value };
  generateCurrent();
}
// 判断某个选项是否当前已选中（用于高亮 active）
function active(field, o) {
  const cur = renderSlots.value[field.key];
  const parsed = field.parse(o);
  return String(cur) === String(parsed);
}
async function generateCurrent() {
  generating.value = true;
  try {
    const p = await api.createPlan(selected.value.scene, renderSlots.value);
    plan.value = p; resultText.value = ''; step.value = 4;
  } catch (e) { resultText.value = '生成失败：' + (e.message || ''); }
  finally { generating.value = false; }
}
</script>

<template>
  <transition name="fade">
    <div v-if="show" class="plan-overlay" @click.self="emit('close')">
      <div class="plan-sheet">
        <!-- 头部 -->
        <div class="po-head">
          <span class="po-title">🎯 全链路规划</span>
          <span class="po-close" @click="emit('close')">×</span>
        </div>
        <PlanFlow :step="Math.min(step, 5)" :step-names="stepNames" />

        <!-- 选场景 -->
        <div v-if="step === 1" class="po-body">
          <div class="q-title">你想规划什么？</div>
          <div class="q-options">
            <div v-for="s in SCENES" :key="s.scene" class="q-opt" @click="choose(s)">{{ s.name }}</div>
          </div>
        </div>

        <!-- 生成中 -->
        <div v-else-if="step === 2" class="po-body">
          <div class="generating">
            <div class="gen-stars"><span class="star"></span><span class="star s2"></span><span class="star s3"></span></div>
            <div class="gen-text">正在为你规划「{{ selected.name }}」路线…</div>
            <div class="gen-sub">结合店铺分布 · 实时状态 · 你的偏好</div>
          </div>
        </div>

        <!-- 缺槽位 -->
        <div v-else-if="step === 3" class="po-body">
          <div class="card hint">{{ resultText }}</div>
          <button class="ic-btn primary" @click="generate">重试</button>
        </div>

        <!-- 确认/完成 -->
        <div v-else class="po-body">
          <!-- 编辑偏好：点选调整槽位即重新生成 -->
          <div v-if="editFields.length" class="edit-prefs">
            <div v-for="f in editFields" :key="f.key" class="ep-row">
              <span class="ep-label">{{ f.label }}</span>
              <div class="ep-opts">
                <span v-for="o in f.options" :key="o" class="chip"
                      :class="{ active: active(f, o) }" @click="adjustField(f, o)">{{ o }}</span>
              </div>
            </div>
            <p class="ep-tip">点选调整后自动重新生成方案</p>
          </div>
          <ItineraryCard v-if="plan && plan.itinerary" :itinerary="{
              tag: selected.name + ' 方案',
              stops: toStops(plan.itinerary),
              actions: (plan.action_results || []).map(a => ({ label: a.label || (a.tool || a.action || '') , ok: a.status !== 'failed' }))
            }" @confirm="onConfirm" @change="onChange" @stoptap="stopPlan" />
          <div v-else class="card hint">暂无行程，请重试。</div>
          <div v-if="step === 5" class="done-tip">✅ 方案已执行，去地图查看路线</div>
          <div class="po-nav">
            <button class="ic-btn ghost" @click="emit('close')">返回对话</button>
            <button class="ic-btn primary" @click="stopPlan">查看地图路线</button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.plan-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 60; display: flex; align-items: flex-end; }
.plan-sheet { width: 100%; background: #fff; border-radius: 20px 20px 0 0; padding: 20px 20px 30px; max-height: 88vh; overflow-y: auto; animation: up .3s ease; }
@keyframes up { from { transform: translateY(100%); } to { transform: none; } }
.po-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.po-title { font-weight: 800; font-size: 18px; color: var(--text); }
.po-close { font-size: 26px; color: #9CA3AF; cursor: pointer; padding: 0 6px; }
.po-body { padding-top: 16px; }
.q-title { font-size: 20px; font-weight: 700; margin: 6px 0 18px; }
.q-options { display: flex; flex-direction: column; gap: 12px; }
.q-opt { background: #fff; border-radius: 14px; padding: 15px; font-size: 16px; box-shadow: 0 4px 14px rgba(124,58,237,0.06); border: 1px solid transparent; cursor: pointer; }
.q-opt:active { border-color: var(--primary); background: #f5f3ff; }
.generating { display: flex; flex-direction: column; align-items: center; margin-top: 40px; }
.gen-stars { display: flex; gap: 12px; }
.star { width: 16px; height: 16px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--cyan)); animation: pulse 1s ease infinite; }
.star.s2 { animation-delay: 0.2s; } .star.s3 { animation-delay: 0.4s; }
@keyframes pulse { 0%,100% { transform: scale(0.7); opacity: 0.5; } 50% { transform: scale(1.2); opacity: 1; } }
.gen-text { font-weight: 700; margin-top: 14px; }
.gen-sub { font-size: 12px; color: #9CA3AF; margin-top: 6px; }
.hint { font-size: 14px; color: var(--muted); }
.done-tip { text-align: center; color: var(--success); font-weight: 600; margin: 14px 0 8px; }
.po-nav { display: flex; gap: 12px; margin-top: 14px; }
.ic-btn { flex: 1; border: none; border-radius: 20px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.edit-prefs { background: #f6f4ff; border: 1px solid #ede9fe; border-radius: 14px; padding: 14px; margin-bottom: 12px; }
.ep-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.ep-label { font-size: 13px; color: var(--muted); width: 42px; flex-shrink: 0; }
.ep-opts { display: flex; flex-wrap: wrap; gap: 6px; }
.ep-tip { font-size: 12px; color: var(--muted); margin-top: 4px; }
</style>
