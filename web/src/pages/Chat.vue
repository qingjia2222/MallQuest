<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import api, { BASE } from '../api';
import RichCard from '../components/RichCard.vue';
import { setCurrentPlan } from '../store/plan';

const router = useRouter();
const messages = ref([]);
const input = ref('发个「停车场还有空位吗？」试试智能对话');
const loading = ref(false);
const currentPlan = ref(null);
const navigation = ref(null); const navVisible = ref(false); const navStep = ref(0); let navTimer;
const currentNode = computed(() => navigation.value?.nodes?.[navStep.value] || null);
const navFloor = computed(() => currentNode.value?.floor || 1);
const floorNodes = computed(() => (navigation.value?.nodes || []).filter(n => n.floor === navFloor.value));
const progressNodes = computed(() => (navigation.value?.nodes || []).slice(0, navStep.value + 1).filter(n => n.floor === navFloor.value));
const points = nodes => nodes.map(n => `${n.x},${n.y}`).join(' ');

onMounted(() => {
  const name = localStorage.getItem('mall_name') || 'QD square';
  push('ai', `已接入「${name}」私有数据。我是你的 AI 私域助手，可以问我停车、积分、特惠，或说「帮我规划约会」让我安排。`);
  const prefill = localStorage.getItem('prefill');
  if (prefill) { localStorage.removeItem('prefill'); send(prefill); }
});

function push(role, text) { messages.value.push({ role, text: role === 'ai' ? String(text || '').replace(/\*/g, '') : text, cards: [] }); }
function scroll() { requestAnimationFrame(() => { const el = document.querySelector('.chat-scroll'); if (el) el.scrollTop = el.scrollHeight; }); }

// 把后端的 cards 映射成前端富卡片类型
function toCards(cards) {
  if (!Array.isArray(cards)) return [];
  return cards.map(c => {
    const type = c.type || (c.data && (Array.isArray(c.data) ? 'list' : 'generic'));
    return { type, data: c.data };
  });
}

async function send(txt) {
  const text = (txt ?? input.value).trim();
  if (!text || loading.value) return;
  input.value = '';
  push('user', text);
  scroll();
  loading.value = true;
  try {
    const data = await api.chat(text);
    let reply = data.reply || '好的，已为你处理。';
    // 若走了在线 agent，content 为空但 reply 由后端组织
    push('ai', reply);
    const msg = messages.value[messages.value.length - 1];
    msg.cards = toCards(data.cards);
    if (data.plan) { currentPlan.value = data.plan; setCurrentPlan(data.plan); msg.plan = data.plan; }
    if (data.navigation) { navigation.value = data.navigation; replayNavigation(); }
    scroll();
  } catch (e) {
    push('ai', '抱歉，请求后端失败：' + (e.message || ''));
    scroll();
  } finally { loading.value = false; }
}

function goPlan() { router.push('/plan'); }
function onCardTap(card) {
  if (card.type === 'parking') router.push('/map');
  else if (card.type === 'coupon' || card.type === 'deals') router.push('/coupon');
  else if (card.type === 'store' || card.type === 'list') router.push('/map');
}
function replayNavigation(){clearInterval(navTimer);navVisible.value=true;navStep.value=0;navTimer=setInterval(()=>{if(navStep.value >= navigation.value.nodes.length-1)clearInterval(navTimer);else navStep.value++},520)}
function closeNavigation(){clearInterval(navTimer);navVisible.value=false} onUnmounted(()=>clearInterval(navTimer));
</script>

<template>
  <div class="chat-page">
    <div class="chat-scroll">
      <div v-for="(m, i) in messages" :key="i">
        <div v-if="m.role === 'user'" class="row user"><div class="bubble user-bubble">{{ m.text }}</div></div>
        <div v-else class="row ai">
          <div class="ai-avatar">AI</div>
          <div class="ai-body">
            <div class="bubble ai-bubble">{{ m.text }}</div>
            <RichCard v-for="(c, j) in m.cards" :key="j" :card="c" @tap="onCardTap" />
            <div v-if="m.plan" class="plan-hint" @click="goPlan">📋 已生成方案，查看详情 →</div>
          </div>
        </div>
      </div>
    </div>

    <div class="composer">
      <input class="ci" v-model="input" @keyup.enter="send()" placeholder="问我任何商场问题…" />
      <div class="mic" @click="send('帮我规划约会')">🎤</div>
      <button class="send-btn" :disabled="loading" @click="send()">{{ loading ? '…' : '发送' }}</button>
    </div>
    <div v-if="navVisible" class="nav-mask"><div class="nav-modal"><div class="nav-head"><div><small>3D ROUTE · 自动导览</small><h2>前往 {{navigation.destination_store.name}}</h2></div><button @click="closeNavigation">×</button></div><div class="nav-stage" :style="{backgroundImage:`url(${api.mapFloorUrl(navFloor)})`}"><svg viewBox="0 0 1000 760"><polyline :points="points(floorNodes)" class="route-all"/><polyline :points="points(progressNodes)" class="route-progress"/><circle v-if="currentNode" :cx="currentNode.x" :cy="currentNode.y" r="18" class="dot"/></svg><span class="floor">{{navFloor}}F</span><span class="you">红点 = 您当前所在位置</span></div><p>约 {{navigation.estimated_distance}} · 可重播、可关闭</p><div class="nav-actions"><button @click="replayNavigation">↻ 重播路线</button><button class="done" @click="closeNavigation">关闭导览</button></div></div></div>
  </div>
</template>

<style scoped>
.chat-page { height: 100%; display: flex; flex-direction: column; background: var(--bg); }
.chat-scroll { flex: 1; overflow-y: auto; padding: 18px 16px; }
.row { display: flex; margin: 12px 0; }
.row.user { justify-content: flex-end; }
.row.ai { align-items: flex-start; }
.bubble { max-width: 78%; padding: 12px 15px; font-size: 15px; line-height: 1.55; word-break: break-word; white-space: pre-wrap; }
.user-bubble { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border-radius: 16px 16px 4px 16px; box-shadow: 0 6px 14px rgba(124,58,237,0.25); }
.ai-avatar { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg, #ede9fe, #e0f2fe); color: var(--primary); font-weight: 700; font-size: 13px; display: flex; align-items: center; justify-content: center; margin-right: 10px; flex-shrink: 0; }
.ai-body { flex: 1; }
.ai-bubble { display: inline-block; background: #fff; color: var(--text); border: 1px solid var(--border); border-radius: 16px 16px 16px 4px; }
.plan-hint { display: inline-block; margin-top: 8px; color: var(--primary); font-weight: 600; font-size: 13px; background: #ede9fe; padding: 6px 14px; border-radius: 18px; cursor: pointer; }
.quick-bar { white-space: nowrap; padding: 8px 0; border-top: 1px solid var(--border); overflow-x: auto; }
.quick-inner { display: inline-flex; padding: 0 16px; }
.composer { display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: #fff; border-top: 1px solid var(--border); }
.ci { flex: 1; background: var(--bg); border: none; border-radius: 24px; padding: 11px 16px; font-size: 15px; }
.ci:focus { outline: none; }
.mic { font-size: 22px; cursor: pointer; }
.send-btn { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border: none; border-radius: 24px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; }
.nav-mask{position:fixed;z-index:100;inset:0;background:#090b19cc;display:flex;align-items:center;justify-content:center;padding:24px}.nav-modal{width:min(720px,94vw);background:#fff;border-radius:24px;padding:24px}.nav-head{display:flex;justify-content:space-between}.nav-head small{color:#7c3aed;letter-spacing:3px}.nav-head h2{margin:7px 0}.nav-head button{border:0;background:none;font-size:32px}.nav-stage{position:relative;height:430px;background-size:100% 100%;border-radius:18px;overflow:hidden;transform:perspective(900px) rotateX(5deg);box-shadow:0 25px 45px #4c1d9533}.nav-stage svg{width:100%;height:100%}.route-all{fill:none;stroke:#7c3aed55;stroke-width:12;stroke-linecap:round;stroke-linejoin:round}.route-progress{fill:none;stroke:#ef4444;stroke-width:15;stroke-linecap:round;stroke-linejoin:round}.dot{fill:#ef4444;stroke:#fff;stroke-width:10}.floor,.you{position:absolute;background:#111827dd;color:#fff;border-radius:18px;padding:6px 10px;font-size:12px}.floor{right:12px;top:12px}.you{left:12px;bottom:12px}.nav-modal>p{text-align:center;color:#6b7280}.nav-actions{display:flex;gap:12px}.nav-actions button{flex:1;border:0;border-radius:24px;padding:12px;color:#6d28d9;background:#f5f3ff}.nav-actions .done{color:#fff;background:#7c3aed}
</style>
