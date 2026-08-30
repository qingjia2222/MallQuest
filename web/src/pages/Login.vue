<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api, { setToken, setSession } from '../api';

const router = useRouter();
const tab = ref('phone');
const username = ref('demo');
const password = ref('demo123');
const loading = ref(false);
const err = ref('');

async function doLogin() {
  loading.value = true; err.value = '';
  try {
    // 1) 登录拿 token（双通道示意：phone/account 都走 web-login，wx 走 wx-login mock）
    let auth;
    if (tab.value === 'wx') auth = await api.wxLogin('mock-demo');
    else auth = await api.webLogin(username.value || 'demo', password.value || 'demo123');
    setToken(auth.token);
    // 2) 扫码建立会话
    const scan = await api.scan('mall_demo');
    setSession(scan.session_id);
    localStorage.setItem('mall_name', scan.mall_name || 'QD square');
    router.replace('/chat');
  } catch (e) {
    err.value = e.message || '登录失败';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login">
    <div class="login-hero">
      <div class="login-logo">🛍️</div>
      <h1 class="login-title">商场 AI 私域服务助手</h1>
      <p class="login-sub">扫码即得一个会替你全链路规划的 AI 助理</p>
    </div>

    <div class="login-card">
      <div class="login-tabs">
        <span :class="{ on: tab === 'phone' }" @click="tab = 'phone'">手机号</span>
        <span :class="{ on: tab === 'account' }" @click="tab = 'account'">账号</span>
        <span :class="{ on: tab === 'wx' }" @click="tab = 'wx'">微信</span>
      </div>

      <template v-if="tab !== 'wx'">
        <label class="label">账号</label>
        <input class="input" v-model="username" placeholder="演示账号 demo" />
        <label class="label">密码</label>
        <input class="input" type="password" v-model="password" placeholder="演示密码 demo123" />
      </template>
      <template v-else>
        <div class="wx-box"><div class="wx-qr">📱</div><p class="wx-tip">使用微信扫码登录<br/><small>（mock 模式，演示用）</small></p></div>
      </template>

      <p v-if="err" class="err">{{ err }}</p>
      <button class="btn login-btn" :disabled="loading" @click="doLogin">{{ loading ? '连接中…' : '登录' }}</button>
      <p class="login-foot">演示账号 demo / demo123</p>
    </div>
  </div>
</template>

<style scoped>
.login { min-height: 100vh; background: linear-gradient(160deg, #1b1530, #312158 60%, #4c3a8c); display: flex; flex-direction: column; align-items: center; padding-top: 90px; }
.login-hero { text-align: center; color: #fff; margin-bottom: 40px; }
.login-logo { font-size: 60px; margin-bottom: 12px; }
.login-title { font-size: 26px; font-weight: 800; }
.login-sub { font-size: 14px; color: rgba(255,255,255,0.72); margin-top: 8px; }
.login-card { width: 86%; max-width: 400px; background: #fff; border-radius: 22px; padding: 28px 26px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.login-tabs { display: flex; gap: 20px; margin-bottom: 22px; border-bottom: 1px solid var(--border); }
.login-tabs span { padding: 8px 2px 12px; color: var(--muted); cursor: pointer; font-size: 15px; }
.login-tabs span.on { color: var(--primary); font-weight: 700; border-bottom: 2px solid var(--primary); }
.label { display: block; font-size: 13px; color: var(--muted); margin: 12px 0 6px; }
.input { width: 100%; background: #F4F6FB; border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; font-size: 16px; }
.input:focus { outline: none; border-color: var(--primary); }
.wx-box { display: flex; align-items: center; gap: 20px; padding: 24px 4px; }
.wx-qr { width: 92px; height: 92px; border: 1px dashed var(--border); border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 44px; }
.wx-tip { font-size: 14px; color: var(--muted); }
.err { color: var(--danger); font-size: 13px; margin-top: 10px; }
.login-btn { width: 100%; margin-top: 24px; }
.login-btn:disabled { opacity: 0.6; }
.login-foot { text-align: center; font-size: 12px; color: #c0c4cc; margin-top: 16px; }
</style>
