<script setup>
import { ref, computed } from 'vue';
import planData from '../store/mall_plan.json';

// 平面图：腾讯/高德风格的室内商场图，用真实店名（来源：蜂鸟云 fmap 解析出的西安大悦城 POI）
const props = defineProps({
  activeId: { type: String, default: '' }
});
const emit = defineEmits(['storetap']);

const floors = ['F1', 'F2', 'F3', 'F4'];
const curFloor = ref('F1');
const currStores = computed(() => planData.filter(s => s.floor === curFloor.value));

// 分类配色（商场平面图常见的分色块）
const catColor = { 餐饮: '#7C3AED', 零售: '#06B6D4', 教育: '#F59E0B', 设施: '#9CA3AF' };
function color(c) { return catColor[c] || '#9CA3AF'; }

function tap(store) { emit('storetap', store); }

// 商场中庭/通道装饰（几块浅灰区块模拟通道与中庭）
const atriums = [
  { x: 40, y: 44, w: 20, h: 12, label: '中庭' },
  { x: 16, y: 44, w: 20, h: 12, label: '回廊' },
  { x: 64, y: 44, w: 20, h: 12, label: '连廊' }
];
</script>

<template>
  <div class="pmap">
    <div class="pmap-top">
      <div class="pmap-title">西安大悦城 · 室内平面图</div>
      <div class="pmap-floors">
        <span v-for="f in floors" :key="f" class="pmap-floor" :class="{ active: curFloor === f }" @click="curFloor = f">
          {{ f === 'F1' ? '1F' : f === 'F2' ? '2F' : f === 'F3' ? '3F' : '4F' }}
        </span>
      </div>
    </div>

    <div class="pmap-canvas">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="pmap-svg">
        <!-- 商场外框 -->
        <rect x="2" y="4" width="96" height="92" rx="2" class="pmap-outline" />
        <!-- 中庭/回廊 -->
        <rect v-for="a in atriums" :key="a.label" :x="a.x" :y="a.y" :width="a.w" :height="a.h" class="pmap-aisle" />
        <!-- 店铺格子 -->
        <g v-for="(s, i) in currStores" :key="s.name + i" class="pmap-shop" @click="tap(s)">
          <rect :x="s.x" :y="s.y" :width="s.w" :height="s.h" rx="1" :fill="color(s.cat)" class="pmap-rect" />
          <text :x="s.x + 1" :y="s.y + 7" class="pmap-label">{{ s.name }}</text>
        </g>
      </svg>
      <div class="pmap-legend">
        <span><i style="background:#7C3AED"></i>餐饮</span>
        <span><i style="background:#06B6D4"></i>零售</span>
        <span><i style="background:#F59E0B"></i>教育/儿童</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pmap { background: #fff; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 24px rgba(124,58,237,0.08); }
.pmap-top { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px 8px; }
.pmap-title { font-weight: 700; font-size: 15px; color: var(--text); }
.pmap-floors { display: flex; gap: 6px; }
.pmap-floor { width: 32px; height: 28px; border-radius: 8px; background: #f3f4f6; color: var(--muted); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; cursor: pointer; }
.pmap-floor.active { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.pmap-canvas { position: relative; padding: 8px 12px 10px; }
.pmap-svg { width: 100%; height: 320px; display: block; }
.pmap-outline { fill: #f7f8fb; stroke: #d1d5db; stroke-width: 0.6; }
.pmap-aisle { fill: #eef0f5; opacity: 0.8; }
.pmap-shop { cursor: pointer; }
.pmap-rect { opacity: 0.92; transition: opacity .15s; }
.pmap-shop:hover .pmap-rect { opacity: 1; stroke: #111; stroke-width: 0.4; }
.pmap-label { font-size: 2.3px; fill: #fff; font-weight: 600; pointer-events: none; }
.pmap-legend { display: flex; gap: 14px; padding: 6px 4px 4px; font-size: 12px; color: var(--muted); }
.pmap-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
</style>
