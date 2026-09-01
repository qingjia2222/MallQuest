const { request } = require('../../utils/request');

Page({
  data: { username:'', password:'', token:'', loggingIn:false, granularities:['day','month','year'], grainLabels:['日度','月度','年度'], grainIndex:1, analytics:null, analyticsLoading:false, analyticsError:'', storeName:'', storeCategory:'', storeFloor:1, created:null, prompts:[], promptName:'system', promptContent:'', promptRevision:'', promptSaving:false, promptMessage:'' },
  field(e) { this.setData({[e.currentTarget.dataset.key]:e.detail.value}); },
  pickGrain(e) { this.setData({grainIndex:Number(e.detail.value)},()=>this.loadAnalytics()); },
  logout() { this.setData({token:'',analytics:null,password:''}); wx.reLaunch({url:'/pages/portal/portal'}); },
  async login() {
    const username=String(this.data.username||'').trim(),password=String(this.data.password||'');
    if(!username||!password) return wx.showModal({title:'请填写账号和密码',content:'请输入完整的管理账号与密码。演示账号为 manager / manager123。',showCancel:false});
    this.setData({username,loggingIn:true});
    try { const auth=await request('/api/auth/web-login',{method:'POST',token:'',data:{username,password}}); this.setData({token:auth.token}); await Promise.all([this.loadAnalytics(),this.loadPrompts()]); }
    catch(e) { wx.showModal({title:'登录失败',content:e.message,showCancel:false}); }
    finally { this.setData({loggingIn:false}); }
  },
  async loadAnalytics() { this.setData({analyticsLoading:true,analyticsError:''}); try { const analytics=await request(`/api/manager/analytics?mall_id=mall_demo&granularity=${this.data.granularities[this.data.grainIndex]}`,{token:this.data.token}); const max=Math.max(1,...analytics.series.map(item=>item.footfall)); analytics.series=analytics.series.map(item=>({...item,barWidth:Math.round(item.footfall/max*100)})); this.setData({analytics}); } catch(e) { this.setData({analytics:null,analyticsError:`统计数据加载失败：${e.message||''}`}); } finally { this.setData({analyticsLoading:false}); } },
  async createStore() { try { const created=await request('/api/manager/stores',{method:'POST',token:this.data.token,data:{mall_id:'mall_demo',name:this.data.storeName,category:this.data.storeCategory,floor:Number(this.data.storeFloor),pos_x:680,pos_y:610}}); this.setData({created}); wx.showToast({title:'编码已创建'}); } catch(e) { wx.showModal({title:'创建失败',content:e.message,showCancel:false}); } },
  async loadPrompts() {
    const prompts=await request('/api/manager/prompts',{token:this.data.token});
    this.setData({prompts});
    if(prompts.length) await this.selectPromptByName(this.data.promptName||prompts[0].name);
  },
  selectPrompt(e) { this.selectPromptByName(e.currentTarget.dataset.name); },
  async selectPromptByName(name) {
    try { const prompt=await request(`/api/manager/prompts/${name}`,{token:this.data.token}); this.setData({promptName:name,promptContent:prompt.content,promptRevision:prompt.revision,promptMessage:''}); }
    catch(e) { wx.showModal({title:'提示词加载失败',content:e.message,showCancel:false}); }
  },
  async savePrompt() {
    if(this.data.promptSaving)return;this.setData({promptSaving:true,promptMessage:''});
    try { const prompt=await request(`/api/manager/prompts/${this.data.promptName}`,{method:'PUT',token:this.data.token,data:{content:this.data.promptContent,expected_revision:this.data.promptRevision}}); this.setData({promptContent:prompt.content,promptRevision:prompt.revision,promptMessage:'已保存，下次 LLM 请求生效'}); wx.showToast({title:'提示词已保存'}); await this.loadPromptListOnly(); }
    catch(e) { wx.showModal({title:'保存失败',content:e.message,showCancel:false}); }
    finally { this.setData({promptSaving:false}); }
  },
  restorePrompt() {
    if(this.data.promptSaving)return;
    wx.showModal({title:'恢复上一版？',content:'当前内容会先自动备份，恢复后从下一次 LLM 请求开始生效。',success:async res=>{
      if(!res.confirm)return;this.setData({promptSaving:true,promptMessage:''});
      try { const prompt=await request(`/api/manager/prompts/${this.data.promptName}/restore-latest`,{method:'POST',token:this.data.token,data:{expected_revision:this.data.promptRevision}}); this.setData({promptContent:prompt.content,promptRevision:prompt.revision,promptMessage:'已恢复上一版'}); wx.showToast({title:'已恢复上一版'}); await this.loadPromptListOnly(); }
      catch(e) { wx.showModal({title:'恢复失败',content:e.message,showCancel:false}); }
      finally { this.setData({promptSaving:false}); }
    }});
  },
  async loadPromptListOnly(){const prompts=await request('/api/manager/prompts',{token:this.data.token});this.setData({prompts});}
});
