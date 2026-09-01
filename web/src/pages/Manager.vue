<script setup>
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import api, { clearAuth } from '../api';
const router=useRouter(),grain=ref('month'),analytics=ref(null),analyticsLoading=ref(false),created=ref(null),form=reactive({name:'',category:'零售',floor:1}),err=ref('');
const prompts=ref([]),promptName=ref('system'),promptContent=ref(''),promptRevision=ref(''),promptSaving=ref(false),promptMessage=ref('');
async function load(){analyticsLoading.value=true;err.value='';try{analytics.value=await api.managerAnalytics(grain.value)}catch(e){analytics.value=null;err.value='统计数据加载失败：'+e.message}finally{analyticsLoading.value=false}}
async function createStore(){try{created.value=await api.managerStore({...form,pos_x:680,pos_y:610})}catch(e){err.value=e.message}}
async function loadPrompts(){try{prompts.value=await api.managerPrompts();await selectPrompt(promptName.value)}catch(e){err.value=e.message}}
async function selectPrompt(name){try{promptName.value=name;promptMessage.value='';const item=await api.managerPrompt(name);promptContent.value=item.content;promptRevision.value=item.revision}catch(e){err.value=e.message}}
async function savePrompt(){if(promptSaving.value)return;promptSaving.value=true;promptMessage.value='';try{const item=await api.updateManagerPrompt(promptName.value,promptContent.value,promptRevision.value);promptContent.value=item.content;promptRevision.value=item.revision;promptMessage.value='已保存，下一次 LLM 请求生效';prompts.value=await api.managerPrompts()}catch(e){err.value=e.message}finally{promptSaving.value=false}}
async function restorePrompt(){if(promptSaving.value)return;promptSaving.value=true;promptMessage.value='';try{const item=await api.restoreManagerPrompt(promptName.value,promptRevision.value);promptContent.value=item.content;promptRevision.value=item.revision;promptMessage.value='已恢复上一版，下一次 LLM 请求生效';prompts.value=await api.managerPrompts()}catch(e){err.value=e.message}finally{promptSaving.value=false}}
function logout(){clearAuth();router.replace('/login')}
onMounted(()=>{load();loadPrompts()});
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
    <p v-if="analyticsLoading" class="period-note">正在切换统计周期…</p>
    <p v-else-if="analytics" class="period-note"><b>{{analytics.granularity_label}}数据</b> · {{analytics.period_range}} · 当前 {{analytics.current_label}}</p>
    <div v-if="analytics" class="kpis">
      <div><span>客流</span><b>{{analytics.current.footfall}}</b></div><div><span>营收</span><b>¥{{analytics.current.revenue}}</b></div>
      <div><span>转化率</span><b>{{analytics.current.conversion_rate}}</b></div><div><span>场内实时人数</span><b>{{analytics.realtime.visitors_in_mall}}</b></div>
    </div>
    <section class="card"><h2>{{analytics?.granularity_label || ''}}客流趋势</h2><div v-for="item in analytics?.series||[]" :key="item.label" class="bar"><span>{{item.label}}</span><i :style="{width:Math.max(5,item.footfall/Math.max(...analytics.series.map(x=>x.footfall))*100)+'%'}"></i><b>{{item.footfall}}</b></div></section>
    <section v-if="analytics" class="card"><h2>实时监测（不随统计周期变化）</h2><div class="realtime-web"><div><b>{{analytics.realtime.visitors_in_mall}}</b><span>场内人数</span></div><div><b>{{analytics.realtime.entrances_per_minute}}</b><span>每分钟入场</span></div><div><b>{{analytics.realtime.occupancy_level}}</b><span>拥挤程度</span></div></div></section>
    <section class="card store-create"><h2>创建入驻店铺编码</h2><input v-model="form.name" placeholder="店铺名称"/><input v-model="form.category" placeholder="类别"/><input v-model.number="form.floor" type="number"/><button class="primary" @click="createStore">创建店铺与编码</button><strong v-if="created" class="result">{{created.store_code}}</strong></section>
    <section class="card prompt-admin">
      <div class="prompt-head"><div><h2>系统提示词维护</h2><p>独立目录、版本校验、保存前自动备份；不影响 SQLite 业务数据。</p></div><div class="prompt-actions"><button :disabled="promptSaving" @click="restorePrompt">恢复上一版</button><button class="primary" :disabled="promptSaving" @click="savePrompt">{{promptSaving?'处理中…':'保存提示词'}}</button></div></div>
      <div class="prompt-tabs"><button v-for="item in prompts" :key="item.name" :class="{active:item.name===promptName}" @click="selectPrompt(item.name)">{{item.title}}</button></div>
      <textarea v-model="promptContent" spellcheck="false" aria-label="系统提示词内容"></textarea>
      <div class="prompt-foot"><span>当前版本 {{promptRevision}}</span><strong v-if="promptMessage">{{promptMessage}}</strong></div>
    </section>
  </div>
</template>

<style scoped>
.workspace{min-height:100%;background:#f4f6fb;padding:28px}header{display:flex;align-items:center;justify-content:space-between;gap:20px;background:linear-gradient(135deg,#172554,#2563eb);color:#fff;border-radius:22px;padding:28px}header h1{margin:7px 0}header small{letter-spacing:2px;color:#bfdbfe}.header-actions{display:flex;align-items:center;gap:10px;flex-shrink:0}.header-actions select,.header-actions button{min-width:92px;padding:10px 15px;border:0;border-radius:20px;margin:0;background:#fff;color:#172554}.period-note{margin:16px 0 0;padding:11px 15px;border-radius:12px;background:#eff6ff;color:#475569}.period-note b{color:#1d4ed8}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}.kpis div{background:#fff;border-radius:16px;padding:20px}.kpis span{display:block;color:#6b7280}.kpis b{display:block;color:#1d4ed8;font-size:25px;margin-top:7px}.card{max-width:none}.bar{display:grid;grid-template-columns:60px 1fr 90px;gap:10px;align-items:center;margin:12px 0}.bar i{display:block;height:12px;background:linear-gradient(90deg,#60a5fa,#2563eb);border-radius:20px}.realtime-web{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.realtime-web div{display:flex;flex-direction:column;gap:6px;text-align:center;padding:14px;background:#f8fafc;border-radius:14px}.realtime-web b{font-size:24px;color:#1d4ed8}.realtime-web span{color:#6b7280}.store-create input{display:block;width:100%;margin:10px 0;padding:11px;border:1px solid #e5e7eb;border-radius:10px}.primary{border:0;border-radius:24px;padding:12px 20px;background:#2563eb;color:#fff}.result{display:block;margin-top:14px;color:#1d4ed8}.err{color:#ef4444}@media(max-width:700px){header{align-items:flex-start}.header-actions{flex-direction:column}.kpis{grid-template-columns:1fr 1fr}}
.prompt-head{display:flex;align-items:center;justify-content:space-between;gap:20px}.prompt-head h2{margin-bottom:5px}.prompt-head p{margin:0;color:#6b7280}.prompt-actions{display:flex;gap:8px}.prompt-actions button{border:1px solid #dbe3f0;background:#fff;color:#1d4ed8;border-radius:22px;padding:11px 18px;white-space:nowrap}.prompt-actions .primary{border:0;background:#2563eb;color:#fff}.prompt-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 12px}.prompt-tabs button{border:1px solid #dbe3f0;background:#fff;color:#475569;border-radius:18px;padding:8px 14px}.prompt-tabs button.active{background:#1d4ed8;color:#fff;border-color:#1d4ed8}.prompt-admin textarea{box-sizing:border-box;width:100%;min-height:360px;resize:vertical;border:1px solid #dbe3f0;border-radius:12px;padding:15px;font:13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;color:#172554;background:#f8fafc}.prompt-foot{display:flex;justify-content:space-between;gap:15px;margin-top:10px;color:#64748b;font-size:13px}.prompt-foot strong{color:#059669}@media(max-width:700px){.prompt-head{align-items:flex-start;flex-direction:column}.prompt-actions{width:100%}.prompt-actions button{flex:1}.prompt-admin textarea{min-height:300px}}
</style>
