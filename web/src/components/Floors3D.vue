<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import ringPlan from '../store/mall_ring.json';
import storeInfo from '../store/store_info.json';

// 取店铺详情(分类/简介/标签)，找不到给默认
function infoOf(name) {
  return storeInfo[name] || { category: '零售', desc: '品类丰富的优质店铺，值得一逛', tags: ['购物', '零售'] };
}

// 3D 楼层导览（three.js r128，本地引入）—— 回字形布局 + 四角 L 形转角店
const props = defineProps({ route: { type: Object, default: null } });
const emit = defineEmits(['select', 'floorschanged']);

const el = ref(null);
const floors = ['F1', 'F2'];
const curFloor = ref('all');       // 'all' | 'F1' | 'F2'

let scene, camera, renderer, controls;
let raf;
let storeMeshes = [];
let routeLines = [];
let floorGroups = { F1: null, F2: null };

// 平台常量：正方形回字形
const W = 58;
const EDGE = 8;
const INNER = W/2 - EDGE;            // 店内边缘(朝中庭)
const DARK = 0xF7F3FA;               // 参考图风：近白淡紫背景
const FLOOR_Y = { F1: 0, F2: 12 };   // 两层楼高差拉大，区分更明显
// 参考图配色：淡粉/淡紫/淡蓝/淡灰的低饱和浅色块，柔和淡雅
const CAT = { 餐饮: 0xF2A9C0, 饮品甜品: 0xB89BE0, 零售: 0x9BB4E8, 服务设施: 0xC7CFDA,
  food: 0xF2A9C0, lift: 0x9BB4E8, esc: 0xF2A9C0, bridge: 0xB89BE0, entrance: 0x6FBF8F };

function init() {
  try {
    if (!window.THREE) { if (el.value) el.value.innerHTML = '<div style="padding:40px;text-align:center;color:#a9b0e0;font-size:14px;">3D 地图库(three.js)未加载，请刷新</div>'; return; }
    scene = new THREE.Scene();
    scene.background = new THREE.Color(DARK);
    scene.fog = new THREE.Fog(DARK, 80, 180);
    camera = new THREE.PerspectiveCamera(50, 1, 0.1, 500);
    camera.position.set(36, 42, 56); camera.lookAt(0, 16, 0);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setClearColor(DARK, 1);
    el.value.appendChild(renderer.domElement);
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.1; controls.target.set(0, 4, 0);
    const amb = new THREE.AmbientLight(0xfdfbff, 0.55); scene.add(amb);
    const dir = new THREE.DirectionalLight(0xffffff, 0.5); dir.position.set(20, 40, 20); scene.add(dir);
    const p = new THREE.PointLight(0xFFFFFF, 0.35, 90); p.position.set(-20, 20, -20); scene.add(p);

    buildFloor('F1'); buildFloor('F2'); buildElevator();
    renderer.domElement.addEventListener('click', onCanvasClick);
    resize(); window.addEventListener('resize', resize); animate(); focusFloor('all');
    drawRoute(props.route);   // 场景就绪后再画初次路线
  } catch (err) {
    console.error('[Floors3D] init 失败:', err);
    if (el.value) el.value.innerHTML = '<div style="padding:40px;text-align:center;color:#a9b0e0;font-size:14px;">3D 地图渲染失败:' + (err && err.message || err) + '</div>';
  }
}

function makeLabel(text) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 80;
  const ctx = c.getContext('2d');
  let size = 40; ctx.font = `bold ${size}px "PingFang SC","Microsoft YaHei",sans-serif`;
  while (ctx.measureText(text).width > 236 && size > 14) { size -= 2; ctx.font = `bold ${size}px "PingFang SC","Microsoft YaHei",sans-serif`; }
  ctx.clearRect(0, 0, 256, 80);
  ctx.fillStyle = 'rgba(255,255,255,0.45)'; ctx.fillRect(0, 0, 256, 80);
  ctx.strokeStyle = 'rgba(150,120,110,0.5)'; ctx.lineWidth = 3; ctx.strokeRect(0, 0, 256, 80);
  ctx.fillStyle = '#5A4B3C'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 128, 42);
  return new THREE.CanvasTexture(c);
}
function catColor(cat) { return CAT[cat] || 0x9CA3AF; }
// 悬浮文字标签
function addLabel(group, text, x, y, z, scale) {
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeLabel(text), depthTest: false, transparent: true }));
  spr.scale.set((scale || 6.4), 1.6, 1);
  spr.position.set(x, y, z);
  group.add(spr);
}

function buildFloor(fl) {
  const floorY = FLOOR_Y[fl];
  const flNum = Number(fl.slice(1));
  const group = new THREE.Group(); group.position.y = floorY;

  // 平台底（浅色 + 中庭走道）
  const base = new THREE.Mesh(new THREE.BoxGeometry(W, 1.0, W), new THREE.MeshStandardMaterial({ color: 0xFDFBF7, transparent: true, opacity: 0.8 }));
  group.add(base);
  const walk = new THREE.Mesh(new THREE.BoxGeometry(W - 2*EDGE, 0.2, W - 2*EDGE), new THREE.MeshStandardMaterial({ color: 0xECEAF3, transparent: true, opacity: 0.55 }));
  walk.position.y = 0.55; group.add(walk);

  // 四角 L 形转角店 + 四边一排小店 + 设施
  buildShops(group, fl, flNum);

  // 中央：美食广场/儿童乐园、扶梯、天桥
  buildCenter(group, fl, flNum);

  floorGroups[fl] = group;   // 存入，便于按楼层显示/隐藏
  scene.add(group);
}

// 四角 L 形转角店：每条边带两端的店不做矩形，改「上下边端点」配「左右边端点」在角处连成 L 形体
function buildShops(group, fl, flNum) {
  // 紧凑对齐回字环：四角 L 形转角占角部(臂长=EDGE)，四边小店紧贴铺满剩余边，店宽加满无缝隙
  const inner = INNER;
  const edged = W/2 - EDGE/2;      // 边带中线(外缘 W/2、内缘 INNER)
  const armLen = EDGE + 4;          // 角臂长(两条腿明显伸出，形成清晰 L 形)，与 buildCorners 一致
  const GAP = 0.6;                  // 边店与角店之间的缝隙
  const span = W - 2*armLen - 2*GAP;  // 边店可用长度(两角臂之间，各留 GAP 缝)
  const list = ringPlan.stores.filter(s => s.floor === flNum);   // 每边 5 家
  const bySide = { 0: [], 1: [], 2: [], 3: [] };
  list.forEach(r => { (bySide[r.side] || []).push(r); });   // 按数据 side 分组，per=5
  Object.keys(bySide).forEach(side => {
    const arr = bySide[side];
    const per = arr.length || 1;
    const bw = (span / per) - 0.5;      // 留一点小缝隙
    arr.forEach((r, i) => {
      // 仅一楼(F1)下边带中央留空给主入口(Main Entrance)，跳过中间那家；二楼同位置店铺保留
      if (side === '2' && flNum === 1 && i === Math.floor(per / 2)) return;
      const c = per === 1 ? 0 : (i / (per - 1) - 0.5) * (span - bw);
      let px, pz, along;
      if (side === '0') { px = c; pz = -edged; along = true; }      // 上
      else if (side === '1') { px = edged; pz = -c; along = false; } // 右
      else if (side === '2') { px = c; pz = edged; along = true; }   // 下
      else { px = -edged; pz = c; along = false; }                   // 左
      const size = along ? [bw, EDGE - 0.4] : [EDGE - 0.4, bw];     // 厚近 EDGE，外/内缘对齐
      placeShop(group, r, px, pz, size, fl, flNum);
    });
  });
  // 四角 L 形转角店（臂对齐同一环）
  buildCorners(group, fl, flNum, edged, armLen);
}

// 四角 L 形转角店：两条臂垂直相交成清晰 L 形（无方块角块），外缘 W/2、内缘 INNER 对齐
function buildCorners(group, fl, flNum, edged, armLen) {
  const cornerNames = (ringPlan.corners && ringPlan.corners[fl]) || ['转角店A', '转角店B', '转角店C', '转角店D'];
  const cornerPos = [[-1,-1],[1,-1],[1,1],[-1,1]];  // 角符号
  const arm = EDGE - 0.4;        // 臂厚(外/内缘对齐)
  const mat = new THREE.MeshLambertMaterial({ color: catColor('餐饮') });
  cornerPos.forEach(([sx, sz], k) => {
    const cx = sx * edged, cz = sz * edged;   // 角中心(环中线)
    // 横向臂(沿 x)：位于角的上/下边带，从角点向内伸 armLen
    const armX = new THREE.Mesh(new THREE.BoxGeometry(armLen, 1.2, arm), mat);
    armX.position.set(sx * (W/2 - armLen/2), 0.9, cz);
    group.add(armX);
    // 纵向臂(沿 z)：位于角的左/右边带，从角点向内伸 armLen
    const armZ = new THREE.Mesh(new THREE.BoxGeometry(arm, 1.2, armLen), mat);
    armZ.position.set(cx, 0.9, sz * (W/2 - armLen/2));
    group.add(armZ);
    // 角店可点击：把两臂合并成一个可点区域，userData 存店名 + 详情
    const info = infoOf(cornerNames[k]);
    const cornerStore = { name: cornerNames[k], floor: fl, floor2: flNum, cat: '零售',
      category: info.category, desc: info.desc, tags: info.tags, floorName: fl, loc: '『' + fl + '』· 转角商铺', id: 'corner_'+flNum+'_'+k };
    armX.userData = { store: cornerStore };
    armZ.userData = { store: cornerStore };
    storeMeshes.push(armX); storeMeshes.push(armZ);
    // 两臂在角点交叉自然形成 L（无独立角块），标签放角部
    addLabel(group, cornerNames[k], cx, 2.2, cz, 4.5);
  });
}

function floorLabelY() { return 2.2; }

// 放一家中段小店：平铺矩形 + 门面
function placeShop(group, r, px, pz, size, fl, flNum) {
  const [sx, sz] = size;
  const isFac = r.fac === 'true' || /卫生间|服务台|信息台/.test(r.name);
  const info = infoOf(r.name);
  const color = isFac ? 0xB8B2A6 : catColor(info.category || '零售');   // 卫生间等设施用灰色；其余按分类上色
  const tile = new THREE.Mesh(new THREE.BoxGeometry(sx, 0.3, sz),
    new THREE.MeshLambertMaterial({ color }));   // Lambert 无自发光，显示本色，避免被光照洗白
  tile.position.set(px, 0.9, pz);
  tile.userData = { store: {
    name: r.name, floor: fl, floor2: flNum,
    cat: r.cat || (isFac ? '设施' : '零售'),
    category: isFac ? '服务设施' : info.category,
    desc: isFac ? '商场服务设施，为顾客提供便利' : info.desc,
    tags: isFac ? ['服务','便民'] : info.tags,
    floorName: fl, loc: '『' + fl + '』· 商铺',
    id: r.name
  } };
  group.add(tile);
  if (!isFac) storeMeshes.push(tile);   // 卫生间等设施不参与点击查店
  addLabel(group, r.name, px, 2.0, pz, Math.min(Math.max(sx, 4), 9));
}

// 中央核心快布局
function buildCenter(group, fl, flNum) {
  const fcMat = new THREE.MeshStandardMaterial({ color: 0xB89BE0, transparent: true, opacity: 0.5 });
  if (fl === 'F1') {
    // 一楼：一侧服务台、另一侧瀑布厅
    const svc = new THREE.Mesh(new THREE.BoxGeometry(11, 0.5, 8), new THREE.MeshStandardMaterial({ color: 0xC7CFDA, transparent: true, opacity: 0.5 }));
    svc.position.set(-9, 0.6, -1); group.add(svc);
    addLabel(group, '服务台', -9, 1.6, -1, 5.2);
    const falls = new THREE.Mesh(new THREE.BoxGeometry(11, 0.5, 8), fcMat);
    falls.position.set(9, 0.6, -1); group.add(falls);
    addLabel(group, '瀑布厅', 9, 1.6, -1, 5.2);
  } else {
    // 二楼：一侧儿童乐园、另一侧美食广场
    const kid = new THREE.Mesh(new THREE.BoxGeometry(11, 0.5, 8), new THREE.MeshStandardMaterial({ color: 0x9BD5AB, transparent: true, opacity: 0.4 }));
    kid.position.set(-9, 0.6, -1); group.add(kid);
    addLabel(group, '儿童乐园', -9, 1.6, -1, 5.2);
    const fc2 = new THREE.Mesh(new THREE.BoxGeometry(11, 0.5, 8), new THREE.MeshStandardMaterial({ color: 0xF2A9C0, transparent: true, opacity: 0.5 }));
    fc2.position.set(9, 0.6, -1); group.add(fc2);
    addLabel(group, '美食广场', 9, 1.6, -1, 5.2);
  }
  // 平铺的电梯（贴本层地面，看哪层都是平的）
  // 电梯平台：中庭中央（青色，平铺）；扶梯为跨层斜梯(见 buildElevator)，这里不再平铺重复
  const lift = new THREE.Mesh(new THREE.BoxGeometry(6, 0.25, 6), new THREE.MeshStandardMaterial({ color: 0x9BB4E8, emissive: 0x9BB4E8, emissiveIntensity: 0.25 }));
  lift.position.set(0, 0.7, 0); group.add(lift);
  addLabel(group, '电梯', 0, 1.5, 0, 4);

  // 主入口(下边中央,F1 留空处)：贴地绿色块 + 标签
  if (fl === 'F1') {
    const ent = new THREE.Mesh(new THREE.BoxGeometry(4, 0.25, 2), new THREE.MeshStandardMaterial({ color: 0x6FBF8F, emissive: 0x6FBF8F, emissiveIntensity: 0.25 }));
    ent.position.set(0, 0.7, INNER + 0.5); group.add(ent);
    addLabel(group, '主入口', 0, 1.5, INNER + 0.5, 4);
  }
}

// 跨层扶梯：剪刀式，能真正从 1F 上到 2F（两条斜梯，梯口在两端错开，可循环使用）
function buildElevator() {
  const escH = FLOOR_Y.F2;              // 高差 8
  const xSpan = 16;                     // 沿 x 升降跨度(更平缓)
  const angle = Math.atan2(escH, xSpan);
  const escLen = Math.hypot(escH, xSpan);
  const matUp = new THREE.MeshStandardMaterial({ color: 0xEF4444, emissive: 0xEF4444, emissiveIntensity: 0.3 });
  const matDn = new THREE.MeshStandardMaterial({ color: 0x10B981, emissive: 0x10B981, emissiveIntensity: 0.3 });
  // 跨层扶梯整体移到中庭靠 z- 一侧（远离主入口/大门口），沿 x 方向倾斜跨层
  const zA = -9.5, zB = -13;             // 两条梯 z 位置，平行并排错开成 "//"
  // 上行梯(1F→2F)：x- 端低(1F)、x+ 端高(2F)
  const up = new THREE.Mesh(new THREE.BoxGeometry(escLen, 1.8, 3), matUp);
  up.position.set(0, escH/2, zA);
  up.rotation.z = angle;
  scene.add(up);
  // 下行梯(2F→1F)：同样方向(与上行梯平行同向)，两梯形成 "//" 而非交叉 X
  const dn = new THREE.Mesh(new THREE.BoxGeometry(escLen, 1.8, 3), matDn);
  dn.position.set(0, escH/2, zB);
  dn.rotation.z = angle;                 // 同向，平行并排
  scene.add(dn);
  // 梯口标签(每层在 x 两端)
  addLabel(scene, '↑上', -xSpan/2, FLOOR_Y.F1 + 0.8, zA, 3);
  addLabel(scene, '↑上', xSpan/2, FLOOR_Y.F2 + 0.8, zA, 3);
  addLabel(scene, '↓下', -xSpan/2, FLOOR_Y.F1 + 0.8, zB, 3);
  addLabel(scene, '↓下', xSpan/2, FLOOR_Y.F2 + 0.8, zB, 3);
}

function onCanvasClick(e) {
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(((e.clientX - rect.left)/rect.width)*2-1, -((e.clientY - rect.top)/rect.height)*2+1);
  const ray = new THREE.Raycaster(); ray.setFromCamera(mouse, camera);
  const hits = ray.intersectObjects(storeMeshes);
  if (hits.length) emit('select', hits[0].object.userData.store);
}

function focusFloor(fl) {
  curFloor.value = fl;
  // 按模式显示/隐藏楼层
  if (floorGroups.F1) floorGroups.F1.visible = (fl === 'all' || fl === 'F1');
  if (floorGroups.F2) floorGroups.F2.visible = (fl === 'all' || fl === 'F2');
  // 相机聚焦
  if (fl === 'all') {
    controls.target.set(0, (FLOOR_Y.F1 + FLOOR_Y.F2) / 2, 0);
    camera.position.set(44, 30, 60);
  } else {
    controls.target.set(0, FLOOR_Y[fl], 0);
    camera.position.set(33, FLOOR_Y[fl] + 26, 48);
  }
  emit('floorschanged', fl);
}
function resize() { const w = el.value.clientWidth||800, h = el.value.clientHeight||500; camera.aspect = w/h; camera.updateProjectionMatrix(); renderer.setSize(w,h); }
function animate() { raf = requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }

// 路线：按店名在 oakwood 找精确坐标
function drawRoute(route) {
  if (!scene) return;   // 场景还没初始化（onMounted init 之前），跳过，避免 scene.add 报错
  clearRoute();
  if (!route || !route.stops || !route.stops.length) return;
  const mat = new THREE.LineBasicMaterial({ color: 0x2BB673 });   // 参考图路线绿色
  route.stops.forEach((s, i) => {
    if (i >= route.stops.length - 1) return;
    const b = route.stops[i + 1];
    const y = FLOOR_Y[s.floor] + 1.2;
    const geom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(s.x, y, s.z), new THREE.Vector3(b.x, y, b.z)]);
    scene.add(new THREE.Line(geom, mat));
  });
}
function clearRoute() { routeLines.forEach(l => scene.remove(l)); routeLines = []; }

onMounted(init);
onBeforeUnmount(() => { if (raf) cancelAnimationFrame(raf); window.removeEventListener('resize', resize); if (renderer) renderer.dispose(); });
watch(() => props.route, drawRoute, { immediate: true });
defineExpose({ focusFloor, drawRoute });
</script>

<template>
  <div class="f3d">
    <div class="f3d-canvas" ref="el"></div>
    <div class="f3d-floors">
      <span class="f3d-floor" :class="{ active: curFloor === 'all' }" @click="focusFloor('all')">全部</span>
      <span class="f3d-floor" :class="{ active: curFloor === 'F2' }" @click="focusFloor('F2')">2F</span>
      <span class="f3d-floor" :class="{ active: curFloor === 'F1' }" @click="focusFloor('F1')">1F</span>
    </div>
    <div class="f3d-hint">🖱️ 拖拽旋转 · 滚轮缩放 · 点击店铺查询</div>
  </div>
</template>

<style scoped>
.f3d { position: relative; width: 100%; background: #F7F3FA; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 24px rgba(120,110,140,0.14); }
.f3d-canvas { width: 100%; height: 480px; }
.f3d-floors { position: absolute; top: 12px; left: 12px; display: flex; flex-direction: column; gap: 6px; }
.f3d-floor { width: 34px; height: 30px; border-radius: 8px; background: rgba(0,0,0,0.04); color: #7A6E8C; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; cursor: pointer; }
.f3d-floor.active { background: linear-gradient(135deg, #C9B6E8, #C5D0E8); color: #3A3550; }
.f3d-hint { position: absolute; bottom: 10px; width: 100%; text-align: center; color: rgba(122,110,140,0.7); font-size: 12px; pointer-events: none; }
</style>
