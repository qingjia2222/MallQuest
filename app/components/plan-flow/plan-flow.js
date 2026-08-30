/**
 * plan-flow 组件：全链路规划「理解→采集→生成→确认→执行」进度条。
 * props：step(1-5)，stepNames。
 */
Component({
  properties: {
    step: { type: Number, value: 1 },
    stepNames: {
      type: Array,
      value: ['理解目标', '采集偏好', '生成方案', '确认方案', '执行']
    }
  }
});
