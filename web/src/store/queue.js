// 全局「到号提醒」：确认方案后跨页面持续轮询实时排队，某店排队归零 → 顶部横幅提示
// 放在组件之外（App.vue 挂载），这样确认后跳到地图页也能继续提醒，不会因 Chat 卸载而失效。
import { reactive } from 'vue';
import api from '../api';

export const queueState = reactive({
  notices: [],      // 待展示的到号提醒 [{id, text}]
  planId: null,
  storeName: {},
  prev: {},         // 每家店上一次的 queue_minutes
  notified: {},     // 已提醒的店，避免重复
});

let timer = null;

export function startQueueWatch(planId, itinerary) {
  stopQueueWatch();
  if (!planId) return;
  const names = {};
  (itinerary || []).forEach(s => { if (s && s.id) names[s.id] = s.name || s.title || ''; });
  queueState.planId = planId;
  queueState.storeName = names;
  queueState.prev = {};
  queueState.notified = {};
  tick();
  timer = setInterval(tick, 6000);
}

export function stopQueueWatch() {
  if (timer) { clearInterval(timer); timer = null; }
  queueState.planId = null;
}

export function clearNotices() { queueState.notices = []; }

async function tick() {
  const pid = queueState.planId;
  if (!pid) return;
  try {
    const data = await api.liveStatus(pid);
    const list = (data && data.status) || [];
    for (const s of list) {
      const sid = s.store_id; if (!sid) continue;
      const q = Number(s.queue_minutes ?? 0);
      const prev = queueState.prev[sid];
      if (prev !== undefined && prev > 0 && q === 0 && !queueState.notified[sid]) {
        queueState.notified[sid] = true;
        const name = queueState.storeName[sid] || sid;
        queueState.notices.push({ id: sid + '_' + Date.now(), text: `🔔 ${name} 排队已到号，请前往（等待结束）。` });
        if (navigator.vibrate) navigator.vibrate([80, 60, 80]);
      }
      queueState.prev[sid] = q;
    }
  } catch (e) {}
}
