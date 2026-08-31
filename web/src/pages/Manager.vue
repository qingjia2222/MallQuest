<script setup>
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import api, { clearAuth } from '../api';
const router=useRouter(),grain=ref('month'),analytics=ref(null),created=ref(null),form=reactive({name:'',category:'零售',floor:1}),err=ref('');
async function load(){try{analytics.value=await api.managerAnalytics(grain.value)}catch(e){err.value=e.message}}
async function createStore(){try{created.value=await api.managerStore({...form,pos_x:680,pos_y:610})}catch(e){err.value=e.message}}
function logout(){clearAuth();router.replace('/login')}
onMounted(load);
</script>

<template>
  <div class="workspace">
    <header>
      <div><small>星河里 · MANAGEMENT</small><h1>经营驾驶舱</h1></div>
      <div class="header-actions">
        <select v-model="grain" @change="load"><option value="day">日度</option><option value="month">月度</option><option value="year">年度</option></select>
        <button @click="logout">退出</button>
      </div>
    </header>
    <p v-if="err" class="err">{{err}}</p>
    <div v-if="analytics" class="kpis">
      <div><span>客流</span><b>{{analytics.current.footfall}}</b></div><div><span>营收</span><b>¥{{analytics.current.revenue}}</b></div>
      <div><span>转化率</span><b>{{analytics.current.conversion_rate}}</b></div><div><span>场内实时人数</span><b>{{analytics.realtime.visitors_in_mall}}</b></div>
    </div>
    <section class="card"><h2>客流趋势</h2><div v-for="item in analytics?.series||[]" :key="item.label" class="bar"><span>{{item.label}}</span><i :style="{width:Math.max(5,item.footfall/Math.max(...analytics.series.map(x=>x.footfall))*100)+'%'}"></i><b>{{item.footfall}}</b></div></section>
    <section class="card store-create"><h2>创建入驻店铺编码</h2><input v-model="form.name" placeholder="店铺名称"/><input v-model="form.category" placeholder="类别"/><input v-model.number="form.floor" type="number"/><button class="primary" @click="createStore">创建店铺与编码</button><strong v-if="created" class="result">{{created.store_code}}</strong></section>
  </div>
</template>

<style scoped>
.workspace{min-height:100%;background:#f4f6fb;padding:28px}header{display:flex;align-items:center;justify-content:space-between;gap:20px;background:linear-gradient(135deg,#172554,#2563eb);color:#fff;border-radius:22px;padding:28px}header h1{margin:7px 0}header small{letter-spacing:2px;color:#bfdbfe}.header-actions{display:flex;align-items:center;gap:10px;flex-shrink:0}.header-actions select,.header-actions button{min-width:92px;padding:10px 15px;border:0;border-radius:20px;margin:0;background:#fff;color:#172554}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}.kpis div{background:#fff;border-radius:16px;padding:20px}.kpis span{display:block;color:#6b7280}.kpis b{display:block;color:#1d4ed8;font-size:25px;margin-top:7px}.card{max-width:none}.bar{display:grid;grid-template-columns:60px 1fr 90px;gap:10px;align-items:center;margin:12px 0}.bar i{display:block;height:12px;background:linear-gradient(90deg,#60a5fa,#2563eb);border-radius:20px}.store-create input{display:block;width:100%;margin:10px 0;padding:11px;border:1px solid #e5e7eb;border-radius:10px}.primary{border:0;border-radius:24px;padding:12px 20px;background:#2563eb;color:#fff}.result{display:block;margin-top:14px;color:#1d4ed8}.err{color:#ef4444}@media(max-width:700px){header{align-items:flex-start}.header-actions{flex-direction:column}.kpis{grid-template-columns:1fr 1fr}}
</style>
