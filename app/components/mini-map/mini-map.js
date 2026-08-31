/**
 * mini-map 组件：2.5D 室内地图 + 路线连线。
 * props：stores(店铺数组), route(路线节点 id 序列), activeId
 * events：storetap
 * 用相对坐标(0-100%)绘制店铺节点与 L 型连线，低配兼容不用 canvas。
 */
Component({
  properties: {
    stores: { type: Array, value: [] },
    route: { type: Array, value: [] },   // store id 序列
    activeId: { type: String, value: '' },
    floor: { type: Number, value: 1 }
  },
  data: {
    floorCount: 2,
    segs: []
  },
  observers: {
    'stores,route'(stores, route) {
      const byId = {};
      (stores || []).forEach(s => { byId[s.id] = s; });
      const segs = [];
      (route || []).forEach((id, i) => {
        if (i < route.length - 1 && byId[id] && byId[route[i + 1]]) {
          const a = byId[id], b = byId[route[i + 1]];
          // 横向段（宽=Δx，厚=0.7）
          segs.push({ x: Math.min(a.pos_x, b.pos_x), y: Math.min(a.pos_y, b.pos_y), w: Math.max(Math.abs(a.pos_x - b.pos_x), 0), h: 0.7 });
          // 纵向段（高=Δy，宽=0.7）
          segs.push({ x: a.pos_x, y: Math.min(a.pos_y, b.pos_y), w: 0.7, h: Math.abs(a.pos_y - b.pos_y) });
        }
      });
      this.setData({ segs });
    }
  },
  methods: {
    onStoreTap(e) {
      this.triggerEvent('storetap', { store: e.currentTarget.dataset.store });
    },
    setFloor(e) {
      this.setData({ floor: Number(e.currentTarget.dataset.f) });
    }
  }
});
