<script setup>
defineProps({
  step: Number,
  stepNames: { type: Array, default: () => ['理解目标', '采集偏好', '生成方案', '确认方案', '执行'] }
});
</script>

<template>
  <div class="pf">
    <template v-for="(name, i) in stepNames" :key="i">
      <div class="pf-item" :class="{ done: i + 1 <= step, cur: i + 1 === step }">
        <div class="pf-dot"><span v-if="i + 1 < step">✓</span><span v-else>{{ i + 1 }}</span></div>
        <div class="pf-label">{{ name }}</div>
      </div>
      <div v-if="i < stepNames.length - 1" class="pf-line" :class="{ done: i + 1 < step }"></div>
    </template>
  </div>
</template>

<style scoped>
.pf { display: flex; align-items: flex-start; padding: 6px 0; }
.pf-item { display: flex; flex-direction: column; align-items: center; }
.pf-dot { width: 26px; height: 26px; border-radius: 50%; background: #f3f4f6; color: #9CA3AF; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; transition: all .3s; }
.pf-item.done .pf-dot { background: linear-gradient(135deg, var(--primary), var(--cyan)); color: #fff; }
.pf-item.cur .pf-dot { background: var(--primary); color: #fff; box-shadow: 0 0 0 5px rgba(124,58,237,0.15); }
.pf-label { font-size: 11px; color: #9CA3AF; margin-top: 6px; white-space: nowrap; }
.pf-item.done .pf-label, .pf-item.cur .pf-label { color: var(--primary-dark); font-weight: 600; }
.pf-line { flex: 1; height: 3px; background: #f3f4f6; margin-top: 12px; border-radius: 3px; }
.pf-line.done { background: var(--primary); }
</style>
