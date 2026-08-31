<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api, { BASE } from '../api';
import { startQueueWatch } from '../store/queue';
import RichCard from '../components/RichCard.vue';
import PlanOverlay from '../components/PlanOverlay.vue';
import PlanFlow from '../components/PlanFlow.vue';
import ItineraryCard from '../components/ItineraryCard.vue';
import { setCurrentPlan } from '../store/plan';
import { setSession } from '../api';
import { renderMd } from '../utils/md';

const router = useRouter();
const messages = ref([]);
const input = ref('发个「停车场还有空位吗？」试试智能对话');
const loading = ref(false);
const listening = ref(false);
const currentPlan = ref(null);
const showPlan = ref(false);        // 规划悬浮窗开关
const planInOverlay = ref(null);    // 传给悬浮窗的方案
const collector = ref(null);        // 偏好采集器
const quickActions = ['停车场还有空位吗？', '积分多久过期？', '今天有什么特惠？', '帮我规划约会'];

// 场景默认槽位（兜底）与偏好问题集
const DEFAULT_SLOTS = {
  date: { time: '今晚7点', people: 2, budget_per_person: 200, cuisine: '川菜', want_movie: true },
  banquet: { time: '周末6点', people: 6, total_budget: 1000, cuisine: '川菜', private_room: true },
  gift: { recipient: '朋友', budget: 300, preferences: '设计感小物', occasion: '礼物' },
  family_day: { child_age: 6, duration: 4, budget: 500, interests: '游乐', meal_preference: '亲子餐' },
  business: { time: '明天下午3点', people: 4, total_budget: 1500, level: '高端', quiet: true, meal_preference: '中餐' }
};
const PLAN_QUESTIONS = {
  date: [{ key: 'time', label: '大概几点开始？', options: ['今晚 19:00', '今晚 18:00', '今晚 20:00'] },
         { key: 'people', label: '一共几个人？', options: ['2人', '3人', '4人'] },
         { key: 'budget_per_person', label: '人均预算大概多少？', options: ['人均100-200', '人均200-300', '人均300+'] },
         { key: 'cuisine', label: '偏好什么口味？', options: ['川菜', '火锅', '日料', '西餐'] }],
  banquet: [{ key: 'people', label: '几位？', options: ['6人', '8人', '10人'] },
            { key: 'cuisine', label: '菜系偏好？', options: ['川菜', '粤菜', '中餐'] }],
  gift: [{ key: 'recipient', label: '送给谁？', options: ['朋友', '22岁女生', '长辈'] },
         { key: 'budget', label: '预算？', options: ['¥200', '¥300', '¥500'] }],
  family_day: [{ key: 'child_age', label: '孩子几岁？', options: ['5岁', '6岁', '8岁'] },
               { key: 'duration', label: '大概玩多久？', options: ['2小时', '4小时', '一整天'] }],
  business: [{ key: 'people', label: '几位？', options: ['4人', '6人', '8人'] },
             { key: 'level', label: '档次？', options: ['高端', '商务', '中端'] }]
};
function detectScene(text) {
  const map = [['business', ['商务', '客户']], ['family_day', ['带娃', '孩子', '亲子']], ['gift', ['礼物', '生日']], ['banquet', ['家宴', '包间']], ['date', ['约会', '电影']]];
  for (const [scene, words] of map) if (words.some(w => text.includes(w))) return scene;
  return null;
}

// 语音识别（浏览器 Web Speech API；Chrome/Edge 可用，需 http 或 https）
let recog = null;
function getRecog() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  if (!recog) {
    recog = new SR();
    recog.lang = 'zh-CN';
    recog.interimResults = false;
    recog.maxAlternatives = 1;
  }
  return recog;
}
function startVoice() {
  const r = getRecog();
  if (!r) { alert('当前浏览器不支持语音识别，请用 Chrome 或 Edge'); return; }
  try {
    listening.value = true;
    r.onresult = (e) => {
      const text = e.results[0][0].transcript.trim();
      if (text) send(text);       // 识别成功直接发送/填入
    };
    r.onend = () => { listening.value = false; };
    r.onerror = () => { listening.value = false; };
    r.start();
  } catch (e) {
    listening.value = false;
    alert('语音识别启动失败：' + (e.message || ''));
  }
}
function toggleVoice() { listening.value ? recog && recog.stop() : startVoice(); }

// 把消息文本渲染成 HTML（AI 消息走 Markdown）
function htmlOf(m) {
  return m.role === 'ai' ? renderMd(m.text) : m.text.replace(/\n/g, '<br>');
}

onMounted(() => {
  const name = localStorage.getItem('mall_name') || 'QD square';
  push('ai', `已接入「${name}」私有数据。我是你的 AI 私域助手，可以问我停车、积分、特惠，或说「帮我规划约会」让我安排。`);
  const ref = localStorage.getItem('plan_ref');
  if (ref) { localStorage.removeItem('plan_ref'); push('ref', ref); }
  const prefill = localStorage.getItem('prefill');
  if (prefill) { localStorage.removeItem('prefill'); send(prefill); }
});

function push(role, text) { messages.value.push({ role, text, cards: [] }); }
function scroll() { requestAnimationFrame(() => { const el = document.querySelector('.chat-scroll'); if (el) el.scrollTop = el.scrollHeight; }); }

function acceptChatData(data) {
  push('ai', data.reply || '好的，已为你处理。');
  const msg = messages.value[messages.value.length - 1];
  msg.cards = toCards(data.cards);
  if (data.plan) {
    currentPlan.value = data.plan; setCurrentPlan(data.plan); msg.plan = data.plan;
    setTimeout(() => openExecuteConfirm(data.plan), 700);
  }
  scroll();
}

// 把后端的 cards 映射成前端富卡片类型
function toCards(cards) {
  if (!Array.isArray(cards)) return [];
  return cards.map(c => {
    const type = c.type || (c.data && (Array.isArray(c.data) ? 'list' : 'generic'));
    return { type, data: c.data };
  });
}

// 把用户点选的选项文本 → 后端槽位期望的值
function parseValue(q, value) {
  const v = String(value);
  if (q.key === 'budget_per_person') { const m = v.match(/\d+/); return m ? Number(m[0]) : 200; }
  if (q.key === 'people') { const m = v.match(/\d+/); return m ? Number(m[0]) : 2; }
  if (q.key === 'total_budget' || q.key === 'budget') { const m = v.match(/\d+/); return m ? Number(m[0]) : 300; }
  if (q.key === 'child_age') { const m = v.match(/\d+/); return m ? Number(m[0]) : 6; }
  if (q.key === 'duration') { const m = v.match(/\d+/); return m ? Number(m[0]) : 4; }
  if (q.key === 'time') return v.replace(/^今晚\s*/, '今晚').replace(/^明天\s*/, '明天');
  return v;
}
// 推进偏好采集：用户点选/回答 → 记录并问下一题，或生成
function advanceCollect(value) {
  const c = collector.value;
  if (!c) return;
  const q = PLAN_QUESTIONS[c.scene][c.qIndex];
  c.slots[q.key] = parseValue(q, value);
  c.qIndex++;
  if (c.qIndex < PLAN_QUESTIONS[c.scene].length) { askQuestion(); }
  else { finishCollect(); }
}
function askQuestion() {
  const c = collector.value;
  const q = PLAN_QUESTIONS[c.scene][c.qIndex];
  push('ai', q.label);
  const msg = messages.value[messages.value.length - 1];
  msg.quick = q.options;
  scroll();
}
async function finishCollect() {
  const c = collector.value;
  // 与默认槽位合并（用户没回答的项用默认）
  const slots = { ...DEFAULT_SLOTS[c.scene], ...c.slots };
  push('ai', '好的，正在为你生成方案…');
  try {
    await api.ensureSession();
    const p = await api.createPlan(c.scene, slots);
    currentPlan.value = p; setCurrentPlan(p);
    planInOverlay.value = p;
    showPlan.value = true;
    scroll();
  } catch (e) { push('ai', '生成方案失败：' + (e.message || '')); scroll(); }
  finally { collector.value = null; }
}
function startPlanCollect(text) {
  const scene = detectScene(text);
  if (!scene) return false;
  collector.value = { scene, slots: {}, qIndex: 0 };
  askQuestion();
  return true;
}

// 到号提醒已提到全局 store/queue.js + App 顶部横幅（跨页面持续轮询，确认后跳地图仍提醒）

async function send(txt) {
  const text = (txt ?? input.value).trim();
  if (!text || loading.value) return;
  input.value = '';
  // 若正在采集中：把用户回答推进采集，走本地向导
  if (collector.value) { push('user', text); scroll(); advanceCollect(text); return; }
  // 规划类文本直接交给后端大模型智能体：查排队、设计时间地点、出方案，并支持确认预约 + 到号提醒
  push('user', text);
  scroll();
  loading.value = true;
  try {
    await api.ensureSession();  // 确保有 token + session，缺则自动补
    const data = await api.chat(text);
    acceptChatData(data);
  } catch (e) {
    // session 失效：强制重扫建全新会话再试一次
    if (/session not found|not found/i.test(e.message || '')) {
      try {
        const scan = await api.freshScan();
        setSession(scan.session_id);
        const data = await api.chat(text);
        acceptChatData(data);
      } catch (e2) {
        push('ai', '抱歉，请求后端失败：' + (e2.message || ''));
        scroll();
      }
    } else {
      push('ai', '抱歉，请求后端失败：' + (e.message || ''));
      scroll();
    }
  } finally { loading.value = false; }
}

// 换一版：重新发一句让后端重规划，生成新方案
function movieOptions(plan) {
  if (!plan || !plan.itinerary) return [];
  for (const s of plan.itinerary) {
    if (s.now_showing && s.now_showing.length) return s.now_showing;
  }
  return [];
}
function onChangePlan(planId) {
  send('请重新规划一版方案，换一些店铺');
}
// —— 执行确认弹窗：提问是否按照方案执行 ——
const showConfirm = ref(false);
const pendingPlan = ref(null);
const confirmStep = ref(1);          // 1=是否按方案执行  2=是否帮忙预约订票
const chosenMovie = ref('');          // 方案含影院时，确认弹窗里选择的影片
function openExecuteConfirm(plan) {
  pendingPlan.value = plan || null;
  confirmStep.value = 1;
  const mvs = movieOptions(plan);
  chosenMovie.value = mvs.length ? mvs[0] : '';
  showConfirm.value = true;
}
function cancelExecute() { showConfirm.value = false; pendingPlan.value = null; confirmStep.value = 1; }
async function runExecute(doBooking) {
  const plan = pendingPlan.value;
  showConfirm.value = false; pendingPlan.value = null; confirmStep.value = 1;
  if (!plan) return;
  if (doBooking && plan.plan_id) { await onConfirmPlan(plan.plan_id, chosenMovie.value ? { selected_movie: chosenMovie.value } : {}, plan.revision); }
  else { currentPlan.value = plan; setCurrentPlan(plan); router.push('/map'); }
}
// 确认方案并执行
async function onConfirmPlan(planId, modifications = {}, expectedRevision = null) {
  if (!planId) return;
  loading.value = true;
  try {
    const data = await api.confirmPlan(planId, 'confirm', modifications, expectedRevision);
    setCurrentPlan(data);
    const last = [...messages.value].reverse().find(m => m.plan);
    if (last) last.plan = { ...last.plan, ...data, state: 'DONE' };
    if (navigator.vibrate) navigator.vibrate(30);
    push('ai', '✅ 方案已确认并执行，已为你预约可排队的店铺，到号时会实时提醒。');
    startQueueWatch(data.plan_id, data.itinerary);
    setTimeout(() => router.push('/map'), 1100);
  } catch (e) { push('ai', '确认失败：' + (e.message || '')); }
  finally { loading.value = false; }
}
// 后端 itinerary → 行程卡 stops
function toStops(it) {
  if (!Array.isArray(it)) return [];
  return it.map((s, i) => ({ time: s.time_label || `${i + 1}`, name: s.name || '', floor: s.floor ?? '', category: s.category || '', waiting: s.waiting_time ?? (s.queue_minutes ?? null), desc: s.desc || '' }));
}
function actionLabel(a) {
  if (!a) return '';
  if (a.label) return a.label;
  const t = a.tool || a.action || '';
  if (t === 'queue') return `${a.store_id ? '已排号：' + a.store_id : '已排队'}${a.queue_minutes ? '（约' + a.queue_minutes + '分钟）' : ''}`;
  const map = { claim_coupon: '领取优惠券', buy_ticket: '购买门票', reserve_restaurant: '预约餐厅', reserve_business_space: '预约商务空间' };
  return map[t] || t;
}
function onCardTap(card) {
  if (card.type === 'parking') router.push('/map');
  else if (card.type === 'coupon' || card.type === 'deals') router.push('/coupon');
  else if (card.type === 'store' || card.type === 'list') router.push('/map');
}
// 点向导/快选项：采集中推进采集，否则作为普通消息发送
function onQuickOption(q) {
  if (collector.value) { advanceCollect(q); }
  else { send(q); }
}
function goMap() { router.push('/map'); }
</script>

<template>
  <div class="chat-page">
    <div class="chat-scroll">
      <div v-for="(m, i) in messages" :key="i">
        <div v-if="m.role === 'user'" class="row user"><div class="bubble user-bubble">{{ m.text }}</div></div>
        <div v-else-if="m.role === 'ref'" class="row ai">
          <div class="ai-avatar">📋</div>
          <div class="ai-body">
            <div class="bubble ref-bubble">📋 引用方案：<span class="ref-text">{{ m.text }}</span></div>
          </div>
        </div>
        <div v-else class="row ai">
          <div class="ai-avatar">AI</div>
          <div class="ai-body">
            <div class="bubble ai-bubble" v-html="htmlOf(m)"></div>
            <RichCard v-for="(c, j) in m.cards" :key="j" :card="c" @tap="onCardTap" />
            <!-- 采集向导的快捷选项 -->
            <div v-if="m.quick && m.quick.length" class="quick-chips">
              <span v-for="q in m.quick" :key="q" class="chip active" @click="onQuickOption(q)">{{ q }}</span>
            </div>
            <!-- 方案提示（方案本体在悬浮窗展示） -->
            <div v-if="m.plan" class="plan-inline">
              <div class="pi-title">🎯 已生成方案<span v-if="m.plan.state === 'DONE'" class="pi-done">已确认</span></div>
              <PlanFlow :step="m.plan.state === 'DONE' ? 5 : 4" :step-names="['理解目标','采集偏好','生成方案','确认方案','执行']" />
              <ItineraryCard v-if="m.plan.itinerary" :itinerary="{
                  tag: '为你定制',
                  stops: toStops(m.plan.itinerary),
                  actions: (m.plan.action_results || []).map(a => ({ label: actionLabel(a), ok: a.status !== 'failed' }))
                }" @confirm="openExecuteConfirm(m.plan)" @change="onChangePlan(m.plan.plan_id)" @stoptap="goMap" />
              <div v-else class="pi-confirm">
                <div class="pi-empty-t">🧠 大模型已生成这份智能方案，确认后即可为你预约 / 排号</div>
                <div class="ic-btns">
                  <button class="ic-btn ghost" @click="onChangePlan(m.plan.plan_id)">换一版</button>
                  <button class="ic-btn primary" @click="openExecuteConfirm(m.plan)">就按这个，帮我预约</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="composer">
      <input class="ci" v-model="input" @keyup.enter="send()" placeholder="问我任何商场问题…" />
      <div class="mic" :class="{ on: listening }" @click="toggleVoice">{{ listening ? '🔴' : '🎤' }}</div>
      <button class="send-btn" :disabled="loading" @click="send()">{{ loading ? '…' : '发送' }}</button>
    </div>

    <!-- 规划悬浮窗：采集完偏好后弹出，可编辑槽位重生成 / 确认 -->
    <PlanOverlay :show="showPlan" :initial-plan="planInOverlay" @close="showPlan = false" />

    <!-- 执行确认弹窗：步骤1确认方案 → 步骤2询问是否预约订票 -->
    <div v-if="showConfirm" class="confirm-mask" @click.self="cancelExecute">
      <div class="confirm-sheet">
        <template v-if="confirmStep === 1">
          <div class="cf-title">是否按照方案执行？</div>
          <div class="cf-sub">确认后为你预约 / 排号，并跳转「规划」页查看路线；选择「继续沟通」可留在对话里调整方案。</div>
          <div v-if="pendingPlan && pendingPlan.itinerary && pendingPlan.itinerary.length" class="cf-stops">
            <span v-for="(s, i) in pendingPlan.itinerary" :key="i" class="cf-stop">{{ s.name || s.title }}</span>
          </div>
          <div v-if="movieOptions(pendingPlan).length" class="cf-movie">
            <div class="cf-movie-title">🎬 想看哪部影片？（默认选第一部）</div>
            <div class="cf-movies">
              <span v-for="mv in movieOptions(pendingPlan)" :key="mv" class="cf-chip" :class="{ on: chosenMovie === mv }" @click="chosenMovie = mv">{{ mv }}</span>
            </div>
          </div>
          <div class="cf-actions">
            <button class="cf-btn ghost" @click="cancelExecute">继续沟通，不执行</button>
            <button class="cf-btn primary" @click="confirmStep = 2">同意，继续</button>
          </div>
        </template>
        <template v-else>
          <div class="cf-title">是否需要我帮你预约和订票？</div>
          <div class="cf-sub">将为你预约可预约店铺、购买演示票券，并进入排队（到号会实时提醒）；选择「先不用」可直接看方案。</div>
          <div class="cf-actions">
            <button class="cf-btn ghost" @click="runExecute(false)">先不用，直接看方案</button>
            <button class="cf-btn primary" @click="runExecute(true)">要，帮我预约和订票</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page { height: 100%; display: flex; flex-direction: column; background: var(--bg); }
.chat-scroll { flex: 1; overflow-y: auto; padding: 18px 16px; }
.row { display: flex; margin: 12px 0; }
.row.user { justify-content: flex-end; }
.row.ai { align-items: flex-start; }
.bubble { max-width: 78%; padding: 12px 15px; font-size: 15px; line-height: 1.55; word-break: break-word; }
.user-bubble { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border-radius: 16px 16px 4px 16px; box-shadow: 0 6px 14px rgba(124,58,237,0.25); }
.ai-avatar { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg, #ede9fe, #e0f2fe); color: var(--primary); font-weight: 700; font-size: 13px; display: flex; align-items: center; justify-content: center; margin-right: 10px; flex-shrink: 0; }
.ai-body { flex: 1; }
.ai-bubble { display: inline-block; background: #fff; color: var(--text); border: 1px solid var(--border); border-radius: 16px 16px 16px 4px; }
.ref-bubble { background: #f3f4f6; color: #4b5563; border: 1px dashed #d1d5db; border-radius: 16px 16px 16px 4px; }
.ref-text { font-weight: 600; }
.ai-bubble :deep(p) { margin: 0 0 0.5em; }
.ai-bubble :deep(p:last-child) { margin-bottom: 0; }
.ai-bubble :deep(ul), .ai-bubble :deep(ol) { margin: 0.4em 0; padding-left: 1.3em; }
.ai-bubble :deep(li) { margin: 0.2em 0; }
.ai-bubble :deep(strong) { font-weight: 700; color: var(--primary-dark); }
.ai-bubble :deep(em) { font-style: italic; }
.ai-bubble :deep(code) { background: #f1f5f9; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; font-family: ui-monospace, Consolas, monospace; }
.ai-bubble :deep(h1), .ai-bubble :deep(h2), .ai-bubble :deep(h3) { font-size: 1.05em; font-weight: 700; margin: 0.5em 0 0.2em; }
.plan-hint { display: inline-block; margin-top: 8px; color: var(--primary); font-weight: 600; font-size: 13px; background: #ede9fe; padding: 6px 14px; border-radius: 18px; cursor: pointer; }
.plan-inline { margin-top: 10px; }
.pi-title { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 14px; margin-bottom: 6px; }
.pi-done { background: #ecfdf5; color: #10B981; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 14px; }
.pi-empty { background: #fff; border-radius: 14px; padding: 20px; text-align: center; color: #9CA3AF; font-size: 13px; }
.pi-confirm { background: #fff; border-radius: 14px; padding: 16px; box-shadow: 0 6px 16px rgba(124,58,237,0.06); }
.pi-empty-t { text-align: center; color: #6b7280; font-size: 13px; margin-bottom: 14px; }
.pi-confirm .ic-btns { display: flex; gap: 12px; }
.pi-confirm .ic-btn { flex: 1; border: none; border-radius: 22px; padding: 11px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.pi-confirm .ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.pi-confirm .ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.confirm-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 70; display: flex; align-items: flex-end; }
.confirm-sheet { width: 100%; background: #fff; border-radius: 20px 20px 0 0; padding: 22px 22px 30px; }
.cf-title { font-size: 18px; font-weight: 800; text-align: center; }
.cf-sub { font-size: 13px; color: #6b7280; text-align: center; margin: 10px 0 16px; line-height: 1.6; }
.cf-stops { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 16px; }
.cf-stop { background: #ede9fe; color: #7C3AED; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 18px; }
.cf-movie { margin: 4px 0 14px; }
.cf-movie-title { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.cf-movies { display: flex; flex-wrap: wrap; gap: 8px; }
.cf-chip { font-size: 13px; padding: 6px 14px; border-radius: 18px; background: #f1f5f9; color: #475569; cursor: pointer; }
.cf-chip.on { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.cf-actions { display: flex; gap: 12px; }
.cf-btn { flex: 1; border: none; border-radius: 22px; padding: 12px 0; font-size: 14px; font-weight: 600; cursor: pointer; }
.cf-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.cf-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }

.composer { display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: #fff; border-top: 1px solid var(--border); }
.ci { flex: 1; background: var(--bg); border: none; border-radius: 24px; padding: 11px 16px; font-size: 15px; }
.ci:focus { outline: none; }
.mic { font-size: 22px; cursor: pointer; }
.mic.on { animation: mic-pulse 1s ease infinite; }
@keyframes mic-pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.25); } }
.send-btn { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border: none; border-radius: 24px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; }
</style>
