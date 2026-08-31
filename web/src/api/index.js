// src/api/index.js - 接队友后端(QD square, 8000)的统一 API 层（用原生 fetch，无需额外依赖）
// PC uses 127.0.0.1; when the Web page is opened from a phone over LAN, use
// the same host as the page instead of incorrectly calling the phone itself.
export const BASE = import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;
export let TOKEN = '';
export function setToken(t) { TOKEN = t; if (t) localStorage.setItem('mall_token', t); else localStorage.removeItem('mall_token'); }
export let SESSION_ID = '';
export function setSession(id) { SESSION_ID = id; if (id) localStorage.setItem('mall_session', id); else localStorage.removeItem('mall_session'); }
export function clearAuth() {
  setToken('');
  setSession('');
  localStorage.removeItem('mall_role');
  localStorage.removeItem('mall_name');
}

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
  const body = await resp.json().catch(() => ({}));
  if (body && body.code === 0) return body.data;
  throw new Error((body && (body.message || body.detail)) || `HTTP ${resp.status}`);
}

export default {
  webLogin: (username, password) => req('POST', '/api/auth/web-login', { username, password }),
  phoneLogin: (phone, password) => req('POST', '/api/auth/phone-login', { phone, password }),
  wxLogin: (code) => req('POST', '/api/auth/wx-login', { code }),
  merchantLogin: (store_code) => req('POST', '/api/merchant/auth/store-code', { store_code }),
  scan: (mall_id = 'mall_demo') => req('POST', '/api/scan', { mall_id }),
  freshScan: (mall_id = 'mall_demo') => req('POST', '/api/scan', { mall_id }),
  chat: (message) => req('POST', '/api/chat', { session_id: getSession(), message }),
  createPlan: (scene, slots = {}) => req('POST', '/api/plan/goal', { session_id: getSession(), scene, slots }),
  getPlan: (plan_id) => req('GET', `/api/plan/${plan_id}`),
  updatePlan: (plan_id, changes) => req('PATCH', `/api/plan/${plan_id}`, changes),
  editablePlanCopy: (plan = {}) => req('POST', '/api/plan/editable-copy', {
    session_id: getSession(), source_plan_id: plan.plan_id || null, scene: plan.scene || 'date',
    slots: plan.slots || {}, itinerary: plan.itinerary || [],
    vertical_mode: (plan.route && plan.route.vertical_mode) || 'elevator'
  }),
  getRoute: (plan_id) => req('GET', '/api/plan/route', { plan_id }),
  confirmPlan: (plan_id, decision, modifications = {}, expected_revision = null) => req('POST', '/api/plan/confirm', { plan_id, decision, modifications, expected_revision }),
  liveStatus: (plan_id) => req('GET', '/api/plan/live-status', { plan_id }),
  parking: () => req('GET', '/api/parking', { session_id: getSession() }),
  stores: () => req('GET', '/api/stores', { session_id: getSession() }),
  location: () => req('GET', '/api/location'),
  memberPoints: () => req('GET', '/api/member/points', { session_id: getSession() }),
  deals: () => req('GET', '/api/deals', { session_id: getSession() }),
  coupons: () => req('GET', '/api/coupons', { session_id: getSession() }),
  purchaseDeal: (deal_id, quantity = 1) => req('POST', '/api/deals/purchase', { session_id: getSession(), deal_id, quantity, confirmed: true }),
  dealPurchases: () => req('GET', '/api/deals/purchases'),
  memberAssets: () => req('GET', '/api/member/assets'),
  ticketsProducts: () => req('GET', '/api/tickets/products', { session_id: getSession() }),
  reservations: () => req('GET', '/api/reservations'),
  cancelReservation: (id) => req('DELETE', `/api/reservations/${id}`),
  claimCoupon: (coupon_id, confirmed = true) => req('POST', '/api/coupons/claim', { session_id: getSession(), coupon_id, confirmed }),
  reserve: (payload) => req('POST', '/api/reservations', { session_id: getSession(), confirmed: true, ...payload }),
  merchantStore: () => req('GET', '/api/merchant/store'),
  merchantStatus: (payload) => req('PATCH', '/api/merchant/store/status', payload),
  merchantDeal: (payload) => req('PUT', '/api/merchant/store/deals', payload),
  managerAnalytics: (granularity = 'month', mall_id = 'mall_demo') => req('GET', '/api/manager/analytics', { mall_id, granularity }),
  managerStore: (payload) => req('POST', '/api/manager/stores', { mall_id: 'mall_demo', ...payload }),
  mapScene: (mall_id = 'mall_demo') => req('GET', `/api/maps/${mall_id}/scene`),
  mapFloorUrl: (floor) => `${BASE}/api/maps/mall_demo/floor_${floor}.svg`,
  // 确保存在有效会话：缺 session 就重新扫码建一个（登录后调用）
  async ensureSession(force = false) {
    if (!getToken()) throw new Error('未登录，请先登录');
    if (force || !getSession()) {
      const scan = await req('POST', '/api/scan', { mall_id: 'mall_demo' });
      setSession(scan.session_id);
    }
    return getSession();
  }
};
