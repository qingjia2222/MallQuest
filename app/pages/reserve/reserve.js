const{request}=require('../../utils/request');Page({data:{result:'等待查询'},async load(){const d=await request('/api/reservations');this.setData({result:JSON.stringify(d,null,2)})}})
