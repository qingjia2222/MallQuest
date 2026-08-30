<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import PlanFlow from '../components/PlanFlow.vue';
import ItineraryCard from '../components/ItineraryCard.vue';

const router = useRouter();

// 与队友后端 planner 一致的五种场景模板（slots 键需匹配）
const SCENES = [
  { scene: 'date', name: '约会', slots: { time: '今晚7点', people: 2, budget_per_person: 250, cuisine: '川菜', want_movie: true } },
  { scene: 'banquet', name: '家宴', slots: { time: '周末6点', people: 8, total_budget: 1500, cuisine: '川菜', private_room: true } },
  { scene: 'gift', name: '礼物', slots: { recipient: '22岁女生', budget: 500, preferences: '香氛', occasion: '生日' } },
  { scene: 'family_day', name: '带娃', slots: { child_age: 6, duration: 4, budget: 600, interests: '游乐', meal_preference: '亲子餐' } },
  { scene: 'business', name: '商务', slots: { time: '明天下午3点', people: 4, total_budget: 2000, level: '高端', quiet: true, meal_preference: '中餐' } }
];

const step = ref(1);        // 1选场景 2生成 3确认 4完成
const selected = ref(SCENES[0]);
const generating = ref(false);
const plan = ref(null);
const resultText = ref('');

const stepNames = ['理解目标', '采集偏好', '生成方案', '确认方案', '执行'];

function choose(s) {
  selected.value = s;
  step.value = 2;
  generate();
}

async function generate() {
  generating.value = true;
  try {
    const p = await api.createPlan(selected.value.scene, selected.value.slots);
    if (p.missing_slots && p.missing_slots.length) {
      resultText.value = '还需补充：' + JSON.stringify(p.missing_slots);
      step.value = 3;
    } else {
      plan.value = p; resultText.value = ''; step.value = 4;
    }
  } catch (e) {
    resultText.value = '生成失败：' + (e.message || '');
  } finally { generating.value = false; }
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
function onStop() { router.push('/map'); }
function goChat() { router.push('/chat'); }

// 后端 itinerary 店铺数组 → 前端行程卡 stops（含序号兜底）
function toStops(it) {
  if (!Array.isArray(it)) return [];
  return it.map((s, i) => ({
    time: s.time_label || `${i + 1}`,
    name: s.name || s.title || '',
    floor: s.floor ?? s.floor_label ?? '',
    category: s.category || '',
    waiting: s.waiting_time ?? null,
    desc: s.desc || ''
  }));
}
</script>

<template>
  <div class="plan-page">
    <div class="plan-hero">
      <div class="plan-goal">🎯 全链路规划</div>
      <PlanFlow :step="Math.min(step, 5)" :step-names="stepNames" />
    </div>
    <div class="plan-body">
      <!-- 步骤1：选场景 -->
      <template v-if="step === 1">
        <div class="q-title">你想规划什么？</div>
        <div class="q-options">
          <div v-for="s in SCENES" :key="s.scene" class="q-opt" @click="choose(s)">{{ s.name }}</div>
        </div>
      </template>

      <!-- 步骤2：生成中 -->
      <template v-else-if="step === 2">
        <div class="generating">
          <div class="gen-stars"><span class="star"></span><span class="star s2"></span><span class="star s3"></span></div>
          <div class="gen-text">正在为你规划「{{ selected.name }}」路线…</div>
          <div class="gen-sub">结合店铺分布 · 实时状态 · 你的偏好</div>
        </div>
      </template>

      <!-- 步骤3：需补槽位 -->
      <template v-else-if="step === 3">
        <div class="card hint">{{ resultText }}</div>
        <button class="ic-btn primary" @click="generate">重试</button>
      </template>

      <!-- 步骤4/5：确认/完成 -->
      <template v-else>
        <ItineraryCard v-if="plan && plan.itinerary" :itinerary="{
            tag: selected.name + ' 方案',
            stops: toStops(plan.itinerary),
            actions: (plan.action_results || []).map(a => ({ label: a.label || (a.tool || a.action || '') , ok: a.status !== 'failed' }))
          }" @confirm="onConfirm" @change="onChange" @stoptap="onStop" />
        <div v-else class="card hint">暂无行程，请重试。</div>
        <div v-if="step === 5" class="done-tip">✅ 方案已执行，去地图查看路线</div>
        <div class="plan-nav">
          <button class="ic-btn ghost" @click="goChat">返回对话</button>
          <button class="ic-btn primary" @click="onStop">查看地图路线</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.plan-page { min-height: 100%; background: var(--bg); }
.plan-hero { background: linear-gradient(160deg, #1b1530, #312158 60%, #4c3a8c); color: #fff; padding: 24px 18px; }
.plan-goal { display: inline-flex; background: rgba(255,255,255,0.14); border-radius: 24px; padding: 8px 16px; font-size: 15px; font-weight: 600; margin-bottom: 20px; }
.plan-body { padding: 16px 20px 80px; }
.q-title { font-size: 22px; font-weight: 700; margin: 12px 0 24px; }
.q-options { display: flex; flex-direction: column; gap: 12px; }
.q-opt { background: #fff; border-radius: 16px; padding: 17px; font-size: 16px; box-shadow: 0 5px 16px rgba(124,58,237,0.06); border: 1px solid transparent; cursor: pointer; }
.q-opt:active { border-color: var(--primary); background: #f5f3ff; transform: scale(0.98); }
.generating { display: flex; flex-direction: column; align-items: center; margin-top: 80px; }
.gen-stars { display: flex; gap: 12px; }
.star { width: 16px; height: 16px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--cyan)); animation: pulse 1s ease infinite; }
.star.s2 { animation-delay: 0.2s; } .star.s3 { animation-delay: 0.4s; }
@keyframes pulse { 0%,100% { transform: scale(0.7); opacity: 0.5; } 50% { transform: scale(1.2); opacity: 1; } }
.gen-text { font-size: 18px; font-weight: 700; margin-top: 20px; }
.gen-sub { font-size: 13px; color: #9CA3AF; margin-top: 8px; }
.hint { font-size: 14px; color: var(--muted); }
.done-tip { text-align: center; color: var(--success); font-weight: 600; margin: 16px 0 8px; }
.plan-nav { display: flex; gap: 12px; margin-top: 16px; }
.ic-btn { flex: 1; border: none; border-radius: 24px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 10px; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
