<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api, { setToken, setSession } from '../api';
const router = useRouter();
const role = ref(''); const username = ref('manager'); const phone = ref('11111111111'); const password = ref('123456'); const storeCode = ref('QD-S01-DEMO'); const loading = ref(false); const err = ref('');
function choose(next) { role.value = next; err.value = ''; if (next === 'manager') { username.value = 'manager'; password.value = 'manager123'; } else if (next === 'visitor') password.value = '123456'; }
function back() { role.value = ''; }
async function doLogin() {
  loading.value = true; err.value = '';
  try {
    if (role.value === 'merchant') { const auth = await api.merchantLogin(storeCode.value); setToken(auth.token); setSession(''); localStorage.setItem('mall_role','merchant'); router.replace('/merchant'); return; }
    const auth = role.value === 'manager' ? await api.webLogin(username.value, password.value) : await api.phoneLogin(phone.value, password.value); setToken(auth.token);
    if (role.value === 'manager') { setSession(''); localStorage.setItem('mall_role','manager'); router.replace('/manager'); return; }
    const scan = await api.scan('mall_demo'); setSession(scan.session_id); localStorage.setItem('mall_role','visitor'); localStorage.setItem('mall_name', scan.mall_name || '星河里'); router.replace('/chat');
  } catch (e) { err.value = e.message || '登录失败'; } finally { loading.value = false; }
}
</script>

<template><div class="login"><div class="hero"><div class="brand">星河里 · PRIVATE AI</div><h1>{{ role ? '身份验证' : '选择您的身份' }}</h1><p>{{ role ? '登录后只进入当前角色工作区' : '三类角色，共享一套商场私域数据底座' }}</p></div>
  <div v-if="!role" class="roles"><button @click="choose('visitor')"><b>游客 / 会员</b><span>AI 问答、2.5D 导览、优惠与会员服务</span></button><button @click="choose('merchant')"><b>商户登录</b><span>维护本店营业、排队与优惠</span></button><button @click="choose('manager')"><b>商场管理者</b><span>经营分析、入驻编码与地图管理</span></button></div>
  <div v-else class="card login-card"><button class="back" @click="back">← 返回三方入口</button><h2>{{ role==='visitor'?'游客 / 会员':role==='merchant'?'商户工作区':'管理驾驶舱' }}</h2><template v-if="role==='merchant'"><label>店铺编码</label><input v-model="storeCode" /></template><template v-else-if="role==='visitor'"><label>手机号</label><input v-model="phone" maxlength="11" inputmode="numeric"/><label>密码</label><input v-model="password" type="password"/><small>演示账号：11111111111 / 123456</small></template><template v-else><label>管理账号</label><input v-model="username"/><label>密码</label><input v-model="password" type="password"/></template><p v-if="err" class="err">{{err}}</p><button class="submit" :disabled="loading" @click="doLogin">{{loading?'连接中…':'进入工作区'}}</button></div>
</div></template>

<style scoped>
.login{min-height:100vh;background:#f4f6fb;color:#fff;padding-bottom:48px}.hero{max-width:680px;margin:0 auto;padding:64px 32px 72px;background:linear-gradient(145deg,#331070,#7c3aed);border-radius:0 0 34px 34px;box-sizing:border-box}.brand{font-size:12px;letter-spacing:4px;color:#ddd6fe}.hero h1{font-size:34px;margin:16px 0 8px}.hero p{color:#ede9fe;line-height:1.6}.roles,.login-card{max-width:620px;margin:-38px auto 0;position:relative}.roles{display:grid;gap:12px;padding:0 18px}.roles button{border:0;border-radius:20px;background:#fff;padding:20px;display:grid;grid-template-columns:54px 1fr;column-gap:16px;text-align:left;cursor:pointer;box-shadow:0 12px 32px rgba(49,46,129,.12)}.roles button::before{content:'客';grid-row:1/3;width:54px;height:54px;border-radius:16px;display:grid;place-items:center;background:#ede9fe;color:#7c3aed;font-size:20px;font-weight:800}.roles button:nth-child(2)::before{content:'店';background:#ecfdf5;color:#059669}.roles button:nth-child(3)::before{content:'图';background:#eff6ff;color:#2563eb}.roles b{color:#1f2937;font-size:19px}.roles span{color:#6b7280;margin-top:6px;line-height:1.45}.login-card{color:#1f2937;padding:28px;margin-top:-38px}.back{border:0;background:none;color:#7c3aed;cursor:pointer}.login-card h2{margin:18px 0}.login-card label{display:block;color:#6b7280;font-size:13px;margin-top:12px}.login-card input{width:100%;box-sizing:border-box;margin-top:6px;padding:13px;border:1px solid #e5e7eb;border-radius:12px}.login-card small{display:block;color:#7c3aed;margin-top:10px}.submit{width:100%;margin-top:24px;padding:14px;border:0;border-radius:30px;background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;font-weight:700}.err{color:#ef4444;font-size:13px}
@media(max-width:680px){.hero{padding:52px 26px 68px}.roles,.login-card{margin-left:16px;margin-right:16px}.roles{padding:0}.hero h1{font-size:30px}}
</style>
