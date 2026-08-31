<script setup>
const props = defineProps({ itinerary: Object });
const emit = defineEmits(['stoptap', 'confirm', 'change', 'strategy']);

function stop(i) { emit('stoptap', i); }
</script>

<template>
  <div class="ic">
    <div class="ic-title">
      <span>推荐方案</span>
      <span class="ic-tag">{{ itinerary.tag || '为你定制' }}</span>
    </div>

    <div v-if="itinerary.alternatives && itinerary.alternatives.length" class="ic-strategies">
      <div class="ic-strategy-title">选择优化目标</div>
      <button v-for="a in itinerary.alternatives" :key="a.strategy" class="ic-strategy" :class="{ selected: a.strategy === itinerary.selectedStrategy }" @click="emit('strategy', a.strategy)">
        <span><b>{{ a.label }}</b><small>{{ a.strategy === itinerary.selectedStrategy ? '当前方案' : '点击切换' }}</small></span>
        <span class="ic-metrics">生成时预计 {{ a.estimated_total_minutes }} 分钟 · 路程 {{ a.estimated_distance }} · 等候 {{ a.estimated_wait_minutes }} 分钟</span>
      </button>
    </div>

    <div class="ic-timeline">
      <div v-for="(s, i) in itinerary.stops" :key="i" class="ic-stop" @click="stop(i)">
        <div class="ic-rail">
          <div class="ic-node" :class="{ start: i === 0 }"></div>
          <div v-if="i < itinerary.stops.length - 1" class="ic-conn"></div>
        </div>
        <div class="ic-body">
          <div class="ic-head">
            <span class="ic-time">{{ s.time }}</span>
            <span class="ic-name">{{ s.name }}</span>
            <span v-if="s.waiting" class="ic-wait" :class="{ busy: s.waiting > 10 }">{{ s.waiting }} 分钟</span>
          </div>
          <div class="ic-meta">{{ s.floor }} 层 · {{ s.category }}</div>
        </div>
      </div>
    </div>

    <div v-if="itinerary.actions && itinerary.actions.length" class="ic-actions">
      <div v-for="(a, i) in itinerary.actions" :key="i" class="ic-action">
        <span class="ic-check" :class="{ ok: a.ok, fail: !a.ok }">{{ a.ok ? '✓' : '×' }}</span>
        <span>{{ a.label }}</span>
      </div>
    </div>

    <div class="ic-btns">
      <button class="ic-btn ghost" @click="emit('change')">换一版</button>
      <button class="ic-btn primary" @click="emit('confirm')">就按这个</button>
    </div>
  </div>
</template>

<style scoped>
.ic { background: #fff; border-radius: 18px; padding: 18px; box-shadow: 0 8px 24px rgba(124,58,237,0.08); }
.ic-title { display: flex; align-items: center; justify-content: space-between; font-weight: 700; font-size: 17px; }
.ic-tag { font-size: 12px; color: var(--primary); background: #ede9fe; padding: 3px 12px; border-radius: 20px; font-weight: 500; }
.ic-strategies{display:flex;flex-direction:column;gap:8px;margin-top:14px}.ic-strategy-title{font-size:12px;color:#6b7280}.ic-strategy{border:1px solid #e5e7eb;background:#fff;border-radius:12px;padding:10px 12px;text-align:left;color:#1f2937}.ic-strategy.selected{border-color:var(--primary);background:#f5f3ff}.ic-strategy span:first-child{display:flex;justify-content:space-between}.ic-strategy small{color:var(--primary)}.ic-metrics{display:block;margin-top:5px;font-size:11px;color:#6b7280}
.ic-timeline { margin-top: 16px; }
.ic-stop { display: flex; cursor: pointer; }
.ic-rail { width: 22px; display: flex; flex-direction: column; align-items: center; }
.ic-node { width: 11px; height: 11px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--cyan)); margin-top: 6px; flex-shrink: 0; }
.ic-node.start { box-shadow: 0 0 0 4px rgba(124,58,237,0.2); }
.ic-conn { flex: 1; width: 3px; background: #ede9fe; margin: 3px 0; }
.ic-body { flex: 1; padding: 0 0 18px 10px; }
.ic-head { display: flex; align-items: center; gap: 10px; }
.ic-time { font-size: 13px; color: var(--primary); font-weight: 700; }
.ic-name { font-size: 15px; font-weight: 600; }
.ic-wait { font-size: 12px; color: var(--success); }
.ic-wait.busy { color: var(--warning); }
.ic-meta { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
.ic-actions { border-top: 1px dashed var(--border); padding-top: 12px; margin-top: 4px; display: flex; flex-direction: column; gap: 8px; }
.ic-action { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.ic-check { width: 18px; height: 18px; border-radius: 50%; text-align: center; line-height: 18px; font-size: 12px; }
.ic-check.ok { background: #ecfdf5; color: var(--success); }
.ic-check.fail { background: #fee2e2; color: var(--danger); }
.ic-btns { display: flex; gap: 12px; margin-top: 18px; }
.ic-btn { flex: 1; border-radius: 24px; padding: 11px 0; font-size: 15px; font-weight: 600; cursor: pointer; border: none; }
.ic-btn.ghost { background: #fff; color: var(--primary); border: 1px solid var(--border); }
.ic-btn.primary { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
</style>
