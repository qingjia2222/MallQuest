<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api, { BASE } from '../api';
import RichCard from '../components/RichCard.vue';
import { setCurrentPlan } from '../store/plan';

const router = useRouter();
const messages = ref([]);
const input = ref('发个「停车场还有空位吗？」试试智能对话');
const loading = ref(false);
const currentPlan = ref(null);
const quickActions = ['停车场还有空位吗？', '积分多久过期？', '今天有什么特惠？', '有什么好吃的推荐？', '帮我规划约会'];

onMounted(() => {
  const name = localStorage.getItem('mall_name') || 'QD square';
  push('ai', `已接入「${name}」私有数据。我是你的 AI 私域助手，可以问我停车、积分、特惠，或说「帮我规划约会」让我安排。`);
  const prefill = localStorage.getItem('prefill');
  if (prefill) { localStorage.removeItem('prefill'); send(prefill); }
});

function push(role, text) { messages.value.push({ role, text, cards: [] }); }
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

    <div class="quick-bar">
      <div class="quick-inner">
        <span v-for="q in quickActions" :key="q" class="chip" @click="send(q)">{{ q }}</span>
      </div>
    </div>

    <div class="composer">
      <input class="ci" v-model="input" @keyup.enter="send()" placeholder="问我任何商场问题…" />
      <div class="mic" @click="send('帮我规划约会')">🎤</div>
      <button class="send-btn" :disabled="loading" @click="send()">{{ loading ? '…' : '发送' }}</button>
    </div>
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
</style>
