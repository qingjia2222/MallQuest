// src/store/auth.js - 轻量登录态（用 localStorage，接后端换 /api/auth/web-login）
import { reactive } from 'vue';

export const auth = reactive({ user: null });

export function login(user) {
  localStorage.setItem('mall_token', 'demo-token');
  localStorage.setItem('mall_user', JSON.stringify(user));
  Object.assign(auth, { user });
}

export function logout() {
  localStorage.removeItem('mall_token');
  localStorage.removeItem('mall_user');
  auth.user = null;
}
