<script setup>
import { computed } from 'vue';
const props = defineProps({ card: Object });
const emit = defineEmits(['tap']);
function tap() { emit('tap', props.card); }

// 统一取底层数据（兼容前端 mock 形状 + 队友后端形状）
const d = computed(() => props.card && props.card.data || {});
// 后端停车返回 { areas:[], total_free }；前端 mock 返回 { free, total, areas }
const parkFree = computed(() => d.value.total_free ?? d.value.free ?? 0);
const parkTotal = computed(() => (d.value.total ?? (d.value.areas || []).reduce((a, x) => a + (x.total || 0), 0)) || 0);
const parkRatio = computed(() => parkTotal.value ? Math.round(parkFree.value / parkTotal.value * 100) : 0);
const parkAreas = computed(() => d.value.areas || []);

const emoji = { '火锅': '🍲', '饮品': '🧋', '影院': '🎬', '甜品': '🍰', '咖啡': '☕', '川菜': '🥘', '西餐': '🍝', '亲子餐厅': '🍼' };
function cateEmoji(c) { return emoji[c] || '🏬'; }
function storeName(s) { return s.name || s.store_name || s.title || ''; }
function storeCat(s) { return s.category || s.type || ''; }
function storeFloor(s) { return s.floor ?? s.floor_label ?? ''; }
function storeDesc(s) { return s.desc || s.description || ''; }
</script>

<template>
  <!-- 店铺 / 列表卡（后端 search_stores 返回数组） -->
  <div v-if="(card.type === 'store' || card.type === 'list') && !Array.isArray(d)" class="rc rc-store" @click="tap">
    <div class="rc-avatar">{{ cateEmoji(storeCat(d)) }}</div>
    <div class="rc-main">
      <div class="rc-name">{{ storeName(d) }}</div>
      <div class="rc-sub">{{ storeCat(d) }}<template v-if="storeFloor(d)"> · {{ storeFloor(d) }}F</template></div>
      <div v-if="storeDesc(d)" class="rc-desc">{{ storeDesc(d) }}</div>
    </div>
    <div v-if="d.waiting != null" class="rc-wait" :class="{ busy: d.waiting > 10 }">{{ d.waiting }} 桌</div>
  </div>

  <!-- 停车卡（兼容 areas[] 与 free/total） -->
  <div v-else-if="card.type === 'parking'" class="rc rc-parking" @click="tap">
    <div class="rc-name">🅿️ 实时停车位</div>
    <div class="pk-row">
      <div class="pk-num">{{ parkFree }}<small> / {{ parkTotal }} 空位</small></div>
      <div class="pk-bar"><div class="pk-inner" :style="{ width: parkRatio + '%' }"></div></div>
    </div>
    <div v-if="parkAreas.length" class="pk-areas">
      <span v-for="a in parkAreas" :key="a.area" class="pk-area">{{ a.area }} <b>{{ a.free }}</b>/{{ a.total }}</span>
    </div>
  </div>

  <!-- RAG 知识卡（后端积分规则返回 { answer, sources }） -->
  <div v-else-if="card.type === 'rag'" class="rc rc-rag" @click="tap">
    <div class="rc-name">📖 规则知识库</div>
    <div class="rc-answer">{{ d.answer || '' }}</div>
    <div v-if="d.sources && d.sources.length" class="rc-src">来源：{{ d.sources[0].doc }}</div>
  </div>

  <!-- 优惠券卡 -->
  <div v-else-if="card.type === 'coupon'" class="rc rc-coupon" @click="tap">
    <div class="cp-l"><div class="cp-t">{{ d.title }}</div><div class="cp-s">{{ d.scope || d.description || '' }}</div></div>
    <div class="cp-r"><div class="cp-exp">{{ d.expire || '' }}</div><button class="cp-btn">领取</button></div>
  </div>

  <!-- 通用 -->
  <div v-else class="rc rc-gen" @click="tap">
    <div class="rc-name">{{ card.title }}</div>
    <div class="rc-sub">{{ card.subtitle }}</div>
  </div>
</template>

<style scoped>
.rc { background: #fff; border-radius: 16px; padding: 16px; margin: 10px 0; box-shadow: 0 6px 18px rgba(124,58,237,0.08); cursor: pointer; animation: rcIn .3s ease; display: flex; align-items: center; gap: 14px; }
@keyframes rcIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.rc-avatar { width: 48px; height: 48px; border-radius: 12px; background: linear-gradient(135deg, #ede9fe, #e0f2fe); display: flex; align-items: center; justify-content: center; font-size: 26px; }
.rc-main { flex: 1; }
.rc-name { font-weight: 700; font-size: 16px; }
.rc-sub { font-size: 13px; color: var(--muted); margin-top: 2px; }
.rc-desc { font-size: 13px; color: var(--muted); margin-top: 4px; }
.rc-wait { font-size: 13px; color: var(--success); font-weight: 600; background: #ecfdf5; padding: 4px 12px; border-radius: 20px; }
.rc-wait.busy { color: var(--warning); background: #fffbeb; }
.pk-row { flex: 1; }
.pk-num { font-size: 26px; font-weight: 800; color: var(--primary); }
.pk-num small { font-size: 13px; color: var(--muted); }
.pk-bar { height: 8px; background: #f3f4f6; border-radius: 6px; margin-top: 8px; overflow: hidden; }
.pk-inner { height: 100%; background: linear-gradient(90deg, var(--primary), var(--cyan)); border-radius: 6px; }
.pk-areas { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pk-area { background: #f9fafb; border-radius: 8px; padding: 4px 8px; font-size: 12px; color: var(--muted); }
.pk-area b { color: var(--primary); }
.rc-rag { flex-direction: column; align-items: flex-start; }
.rc-answer { font-size: 14px; color: var(--text); margin-top: 6px; line-height: 1.6; }
.rc-src { font-size: 11px; color: #9CA3AF; margin-top: 8px; }
.rc-coupon { justify-content: space-between; }
.cp-l { display: flex; flex-direction: column; }
.cp-s { font-size: 13px; color: var(--muted); margin-top: 4px; }
.cp-r { display: flex; flex-direction: column; align-items: flex-end; }
.cp-exp { font-size: 12px; color: var(--warning); margin-bottom: 8px; }
.cp-btn { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; border: none; border-radius: 20px; padding: 6px 18px; cursor: pointer; }
</style>
