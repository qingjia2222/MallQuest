// pages/plan/plan.js - 甲方 PlanFlow/行程卡 + 乙方 Planner 状态机
const { request } = require('../../utils/request');
const { actionResultLabel, actionResultOk } = require('../../utils/action-result');

function clockMinutes(value) {
  const match=String(value||'').match(/(\d{1,2})(?::|点)(\d{1,2})?/);
  if(!match)return null;
  let hour=Number(match[1]);
  if(/下午|晚上|晚/.test(String(value))&&hour<12)hour+=12;
  return hour*60+Number(match[2]||0);
}
function calendarRange(plan) {
  const itinerary=(plan&&plan.itinerary)||[];
  const values=itinerary.map(item=>clockMinutes(item.time_label)).filter(item=>item!==null);
  const fallback=clockMinutes(plan&&plan.slots&&plan.slots.time);
  const startMinutes=values.length?values[0]:(fallback===null?19*60:fallback);
  let endMinutes=values.length?values[values.length-1]+60:startMinutes+60;
  if(endMinutes<=startMinutes)endMinutes+=24*60;
  const base=new Date();base.setHours(0,0,0,0);
  let start=base.getTime()+startMinutes*60000;
  if(start<Date.now()+60000)start+=24*60*60000;
  const end=start+(endMinutes-startMinutes)*60000;
  return {startTime:Math.floor(start/1000),endTime:Math.floor(end/1000)};
}
Page({
  data: { step: 1, goalText: '我今天约会', form: {}, questions: [], qIndex: 0, currentQ: {}, options: [], itinerary: {}, generating: false, executing: false, editing: false, editSaving: false, addingReminder:false, availableStores:[], addableStores:[], addStoreIndex:0, plan: null },
  async onLoad() {
    const existing = getApp().globalData.currentPlan || (getApp().globalData.planState && getApp().globalData.planState.current);
    if (existing) {
      try {
        const fresh=await request(`/api/plan/${existing.plan_id}`); getApp().globalData.currentPlan=fresh; getApp().setPlanState({current:fresh}); this.present(fresh,fresh.state==='DONE'?5:4);
      } catch(e) {
        if(/plan not found|not found/i.test(e.message||'')) {
          try { const restored=await this.copyForEdit(existing); this.present(restored,4); }
          catch(copyError) {
            if(!/invalid store|not found/i.test(copyError.message||'')) throw copyError;
            getApp().globalData.currentPlan=null; getApp().setPlanState({current:null});
            const goalText=wx.getStorageSync('planGoal')||'我今天约会'; this.setData({goalText,plan:null,itinerary:{}}); this.startUnderstand();
          }
        }
        else { this.present(existing,existing.state==='DONE'?5:4); wx.showToast({title:e.message||'方案校验失败',icon:'none'}); }
      }
      return;
    }
    const goalText = wx.getStorageSync('planGoal') || '我今天约会'; this.setData({ goalText }); this.startUnderstand();
  },
  startUnderstand() {
    const questions = [
      { key: 'time', label: '大概打算几点开始？', options: ['19:00', '19:30', '20:00'] },
      { key: 'people', label: '一共几个人？', options: ['2人', '3人', '4人'] },
      { key: 'budget', label: '人均预算大概多少？', options: ['150', '250', '350'] },
      { key: 'taste', label: '偏好什么口味？', options: ['川菜', '日料', '西餐'] }
    ];
    this.setData({ questions, currentQ: questions[0], options: questions[0].options, step: 2 });
  },
  pickOption(e) {
    const val = e.currentTarget.dataset.val, q = this.data.currentQ, form = { ...this.data.form, [q.key]: val }, next = this.data.qIndex + 1;
    if (next < this.data.questions.length) this.setData({ form, qIndex: next, currentQ: this.data.questions[next], options: this.data.questions[next].options });
    else { this.setData({ form }); this.generatePlan(form); }
  },
  async generatePlan(form) {
    this.setData({ step: 3, generating: true });
    try {
      const app = getApp(); await app.ensureSession();
      const plan = await request('/api/plan/goal', { method: 'POST', data: { session_id: app.globalData.sessionId, text: this.data.goalText, scene: 'date', slots: { time: form.time || '19:00', people: Number(String(form.people || '2').replace('人','')), budget_per_person: Number(form.budget || 250), cuisine: form.taste || '川菜', want_movie: true } } });
      app.globalData.currentPlan = plan; app.setPlanState({ current: plan }); this.present(plan, 4);
    } catch (e) { wx.showModal({ title: '规划失败', content: e.message, showCancel: false }); this.setData({ step: 2 }); }
    finally { this.setData({ generating: false }); }
  },
  present(plan, step) {
    const time = (plan.slots && plan.slots.time) || '19:00';
    const stops = (plan.itinerary || []).map((s, index) => ({ ...s, time: s.time_label || (index ? `第 ${index + 1} 站` : time), time_label: s.time_label || '', waiting: s.queue_minutes || 0 }));
    const actions = (plan.action_results || []).map(a => ({ label: actionResultLabel(a), ok: actionResultOk(a) }));
    this.setData({ plan, step, editing: false, itinerary: { tag: plan.state === 'DONE' ? '已执行' : '等待确认', stops, actions } });
  },
  onChangePlan() { this.generatePlan(this.data.form); },
  async copyForEdit(plan) {
    const app=getApp(); await app.ensureSession();
    const payload=()=>({session_id:app.globalData.sessionId,source_plan_id:plan.plan_id||null,scene:plan.scene||'date',slots:plan.slots||{},itinerary:plan.itinerary||[],vertical_mode:plan.route&&plan.route.vertical_mode||'elevator'});
    let copied;
    try { copied=await request('/api/plan/editable-copy',{method:'POST',data:payload()}); }
    catch(e) { if(!/session not found|not found/i.test(e.message||''))throw e; app.globalData.sessionId='';await app.ensureSession();copied=await request('/api/plan/editable-copy',{method:'POST',data:payload()}); }
    app.globalData.currentPlan=copied;app.setPlanState({current:copied});return copied;
  },
  async editExecutedPlan() {
    try { const copied=await this.copyForEdit(this.data.plan); this.present(copied,4); wx.showToast({title:'已复制为可编辑方案'}); }
    catch(e){wx.showModal({title:'恢复编辑失败',content:e.message||'',showCancel:false});}
  },
  editStopTime(e) { this.setData({ [`plan.itinerary[${e.currentTarget.dataset.index}].time_label`]: e.detail.value }); },
  moveStop(e) { const index=Number(e.currentTarget.dataset.index),delta=Number(e.currentTarget.dataset.delta),next=index+delta,list=[...(this.data.plan.itinerary||[])]; if(next<0||next>=list.length)return; const tmp=list[index];list[index]=list[next];list[next]=tmp;this.setData({'plan.itinerary':list}); },
  refreshAddableStores(itinerary) { const ids=new Set((itinerary||[]).map(item=>item.id));const addableStores=(this.data.availableStores||[]).filter(item=>!ids.has(item.id)&&item.open_status!=='closed');this.setData({addableStores,addStoreIndex:0}); },
  async startEdit() {
    if(this.data.step!==4)return;this.setData({editing:true});
    try { const app=getApp();await app.ensureSession();const availableStores=await request(`/api/stores?session_id=${app.globalData.sessionId}`);this.setData({availableStores});this.refreshAddableStores(this.data.plan.itinerary||[]); }
    catch(e){wx.showToast({title:`店铺列表加载失败：${e.message||''}`,icon:'none'});}
  },
  pickAddStore(e) { this.setData({addStoreIndex:Number(e.detail.value)}); },
  addSelectedStore() { const store=this.data.addableStores[this.data.addStoreIndex];if(!store)return;const list=[...(this.data.plan.itinerary||[]),{...store,time_label:''}];this.setData({'plan.itinerary':list});this.refreshAddableStores(list); },
  removeStop(e) { const index=Number(e.currentTarget.dataset.index),list=[...(this.data.plan.itinerary||[])];if(list.length<=1){wx.showToast({title:'方案至少保留一个地点',icon:'none'});return;}list.splice(index,1);this.setData({'plan.itinerary':list});this.refreshAddableStores(list); },
  cancelEdit() { this.present(this.data.plan, 4); },
  async savePlan() {
    if (!this.data.plan || !this.data.plan.plan_id) return;
    this.setData({editSaving:true});
    try { const plan=await request(`/api/plan/${this.data.plan.plan_id}`,{method:'PATCH',data:{itinerary:this.data.plan.itinerary.map(s=>({id:s.id,time_label:s.time_label||''})),expected_revision:this.data.plan.revision}}); getApp().globalData.currentPlan=plan; getApp().setPlanState({current:plan}); this.present(plan,4); wx.showToast({title:'方案已同步'}); }
    catch(e){wx.showToast({title:e.message,icon:'none'})}
    finally{this.setData({editSaving:false})}
  },
  async onConfirm() {
    if (!this.data.plan || this.data.plan.state !== 'CONFIRM') return;
    this.setData({ executing: true });
    try { const plan = await request('/api/plan/confirm', { method: 'POST', data: { plan_id: this.data.plan.plan_id, decision: 'confirm', expected_revision: this.data.plan.revision } }); getApp().globalData.currentPlan = plan; getApp().setPlanState({ current: plan }); this.present(plan, 5); wx.showToast({ title: '规划已执行' }); }
    catch (e) { wx.showModal({ title: '执行失败', content: e.message, showCancel: false }); }
    finally { this.setData({ executing: false }); }
  },
  onStopTap(e) { const name = e.detail && e.detail.stop ? e.detail.stop.name : ''; wx.navigateTo({ url: '/pages/map/map?focus=' + name }); },
  addCalendarReminder() {
    if(this.data.addingReminder)return;
    if(typeof wx.addPhoneCalendar!=='function') { wx.showModal({title:'当前微信版本不支持',content:'请升级微信后再添加手机日历提醒。',showCancel:false});return; }
    const plan=this.data.plan||{},range=calendarRange(plan),names=(plan.itinerary||[]).map(item=>item.name).filter(Boolean);
    this.setData({addingReminder:true});
    wx.addPhoneCalendar({
      title:`星河里${this.data.goalText||'行程'}提醒`,startTime:range.startTime,endTime:range.endTime,
      description:names.length?`行程：${names.join(' → ')}`:'星河里购物中心行程',location:'星河里购物中心',alarm:true,alarmOffset:15*60,
      success:()=>wx.showToast({title:'已添加到手机日历',icon:'success'}),
      fail:(error)=>{const denied=/auth deny|authorize|permission/i.test((error&&error.errMsg)||'');wx.showModal({title:'添加提醒失败',content:denied?'请在小程序设置中允许“添加到日历”后重试。':'手机系统未能写入日历，请检查系统日历权限后重试。',confirmText:denied?'去设置':'知道了',showCancel:denied,success:res=>{if(denied&&res.confirm)wx.openSetting({});}});},
      complete:()=>this.setData({addingReminder:false})
    });
  },
  goMap() { wx.switchTab({ url: '/pages/map/map' }); },
  goChat() { wx.switchTab({ url: '/pages/chat/chat' }); }
});
