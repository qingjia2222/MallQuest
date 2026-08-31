// src/store/plan.js - 共享当前规划方案（Chat 生成 → Map/Result 消费）
import { reactive } from 'vue';
let restored = null;
try { restored = JSON.parse(localStorage.getItem('mall_current_plan') || 'null'); } catch (_) {}
export const planStore = reactive({ current: restored, navigateTarget: null });

export function setCurrentPlan(p) {
  planStore.current = p;
  if (p) localStorage.setItem('mall_current_plan', JSON.stringify(p));
  else localStorage.removeItem('mall_current_plan');
}
export function setNavigateTarget(target) { planStore.navigateTarget = target || null; }
