Page({
  onLoad(options) {
    if (options && options.scene) getApp().globalData.serviceCode = decodeURIComponent(options.scene).trim().toUpperCase();
  },
  visitor(){wx.reLaunch({url:'/pages/scan/scan'})},
  merchant(){wx.reLaunch({url:'/pages/merchant/merchant'})},
  manager(){wx.reLaunch({url:'/pages/manager/manager'})}
})
