// src/api/index.js - 接队友后端(QD square, 8000)的统一 API 层（用原生 fetch，无需额外依赖）
export const BASE = 'http://127.0.0.1:8000';
export let TOKEN = '';
export function setToken(t) { TOKEN = t; if (t) localStorage.setItem('mall_token', t); else localStorage.removeItem('mall_token'); }
export let SESSION_ID = '';
export function setSession(id) { SESSION_ID = id; if (id) localStorage.setItem('mall_session', id); }

// 从内存/localStorage 兜底取 token 和 session（刷新后内存清空也能用）
function getToken() { return TOKEN || localStorage.getItem('mall_token') || ''; }
function getSession() { return SESSION_ID || localStorage.getItem('mall_session') || ''; }
// 登录态恢复：页面刷新时调用，从 localStorage 还原内存变量
export function restoreAuth() {
  TOKEN = localStorage.getItem('mall_token') || '';
  SESSION_ID = localStorage.getItem('mall_session') || '';
}

async function req(method, path, data) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
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
  scan: (mall_id = 'mall_demo') => req('POST', '/api/scan', { mall_id }),
  freshScan: (mall_id = 'mall_demo') => req('POST', '/api/scan', { mall_id }),
  chat: (message) => req('POST', '/api/chat', { session_id: getSession(), message }),
  createPlan: (scene, slots = {}) => req('POST', '/api/plan/goal', { session_id: getSession(), scene, slots }),
  getPlan: (plan_id) => req('GET', `/api/plan/${plan_id}`),
  getRoute: (plan_id) => req('GET', '/api/plan/route', { plan_id }),
  confirmPlan: (plan_id, decision, modifications = {}) => req('POST', '/api/plan/confirm', { plan_id, decision, modifications }),
  liveStatus: (plan_id) => req('GET', '/api/plan/live-status', { plan_id }),
  parking: () => req('GET', '/api/parking', { session_id: getSession() }),
  stores: () => req('GET', '/api/stores', { session_id: getSession() }),
  location: () => req('GET', '/api/location'),
  memberPoints: () => req('GET', '/api/member/points', { session_id: getSession() }),
  deals: () => req('GET', '/api/deals', { session_id: getSession() }),
  ticketsProducts: () => req('GET', '/api/tickets/products', { session_id: getSession() }),
  reservations: () => req('GET', '/api/reservations'),
  claimCoupon: (coupon_id, confirmed = true) => req('POST', '/api/coupons/claim', { session_id: getSession(), coupon_id, confirmed }),
  reserve: (payload) => req('POST', '/api/reservations', { session_id: getSession(), confirmed: true, ...payload }),
  mapFloorUrl: (floor) => `${BASE}/api/maps/mall_demo/floor_${floor}.svg`,
  // 确保存在有效会话：缺 session 就重新扫码建一个（登录后调用）
  async ensureSession() {
    if (!getToken()) throw new Error('未登录，请先登录');
    if (!getSession()) {
      const scan = await req('POST', '/api/scan', { mall_id: 'mall_demo' });
      setSession(scan.session_id);
    }
    return getSession();
  }
};
