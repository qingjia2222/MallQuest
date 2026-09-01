const TOOL_LABELS = {
  reserve_restaurant: '餐厅预约', reserve_business_space: '商务空间预约',
  cancel_reservation: '取消预约', update_reservation: '修改预约时间/人数',
  claim_coupon: '优惠券领取', buy_ticket: '电影票购买',
  purchase_deal: '限时特惠购买', queue: '店铺排号'
};
const STATUS_LABELS = { success:'成功', already_claimed:'已经领取过', queued:'已排号', failed:'操作失败', unavailable:'暂不可用' };

function actionResultLabel(action) {
  action=action||{};
  if(action.tool==='queue') return `店铺排号：已排号${action.queue_minutes ? `（约${action.queue_minutes}分钟）` : ''}`;
  const label=TOOL_LABELS[action.tool]||action.label||action.tool||action.action||'服务操作';
  return `${label}：${action.reason||STATUS_LABELS[action.status]||action.status||'已完成'}`;
}
function actionResultOk(action) { return ['success','already_claimed','queued'].includes((action||{}).status); }
module.exports={actionResultLabel,actionResultOk};
