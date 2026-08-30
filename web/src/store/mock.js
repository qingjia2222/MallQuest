// src/store/mock.js - 演示数据（与小程序 app/utils/mock.js 同构）
export const mall = {
  mallId: 'mall-main',
  name: '星河里 · 购物中心',
  slogan: '夜晚不打烊的潮流地标'
};

export const user = {
  id: 'u_10086',
  nickname: '小星',
  points: 2680,
  level: '黄金会员',
  nextLevelPoints: 3000
};

export const stores = [
  { id: 's_01', name: '川渝人家', category: '川菜', floor: 3, pos_x: 12, pos_y: 18, rating: 4.8, waiting: 12, open: true, desc: '地道川味，麻辣鲜香' },
  { id: 's_02', name: '茶颜观色奶茶', category: '饮品', floor: 1, pos_x: 22, pos_y: 9, rating: 4.7, waiting: 5, open: true, desc: '国风现制茶饮' },
  { id: 's_03', name: '星辰影院', category: '影院', floor: 4, pos_x: 30, pos_y: 22, rating: 4.9, waiting: 0, open: true, desc: 'IMAX 激光巨幕' },
  { id: 's_04', name: '甜心甜品', category: '甜品', floor: 2, pos_x: 18, pos_y: 26, rating: 4.6, waiting: 3, open: true, desc: '法式下午茶' },
  { id: 's_05', name: '星巴克', category: '咖啡', floor: 1, pos_x: 8, pos_y: 6, rating: 4.5, waiting: 8, open: true, desc: '经典手冲' },
  { id: 's_06', name: '潮玩星球', category: '潮玩零售', floor: 2, pos_x: 26, pos_y: 15, rating: 4.7, waiting: 0, open: true, desc: '潮玩与盲盒' },
  { id: 's_07', name: '云顶火锅', category: '火锅', floor: 3, pos_x: 6, pos_y: 14, rating: 4.8, waiting: 20, open: true, desc: '川渝麻辣火锅' },
  { id: 's_08', name: '海底捞', category: '火锅', floor: 3, pos_x: 14, pos_y: 10, rating: 4.9, waiting: 15, open: true, desc: '贴心服务' }
];

export const deals = [
  { id: 'deal_1', title: '川渝人家双人餐', original: '238', price: '168', stock: 32, tag: '限时 5 折' },
  { id: 'deal_2', title: '茶颜观色第二杯半价', original: '32', price: '16', stock: 100, tag: '今日特惠' },
  { id: 'deal_3', title: '星辰影院 19:30 场次', original: '88', price: '49', stock: 20, tag: 'IMAX' }
];

export const coupons = [
  { id: 'cp_1', title: '餐饮满 100 减 30', scope: '全场餐饮', expire: '今日 24 点', color: '#7C3AED' },
  { id: 'cp_2', title: '停车 3 小时免费', scope: '商场停车场', expire: '本月内', color: '#06B6D4' },
  { id: 'cp_3', title: '奶茶第二杯半价', scope: '指定饮品', expire: '本周内', color: '#F59E0B' }
];

export const parking = { free: 95, total: 540 };

export const pointsRules = [
  '每消费 1 元累计 1 积分。',
  '黄金会员享受 1.2 倍积分加速。',
  '1000 积分可兑换星巴克中杯券。',
  '积分每年 12 月 31 日清零，请及时兑换。',
  '会员生日当月消费双倍积分。'
];

export const quickActions = ['预约餐厅', '今日特惠', '找奶茶', '停车', '帮我规划约会', '积分'];
