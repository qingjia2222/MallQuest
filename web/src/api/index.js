// src/api/index.js - 接队友后端(QD square, 8000)的统一 API 层（用原生 fetch，无需额外依赖）
export const BASE = 'http://127.0.0.1:8000';
export let TOKEN = localStorage.getItem('mall_token') || '';
export function setToken(t) { TOKEN = t; if (t) localStorage.setItem('mall_token', t); else localStorage.removeItem('mall_token'); }
export let SESSION_ID = localStorage.getItem('mall_session') || '';
export function setSession(id) { SESSION_ID = id; if (id) localStorage.setItem('mall_session', id); else localStorage.removeItem('mall_session'); }

async function req(method, path, data, tokenOverride) {
  const headers = { 'Content-Type': 'application/json' };
  const activeToken = tokenOverride === undefined ? TOKEN : tokenOverride;
  if (activeToken) headers.Authorization = `Bearer ${activeToken}`;
  const params = method === 'GET' && data ? '?' + new URLSearchParams(data).toString() : '';
  const resp = await fetch(BASE + path + params, {
    method,
    headers,
    body: method !== 'GET' ? JSON.stringify(data) : undefined
  });
  const body = await resp.json();
  if (body && body.code === 0) return body.data;
  throw new Error((body && body.message) || `HTTP ${resp.status}`);
}

export default {
  webLogin: (username, password) => req('POST', '/api/auth/web-login', { username, password }),
  wxLogin: (code) => req('POST', '/api/auth/wx-login', { code }),
  scan: (mall_id = 'mall_demo') => req('POST', '/api/scan', { mall_id, session_id: SESSION_ID || null }),
  chat: (message) => req('POST', '/api/chat', { session_id: SESSION_ID, message }),
  createPlan: (scene, slots = {}) => req('POST', '/api/plan/goal', { session_id: SESSION_ID, scene, slots }),
  getPlan: (plan_id) => req('GET', `/api/plan/${plan_id}`),
  getRoute: (plan_id) => req('GET', '/api/plan/route', { plan_id }),
  confirmPlan: (plan_id, decision, modifications = {}) => req('POST', '/api/plan/confirm', { plan_id, decision, modifications }),
  liveStatus: (plan_id) => req('GET', '/api/plan/live-status', { plan_id }),
  parking: () => req('GET', '/api/parking', { session_id: SESSION_ID }),
  memberPoints: () => req('GET', '/api/member/points', { session_id: SESSION_ID }),
  deals: () => req('GET', '/api/deals', { session_id: SESSION_ID }),
  ticketsProducts: () => req('GET', '/api/tickets/products', { session_id: SESSION_ID }),
  reservations: () => req('GET', '/api/reservations'),
  cancelReservation: (id) => req('DELETE', `/api/reservations/${id}`),
  claimCoupon: (coupon_id, confirmed = true) => req('POST', '/api/coupons/claim', { session_id: SESSION_ID, coupon_id, confirmed }),
  reserve: (payload) => req('POST', '/api/reservations', { session_id: SESSION_ID, confirmed: true, ...payload }),
  merchantLogin: (store_code) => req('POST', '/api/merchant/auth/store-code', { store_code }, ''),
  merchantStore: () => req('GET', '/api/merchant/store'),
  merchantStatus: (payload) => req('PATCH', '/api/merchant/store/status', payload),
  merchantDeal: (payload) => req('PUT', '/api/merchant/store/deals', payload),
  managerAnalytics: (granularity = 'month') => req('GET', '/api/manager/analytics', { mall_id: 'mall_demo', granularity }),
  managerStore: (payload) => req('POST', '/api/manager/stores', { mall_id: 'mall_demo', ...payload }),
  managerMap: (source_name) => req('POST', '/api/manager/maps', { mall_id: 'mall_demo', source_name }),
  mapScene: () => req('GET', '/api/maps/mall_demo/scene'),
  publicStore: (store_id) => req('GET', `/api/stores/${store_id}/public-status`, { mall_id: 'mall_demo' }),
  mapFloorUrl: (floor) => `${BASE}/api/maps/mall_demo/floor_${floor}.svg`
};
