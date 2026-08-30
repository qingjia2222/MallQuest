<script setup>
import { computed } from 'vue';
const props = defineProps({ free: Number, total: Number });
const deg = computed(() => (props.total ? Math.round((props.free / props.total) * 360) : 0));
const ring = computed(() => `conic-gradient(#06B6D4 ${deg.value}deg, #eef2ff 0deg)`);
</script>

<template>
  <div class="gauge" :style="{ background: ring }">
    <div class="inner">
      <div class="num">{{ free }}</div>
      <div class="total">/ {{ total }} 空位</div>
    </div>
  </div>
</template>

<style scoped>
.gauge { width: 110px; height: 110px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.inner { width: 78px; height: 78px; border-radius: 50%; background: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.num { font-size: 28px; font-weight: 800; color: #06B6D4; }
.total { font-size: 11px; color: var(--muted); }
</style>
