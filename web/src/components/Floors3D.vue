<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import ringPlan from '../store/mall_ring.json';
import storeInfo from '../store/store_info.json';

// 取店铺详情(分类/简介/标签)，找不到给默认
function infoOf(name) {
  return storeInfo[name] || { category: '零售', desc: '品类丰富的优质店铺，值得一逛', tags: ['购物', '零售'] };
}

// 3D 楼层导览（three.js r128，本地引入）—— 回字形布局 + 四角 L 形转角店
const props = defineProps({ route: { type: Object, default: null }, navigate: { type: Object, default: null } });
const emit = defineEmits(['select', 'floorschanged']);

const el = ref(null);
const floors = ['F1', 'F2'];
const curFloor = ref('all');       // 'all' | 'F1' | 'F2'

let scene, camera, renderer, controls;
let raf;
let storeMeshes = [];
let routeLines = [];
let navLines = [];
let routeMarker = null;
let animationPoints = [];
let animationStartedAt = 0;
let animationDuration = 6500;
let storePositions = {};
let mainEntrance = null;
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
    if (props.navigate) drawNav(props.navigate);   // 场景就绪后再画导航
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
    // 转角店的导航终点放在朝中庭的内角门口，不把路线画进 L 形店体中心。
    storePositions[cornerNames[k]] = {
      x: cx, z: cz, floor: flNum,
      entrance: { x: sx * INNER, z: sz * INNER, floor: flNum }
    };
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
    recommend: isFac ? [] : (info.recommend || []),
    now_showing: info.now_showing || [],
    hero: isFac ? '🛎️' : (info.hero || '🏬'),
    open_status: (info.open_status || 'open'),
    queue_minutes: info.queue_minutes ?? 0,
    seats_available: info.seats_available ?? 0,
    floorName: fl, loc: '『' + fl + '』· 商铺',
    id: r.name
  } };
  group.add(tile);
  if (!isFac) storeMeshes.push(tile);   // 卫生间等设施不参与点击查店
  const side = Number(r.side);
  const entrance = side === 0 ? { x: px, z: -INNER, floor: flNum }
    : side === 1 ? { x: INNER, z: pz, floor: flNum }
      : side === 2 ? { x: px, z: INNER, floor: flNum }
        : { x: -INNER, z: pz, floor: flNum };
  storePositions[r.name] = { x: px, z: pz, floor: flNum, entrance };
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
    mainEntrance = { x: 0, z: INNER + 0.5, floor: 1 };
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
  [...routeLines, ...navLines].forEach((m) => { const f = m.userData && m.userData.floor; m.visible = !f || f === 'all' || fl === 'all' || ('F' + f) === fl; });
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
function animate(now) {
  raf = requestAnimationFrame(animate);
  controls.update();
  updateMarker(now || performance.now());
  renderer.render(scene, camera);
}

function floorNumber(value) {
  const parsed = Number(String(value == null ? 1 : value).replace(/^F/i, ''));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}
function worldPoint(point) {
  const floor = floorNumber(point.floor);
  return new THREE.Vector3(point.x, FLOOR_Y['F' + floor] + 1.8, point.z);
}
function setAnimationPath(points) {
  animationPoints = [];
  for (const point of points || []) {
    const next = worldPoint(point);
    if (!animationPoints.length || animationPoints[animationPoints.length - 1].distanceTo(next) > 0.05) animationPoints.push(next);
  }
  if (!routeMarker && scene) {
    routeMarker = new THREE.Mesh(
      new THREE.SphereGeometry(0.82, 24, 18),
      new THREE.MeshStandardMaterial({ color: 0xef4444, emissive: 0xef4444, emissiveIntensity: 0.55 })
    );
    scene.add(routeMarker);
  }
  if (routeMarker) routeMarker.visible = animationPoints.length > 1;
  replayRoute();
}
function replayRoute() {
  animationStartedAt = performance.now();
  if (routeMarker && animationPoints.length) {
    routeMarker.position.copy(animationPoints[0]);
    routeMarker.visible = animationPoints.length > 1;
  }
}
function updateMarker(now) {
  if (!routeMarker || !routeMarker.visible || animationPoints.length < 2) return;
  const lengths = [];
  let total = 0;
  for (let i = 0; i < animationPoints.length - 1; i++) {
    total += animationPoints[i].distanceTo(animationPoints[i + 1]);
    lengths.push(total);
  }
  if (!total) return;
  const distance = (((now - animationStartedAt) % animationDuration) / animationDuration) * total;
  let index = lengths.findIndex((value) => value >= distance);
  if (index < 0) index = lengths.length - 1;
  const previous = index === 0 ? 0 : lengths[index - 1];
  const segment = lengths[index] - previous || 1;
  routeMarker.position.lerpVectors(animationPoints[index], animationPoints[index + 1], (distance - previous) / segment);
}

// 用 BoxGeometry 画一段粗线段（比 Line 更清晰）
function segMesh(a, b, color, width) {
  const dx = b.x - a.x, dz = b.z - a.z, len = Math.hypot(dx, dz);
  if (len < 0.01) return null;
  const ang = Math.atan2(dx, dz);
  const floor = floorNumber(a.floor);
  const y = FLOOR_Y['F' + floor] + 1.2;
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width || 0.6, 0.2, len), new THREE.MeshBasicMaterial({ color }));
  mesh.position.set((a.x + b.x) / 2, y, (a.z + b.z) / 2);
  mesh.rotation.y = ang;
  mesh.userData = { floor };
  return mesh;
}
function waypointTexture(index) {
  const canvas = document.createElement('canvas'); canvas.width = 96; canvas.height = 96;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#7C3AED'; ctx.beginPath(); ctx.arc(48,48,38,0,Math.PI*2); ctx.fill();
  ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 7; ctx.stroke();
  ctx.fillStyle = '#ffffff'; ctx.font = 'bold 44px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(index),48,51);
  return new THREE.CanvasTexture(canvas);
}
function addWaypoint(point, index) {
  const floor = floorNumber(point.floor); const group = new THREE.Group();
  const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.72,0.72,0.32,24),new THREE.MeshBasicMaterial({color:0x7C3AED}));
  pin.position.y = 0; group.add(pin);
  const badge = new THREE.Sprite(new THREE.SpriteMaterial({map:waypointTexture(index),depthTest:false,transparent:true}));
  badge.scale.set(2.5,2.5,1); badge.position.y = 2; group.add(badge);
  group.position.set(point.x,FLOOR_Y['F'+floor]+1.35,point.z); group.userData={floor};
  scene.add(group); routeLines.push(group);
}
// 方案路线：每段相邻店铺也用走环路径连接，避免穿过中心核心块/边带店铺（导航时只显示导航线）
function drawRoute(route) {
  clearRoute();
  if (!scene) return;
  if (props.navigate) return;   // 正在导航时不叠加方案路线，避免多条线/废线
  if (!route || !route.stops || route.stops.length < 2) { setAnimationPath([]); return; }
  const PAL = [0x2BB673, 0xE8616E, 0x4EA8E8, 0xE8912B, 0x9C6ADE];   // 绿/红/蓝/橙/紫，按方案顺序分段着色
  const animation = [];
  const addPath = (path, color) => {
    for (let j = 0; j < path.length - 1; j++) {
      const m = segMesh(path[j], path[j + 1], color, 0.6);
      if (m) { scene.add(m); routeLines.push(m); }
    }
    animation.push(...path);
  };
  const resolvedStops = route.stops.map(routePoint);
  resolvedStops.slice(1).forEach((point,index) => addWaypoint(point,index+1));
  for (let i = 0; i < resolvedStops.length - 1; i++) {
    const a = resolvedStops[i];
    const b = resolvedStops[i + 1];
    const color = PAL[i % PAL.length];
    if (a.floor === b.floor) {
      addPath(corridorPath(a, b, a.floor), color);
      continue;
    }
    const useEscalator = route.vertical_mode === 'escalator';
    const low = useEscalator ? { x: -8, z: -9.5, floor: 1 } : { x: 0, z: 0, floor: 1 };
    const high = useEscalator ? { x: 8, z: -9.5, floor: 2 } : { x: 0, z: 0, floor: 2 };
    const fromTransfer = a.floor === 1 ? low : high;
    const toTransfer = b.floor === 2 ? high : low;
    addPath(corridorPath(a, fromTransfer, a.floor), color);
    const transfer = linkMesh(fromTransfer, toTransfer, color, 0.65);
    if (transfer) { scene.add(transfer); routeLines.push(transfer); }
    animation.push(fromTransfer, toTransfer);
    addPath(corridorPath(toTransfer, b, b.floor), color);
  }
  setAnimationPath(animation);
}
function clearRoute() { routeLines.forEach(l => scene.remove(l)); routeLines = []; }
// 竖直电梯段（跨层，中心处）
function vSeg(x, z, f1, f2, color, width) {
  const y1 = FLOOR_Y['F' + f1], y2 = FLOOR_Y['F' + f2];
  const len = Math.abs(y2 - y1);
  if (len < 0.01) return null;
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width || 0.5, len, width || 0.5), new THREE.MeshBasicMaterial({ color }));
  mesh.position.set(x, (y1 + y2) / 2 + 1.2, z);
  mesh.userData = { floor: 'all' };
  return mesh;
}
// 3D 场景坐标适配：业务路线给出店名时，以店门而不是店体中心作为终点。
function routePoint(raw) {
  const floor = floorNumber(raw.floor);
  if (/当前位置|主入口|入口/.test(raw.name || '')) return { x: 0, z: INNER + 0.5, floor: 1 };
  const store = storePositions[raw.name];
  if (store && store.entrance) return { ...store.entrance };
  return { x: Number(raw.x) || 0, z: Number(raw.z) || 0, floor };
}

// 中庭实体占据中央区域，因此路线只在这条矩形走廊骨架上运行。
// RX 位于左右商铺内边界以内，RZ 位于服务台/瀑布厅外侧，所有主干段均不会穿越实体。
const CORRIDOR_RX = INNER - 3;
const CORRIDOR_RZ = 9.5;
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function corridorPort(point) {
  // 直梯位于中心，使用南侧中央通道接入外环；主入口也从同一通道进入。
  if (Math.abs(point.x) < 1 && Math.abs(point.z) < 1) return { x: 0, z: CORRIDOR_RZ, floor: point.floor };
  if (Math.abs(point.x) < 1 && point.z > CORRIDOR_RZ) return { x: 0, z: CORRIDOR_RZ, floor: point.floor };
  const candidates = [
    { x: clamp(point.x, -CORRIDOR_RX, CORRIDOR_RX), z: -CORRIDOR_RZ, floor: point.floor },
    { x: CORRIDOR_RX, z: clamp(point.z, -CORRIDOR_RZ, CORRIDOR_RZ), floor: point.floor },
    { x: clamp(point.x, -CORRIDOR_RX, CORRIDOR_RX), z: CORRIDOR_RZ, floor: point.floor },
    { x: -CORRIDOR_RX, z: clamp(point.z, -CORRIDOR_RZ, CORRIDOR_RZ), floor: point.floor }
  ];
  return candidates.reduce((best, item) => {
    const distance = Math.abs(item.x - point.x) + Math.abs(item.z - point.z);
    return !best || distance < best.distance ? { ...item, distance } : best;
  }, null);
}
function perimeterScalar(point) {
  const rx = CORRIDOR_RX, rz = CORRIDOR_RZ;
  if (Math.abs(point.z + rz) < 0.01) return point.x + rx;
  if (Math.abs(point.x - rx) < 0.01) return 2 * rx + point.z + rz;
  if (Math.abs(point.z - rz) < 0.01) return 2 * rx + 2 * rz + rx - point.x;
  return 4 * rx + 2 * rz + rz - point.z;
}
function perimeterPoint(value, floor) {
  const rx = CORRIDOR_RX, rz = CORRIDOR_RZ, total = 4 * rx + 4 * rz;
  const s = ((value % total) + total) % total;
  if (s <= 2 * rx) return { x: -rx + s, z: -rz, floor };
  if (s <= 2 * rx + 2 * rz) return { x: rx, z: -rz + s - 2 * rx, floor };
  if (s <= 4 * rx + 2 * rz) return { x: rx - (s - 2 * rx - 2 * rz), z: rz, floor };
  return { x: -rx, z: rz - (s - 4 * rx - 2 * rz), floor };
}
function clockwiseArc(from, to, floor) {
  const rx = CORRIDOR_RX, rz = CORRIDOR_RZ, total = 4 * rx + 4 * rz;
  const start = perimeterScalar(from);
  let end = perimeterScalar(to);
  while (end < start) end += total;
  const corners = [2 * rx, 2 * rx + 2 * rz, 4 * rx + 2 * rz, total, total + 2 * rx,
    total + 2 * rx + 2 * rz, total + 4 * rx + 2 * rz];
  return [from, ...corners.filter((s) => s > start + 0.01 && s < end - 0.01).map((s) => perimeterPoint(s, floor)), to];
}
function shortestPerimeter(from, to, floor) {
  const total = 4 * CORRIDOR_RX + 4 * CORRIDOR_RZ;
  const a = perimeterScalar(from), b = perimeterScalar(to);
  const clockwise = (b - a + total) % total;
  if (clockwise <= total - clockwise) return clockwiseArc(from, to, floor);
  return clockwiseArc(to, from, floor).reverse();
}
function appendUnique(path, point) {
  const last = path[path.length - 1];
  if (!last || Math.abs(last.x - point.x) > 0.01 || Math.abs(last.z - point.z) > 0.01 || last.floor !== point.floor) path.push(point);
}
function spur(point, port) {
  const path = [{ ...point }];
  if (Math.abs(point.x - port.x) > 0.01 && Math.abs(point.z - port.z) > 0.01) {
    // 先沿商铺内边界走，再垂直接入主走廊，避免斜线切过转角店。
    path.push({ x: port.x, z: point.z, floor: point.floor });
  }
  path.push({ ...port });
  return path;
}
function corridorPath(s, t, fl) {
  const floor = fl || s.floor;
  const start = { ...s, floor }, end = { ...t, floor };
  const fromPort = corridorPort(start), toPort = corridorPort(end);
  const path = [];
  spur(start, fromPort).forEach((p) => appendUnique(path, p));
  shortestPerimeter(fromPort, toPort, floor).forEach((p) => appendUnique(path, p));
  spur(end, toPort).reverse().forEach((p) => appendUnique(path, p));
  return path;
}
// 跨层斜线段（乘扶梯）：连接两个不同楼层的点，斜向跨层，userData='all' 始终显示
function linkMesh(a, b, color, width) {
  const y1 = FLOOR_Y['F' + a.floor] + 1.2, y2 = FLOOR_Y['F' + b.floor] + 1.2;
  const v1 = new THREE.Vector3(a.x, y1, a.z), v2 = new THREE.Vector3(b.x, y2, b.z);
  const len = v1.distanceTo(v2);
  if (len < 0.01) return null;
  const dir = v2.clone().sub(v1).normalize();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width || 0.6, width || 0.6, len), new THREE.MeshBasicMaterial({ color }));
  mesh.position.copy(v1.clone().add(v2).multiplyScalar(0.5));
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir);
  mesh.userData = { floor: 'all' };
  return mesh;
}
function navSeg(a, b) { const m = segMesh(a, b, 0x219653, 0.7); if (m) { scene.add(m); navLines.push(m); } }
// 导航：1F 店=主入口沿走道到店；2F 店=主入口→1F电梯→电梯升2F→走道到店（一楼二楼都可见）
function drawNav(nav) {
  clearNav();
  if (!scene || !nav || !nav.name) return;
  const target = storePositions[nav.name];
  if (!target) return;
  const animation = [];
  if (target.floor === 1) {
    const p = corridorPath({ x: 0, z: INNER + 0.5, floor: 1 }, target.entrance || target, 1);
    for (let i = 0; i < p.length - 1; i++) navSeg(p[i], p[i + 1]);
    animation.push(...p);
  } else {
    const useEscalator = nav.vertical_mode === 'escalator';
    const LF1 = useEscalator ? { x: -8, z: -9.5, floor: 1 } : { x: 0, z: 0, floor: 1 };
    const LF2 = useEscalator ? { x: 8, z: -9.5, floor: 2 } : { x: 0, z: 0, floor: 2 };
    // 1F：主入口（获得的位置）→ 沿走道走到换层设施
    const p1 = corridorPath({ x: 0, z: INNER + 0.5, floor: 1 }, LF1, 1);
    for (let i = 0; i < p1.length - 1; i++) navSeg(p1[i], p1[i + 1]);
    // 乘直梯或扶梯跨层；两者都只连接已建模的换层设施。
    const lm = linkMesh(LF1, LF2, 0x219653, 0.7);
    if (lm) { scene.add(lm); navLines.push(lm); }
    // 2F：换层设施 → 沿走道 → 店
    const p2 = corridorPath(LF2, target.entrance || target, 2);
    for (let i = 0; i < p2.length - 1; i++) navSeg(p2[i], p2[i + 1]);
    animation.push(...p1, LF2, ...p2);
  }
  setAnimationPath(animation);
  focusFloor('all');   // 导航时地图展示全部楼层，清楚看到电梯上下
}
function clearNav() { navLines.forEach(l => scene.remove(l)); navLines = []; }

onMounted(init);
onBeforeUnmount(() => { if (raf) cancelAnimationFrame(raf); window.removeEventListener('resize', resize); if (renderer) renderer.dispose(); });
watch(() => props.route, drawRoute, { immediate: true });
watch(() => props.navigate, (n) => { if (n) drawNav(n); else { clearNav(); drawRoute(props.route); } }, { immediate: true });
defineExpose({ focusFloor, drawRoute, replayRoute });
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
