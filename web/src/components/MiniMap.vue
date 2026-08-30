<script setup>
import { computed, watch } from 'vue';
const props = defineProps({
  stores: Array,
  route: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
  floor: { type: Number, default: 1 }
});
const emit = defineEmits(['storetap', 'floor']);

const byId = computed(() => { const m = {}; (props.stores || []).forEach(s => m[s.id] = s); return m; });
const segs = computed(() => {
  const out = [];
  const r = props.route;
  r.forEach((id, i) => {
    if (i < r.length - 1 && byId.value[id] && byId.value[r[i + 1]]) {
      const a = byId.value[id], b = byId.value[r[i + 1]];
      out.push({ x: Math.min(a.pos_x, b.pos_x), y: Math.min(a.pos_y, b.pos_y), w: Math.abs(a.pos_x - b.pos_x), h: 0.5 });
      out.push({ x: a.pos_x, y: Math.min(a.pos_y, b.pos_y), w: 0.5, h: Math.abs(a.pos_y - b.pos_y) });
    }
  });
  return out;
});

function tap(s) { emit('storetap', s); }
function setFloor(f) { emit('floor', f); }
const emoji = { '火锅': '🍲', '饮品': '🧋', '影院': '🎬', '甜品': '🍰', '咖啡': '☕' };
function cateEmoji(c) { return emoji[c] || '🏬'; }
</script>

<template>
  <div class="mm">
    <div class="mm-floors">
      <div v-for="f in [1,2,3,4]" :key="f" class="mm-floor" :class="{ active: floor === f }" @click="setFloor(f)">{{ f }}F</div>
    </div>
    <div class="mm-canvas">
      <div class="mm-grid"></div>
      <div v-for="(s, i) in segs" :key="'s'+i" class="mm-seg" :style="{ left: s.x+'%', top: s.y+'%', width: s.w+'%', height: s.h+'%' }"></div>
      <div v-for="s in stores" :key="s.id" class="mm-store"
           :class="{ active: s.id === activeId, dim: s.floor !== floor }"
           :style="{ left: s.pos_x+'%', top: s.pos_y+'%' }" @click="tap(s)">
        <span class="mm-emoji">{{ cateEmoji(s.category) }}</span>
      </div>
    </div>
    <div class="mm-legend">轻点节点可查看店铺 · 紫青连线为规划路线</div>
  </div>
</template>

<style scoped>
.mm { position: relative; background: #fff; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 24px rgba(124,58,237,0.08); }
.mm-floors { position: absolute; top: 12px; left: 12px; z-index: 5; display: flex; flex-direction: column; gap: 6px; }
.mm-floor { width: 34px; height: 30px; border-radius: 8px; background: rgba(255,255,255,0.92); color: var(--muted); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.08); cursor: pointer; }
.mm-floor.active { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.mm-canvas { position: relative; height: 300px; }
.mm-grid { position: absolute; inset: 0; background-image: linear-gradient(#f3f4f6 1px, transparent 1px), linear-gradient(90deg, #f3f4f6 1px, transparent 1px); background-size: 32px 32px; }
.mm-seg { position: absolute; background: linear-gradient(90deg, var(--primary), var(--cyan)); border-radius: 3px; }
.mm-store { position: absolute; transform: translate(-50%,-50%); width: 36px; height: 36px; border-radius: 50%; background: #fff; box-shadow: 0 3px 10px rgba(0,0,0,0.14); display: flex; align-items: center; justify-content: center; font-size: 18px; cursor: pointer; transition: all .2s; }
.mm-store.active { background: linear-gradient(135deg, var(--primary), var(--cyan)); transform: translate(-50%,-50%) scale(1.3); box-shadow: 0 0 0 6px rgba(124,58,237,0.18); }
.mm-store.dim { opacity: 0.4; }
.mm-legend { text-align: center; font-size: 11px; color: #9CA3AF; padding: 9px; }
</style>
