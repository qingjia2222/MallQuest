<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api, { setToken, setSession } from '../api';
const router = useRouter();
const role = ref(''); const username = ref('demo'); const password = ref('demo123'); const storeCode = ref('QD-S01-DEMO'); const loading = ref(false); const err = ref('');
function choose(next) { role.value = next; err.value = ''; if (next === 'manager') { username.value = 'manager'; password.value = 'manager123'; } }
function back() { role.value = ''; }
async function doLogin() {
  loading.value = true; err.value = '';
  try {
    if (role.value === 'merchant') { const auth = await api.merchantLogin(storeCode.value); setToken(auth.token); setSession(''); localStorage.setItem('mall_role','merchant'); router.replace('/merchant'); return; }
    const auth = await api.webLogin(username.value, password.value); setToken(auth.token);
    if (role.value === 'manager') { setSession(''); localStorage.setItem('mall_role','manager'); router.replace('/manager'); return; }
    const scan = await api.scan('mall_demo'); setSession(scan.session_id); localStorage.setItem('mall_role','visitor'); localStorage.setItem('mall_name', scan.mall_name || 'QD square'); router.replace('/chat');
  } catch (e) { err.value = e.message || '登录失败'; } finally { loading.value = false; }
}
</script>

<template><div class="login"><div class="hero"><div class="brand">QD SQUARE · PRIVATE AI</div><h1>{{ role ? '身份验证' : '选择您的身份' }}</h1><p>{{ role ? '登录后只进入当前角色工作区' : '三类角色，共享一套商场私域数据底座' }}</p></div>
  <div v-if="!role" class="roles"><button @click="choose('visitor')"><b>游客 / 会员</b><span>AI 问答、2.5D 导览、优惠与会员服务</span></button><button @click="choose('merchant')"><b>商户登录</b><span>维护本店营业、排队与优惠</span></button><button @click="choose('manager')"><b>商场管理者</b><span>经营分析、入驻编码与地图管理</span></button></div>
  <div v-else class="card login-card"><button class="back" @click="back">← 返回三方入口</button><h2>{{ role==='visitor'?'游客 / 会员':role==='merchant'?'商户工作区':'管理驾驶舱' }}</h2><template v-if="role==='merchant'"><label>店铺编码</label><input v-model="storeCode" /></template><template v-else><label>账号</label><input v-model="username"/><label>密码</label><input v-model="password" type="password"/></template><p v-if="err" class="err">{{err}}</p><button class="submit" :disabled="loading" @click="doLogin">{{loading?'连接中…':'进入工作区'}}</button></div>
</div></template>

<style scoped>.login{min-height:100vh;background:linear-gradient(160deg,#1b1530,#312158 60%,#4c3a8c);padding:64px 24px;color:#fff}.hero{max-width:620px;margin:0 auto 30px}.brand{font-size:12px;letter-spacing:4px;color:#c4b5fd}.hero h1{font-size:34px;margin:14px 0 6px}.hero p{color:#ddd6fe}.roles,.login-card{max-width:620px;margin:auto}.roles{display:grid;gap:14px}.roles button{border:0;border-radius:20px;background:#fff;padding:24px;text-align:left;cursor:pointer;box-shadow:0 18px 50px rgba(0,0,0,.18)}.roles b{display:block;color:#1f2937;font-size:20px}.roles span{display:block;color:#6b7280;margin-top:7px}.login-card{color:#1f2937;padding:28px}.back{border:0;background:none;color:#7c3aed;cursor:pointer}.login-card h2{margin:18px 0}.login-card label{display:block;color:#6b7280;font-size:13px;margin-top:12px}.login-card input{width:100%;margin-top:6px;padding:13px;border:1px solid #e5e7eb;border-radius:12px}.submit{width:100%;margin-top:24px;padding:14px;border:0;border-radius:30px;background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;font-weight:700}.err{color:#ef4444;font-size:13px}</style>
