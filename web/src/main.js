import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import App from './App.vue';
import './theme.css';

import Login from './pages/Login.vue';
import Home from './pages/Home.vue';
import Chat from './pages/Chat.vue';
import Map from './pages/Map.vue';
import Coupon from './pages/Coupon.vue';
import Profile from './pages/Profile.vue';
import Reserve from './pages/Reserve.vue';
import Merchant from './pages/Merchant.vue';
import Manager from './pages/Manager.vue';
import { restoreAuth } from './api';

restoreAuth(); // 刷新后从 localStorage 恢复 token/session

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/home', component: Home, meta: { auth: true, role: 'visitor', tab: true } },
  { path: '/chat', component: Chat, meta: { auth: true, role: 'visitor', tab: true } },
  { path: '/map', component: Map, meta: { auth: true, role: 'visitor', tab: true } },
  { path: '/coupon', component: Coupon, meta: { auth: true, role: 'visitor' } },
  { path: '/profile', component: Profile, meta: { auth: true, role: 'visitor', tab: true } },
  { path: '/reserve', component: Reserve, meta: { auth: true, role: 'visitor' } },
  { path: '/merchant', component: Merchant, meta: { auth: true, role: 'merchant', standalone: true } },
  { path: '/manager', component: Manager, meta: { auth: true, role: 'manager', standalone: true } }
];

const router = createRouter({ history: createWebHashHistory(), routes });

// 登录守卫：需要登录的页面校验 localStorage token
router.beforeEach((to) => {
  const authed = !!localStorage.getItem('mall_token');
  const role = localStorage.getItem('mall_role') || 'visitor';
  const roleHome = role === 'manager' ? '/manager' : role === 'merchant' ? '/merchant' : '/home';
  if (to.meta.auth && !authed) return '/login';
  if (to.path === '/login' && authed) return roleHome;
  if (to.meta.role && to.meta.role !== role) return roleHome;
  return true;
});

// —— 全局错误捕获：把「空白页」背后的真实错误显示到页面顶部红条 ——
function showError(msg, extra = '') {
  let el = document.getElementById('app-error');
  if (!el) {
    el = document.createElement('div');
    el.id = 'app-error';
    el.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;background:#dc2626;color:#fff;padding:10px 16px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-all;';
    document.body.appendChild(el);
  }
  el.textContent = '⚠ 页面错误：' + msg + (extra ? '  [' + extra + ']' : '');
}

const app = createApp(App);
app.config.errorHandler = (err, _inst, info) => { showError((err && err.message) || String(err), info); };
window.addEventListener('error', (e) => showError(e.message || '脚本错误', (e.filename || '') + ':' + (e.lineno || '')));
window.addEventListener('unhandledrejection', (e) => showError('Promise: ' + ((e.reason && e.reason.message) || e.reason), ''));

app.use(router).mount('#app');
