// src/api/request.js - 网络请求封装（接后端用，当前 demo 模式未调用）
// 【接后端提醒】与小程序 app/utils/request.js 一致：/api/chat、/api/plan/date、
// /api/plan/route、/api/plan/confirm、/api/plan/live-status(SSE)、/api/parking、
// /api/member/points、/api/coupons/claim、/api/reservations

const BASE_URL = 'http://127.0.0.1:8200/api';

export async function request(path, { method = 'GET', data = {}, header = {} } = {}) {
  const token = localStorage.getItem('mall_token');
  const res = await fetch(BASE_URL + path, {
    method,
    headers: {
      'content-type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...header
    },
    body: method !== 'GET' ? JSON.stringify(data) : undefined
  });
  const body = await res.json();
  if (body.code === 0) return body.data;
  throw new Error(body.message || '请求失败');
}

export { BASE_URL };
