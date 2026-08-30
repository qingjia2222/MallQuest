<script setup>
defineProps({ coupon: Object, claimed: Boolean });
const emit = defineEmits(['claim']);
function claim() { emit('claim', coupon); }
</script>

<template>
  <div class="ct" :style="{ '--cp': coupon.color || '#7C3AED' }">
    <div class="ct-main">
      <div class="ct-title">{{ coupon.title }}</div>
      <div class="ct-scope">{{ coupon.scope }}</div>
      <div class="ct-notch top"></div>
      <div class="ct-notch bottom"></div>
    </div>
    <div class="ct-side" :class="{ claimed }" @click="claim">
      <span v-if="!claimed">领</span><span v-else>✓</span>
    </div>
  </div>
</template>

<style scoped>
.ct { position: relative; display: flex; background: #fff; border-radius: 14px; overflow: hidden; box-shadow: 0 5px 16px rgba(0,0,0,0.06); margin: 10px 0; }
.ct-main { flex: 1; padding: 14px 18px; border-right: 1px dashed rgba(0,0,0,0.08); }
.ct-title { font-weight: 700; font-size: 15px; }
.ct-scope { font-size: 12px; color: #9CA3AF; margin-top: 5px; }
.ct-notch { position: absolute; width: 14px; height: 14px; border-radius: 50%; background: var(--bg); left: calc(76% - 7px); }
.ct-notch.top { top: -7px; }
.ct-notch.bottom { bottom: -7px; }
.ct-side { width: 52px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, var(--cp), var(--cyan)); color: #fff; font-size: 22px; font-weight: 800; cursor: pointer; }
.ct-side.claimed { background: #e5e7eb; color: var(--success); font-size: 18px; }
</style>
