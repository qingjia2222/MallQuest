import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import App from './App.vue';
import './theme.css';

import Login from './pages/Login.vue';
import Chat from './pages/Chat.vue';
import Plan from './pages/Plan.vue';
import Map from './pages/Map.vue';
import Coupon from './pages/Coupon.vue';
import Profile from './pages/Profile.vue';
import Reserve from './pages/Reserve.vue';

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/chat', component: Chat, meta: { auth: true, tab: true } },
  { path: '/plan', component: Plan, meta: { auth: true } },
  { path: '/map', component: Map, meta: { auth: true, tab: true } },
  { path: '/coupon', component: Coupon, meta: { auth: true } },
  { path: '/profile', component: Profile, meta: { auth: true, tab: true } },
  { path: '/reserve', component: Reserve, meta: { auth: true } }
];

const router = createRouter({ history: createWebHashHistory(), routes });

// 登录守卫：需要登录的页面校验 localStorage token
router.beforeEach((to) => {
  const authed = !!localStorage.getItem('mall_token');
  if (to.meta.auth && !authed) return '/login';
  if (to.path === '/login' && authed) return '/chat';
  return true;
});

createApp(App).use(router).mount('#app');
