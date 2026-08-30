// src/store/plan.js - 共享当前规划方案（Chat 生成 → Map/Result 消费）
import { reactive } from 'vue';
export const planStore = reactive({ current: null });

export function setCurrentPlan(p) { planStore.current = p; }
