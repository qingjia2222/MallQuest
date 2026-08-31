<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';

// 3D 楼层导览（three.js r128，本地引入）—— 后端店铺主数据 + 走廊路由
const props = defineProps({ route: { type: Object, default: null }, stores: { type: Array, default: () => [] } });
const emit = defineEmits(['select', 'floorschanged']);

const el = ref(null);
const floors = ['F1', 'F2'];
const curFloor = ref('all');       // 'all' | 'F1' | 'F2'

let scene, camera, renderer, controls;
let raf;
let storeMeshes = [];
let routeLines = [];
let routeMarker = null;
let routeAnimation = null;
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

  // 店铺只读后端主数据；视觉模型不再维护另一套商户名称。
  buildCanonicalShops(group, fl, flNum);

  // 中央公共区域只承担视觉分区，不伪装成可点击店铺。
  buildCenter(group, fl, flNum);

  floorGroups[fl] = group;   // 存入，便于按楼层显示/隐藏
  scene.add(group);
}

function graphX(x) { return ((Number(x || 500) - 500) / 1000) * 50; }
function graphZ(y) { return ((Number(y || 380) - 380) / 760) * 42; }
function categoryColor(category) {
  const value = String(category || '');
  if (/餐|菜|轻食/.test(value)) return CAT['餐饮'];
  if (/咖啡|茶|奶|甜品|烘焙/.test(value)) return CAT['饮品甜品'];
  if (/服务/.test(value)) return CAT['服务设施'];
  return CAT['零售'];
}
function buildCanonicalShops(group, fl, flNum) {
  (props.stores || []).filter(s => Number(s.floor) === flNum).forEach(store => {
    const px = graphX(store.pos_x), pz = graphZ(store.pos_y);
    const tile = new THREE.Mesh(new THREE.BoxGeometry(5.4, 1.3, 5.2), new THREE.MeshLambertMaterial({ color: categoryColor(store.category) }));
    tile.position.set(px, 1.1, pz);
    tile.userData = { store: { ...store, floor: fl, floor2: flNum, floorName: fl, loc: `『${fl}』· 商铺`, tags: String(store.service_tags || store.tags || '').split(',').filter(Boolean), desc: store.service_tags || '商场数据库认证店铺' } };
    group.add(tile); storeMeshes.push(tile); addLabel(group, store.name, px, 2.35, pz, 5.8);
  });
}

// 中央保持开放中庭。服务台等实体均由后端店铺主数据定位，路线只走走廊。
function buildCenter(group, fl) {
  // 主入口(下边中央,F1 留空处)：贴地绿色块 + 标签
  if (fl === 'F1') {
    const ent = new THREE.Mesh(new THREE.BoxGeometry(4, 0.25, 2), new THREE.MeshStandardMaterial({ color: 0x6FBF8F, emissive: 0x6FBF8F, emissiveIntensity: 0.25 }));
    ent.position.set(0, 0.7, INNER + 0.5); group.add(ent);
    addLabel(group, '主入口', 0, 1.5, INNER + 0.5, 4);
  }
}

// 跨层扶梯：剪刀式，能真正从 1F 上到 2F（两条斜梯，梯口在两端错开，可循环使用）
function buildElevator() {
  // 后端 route graph 的固定换层节点 f1_c7/f2_c7：红点只在此处垂直乘电梯换层。
  const x = graphX(520), z = graphZ(520);
  const shaft = new THREE.Mesh(new THREE.BoxGeometry(4.6, FLOOR_Y.F2 + 2.4, 4.6), new THREE.MeshStandardMaterial({ color: 0x22B8C7, transparent: true, opacity: 0.42, emissive: 0x22B8C7, emissiveIntensity: 0.16 }));
  shaft.position.set(x, FLOOR_Y.F2 / 2 + 0.8, z); scene.add(shaft);
  addLabel(scene, '电梯 1F', x, FLOOR_Y.F1 + 2.4, z, 4.4);
  addLabel(scene, '电梯 2F', x, FLOOR_Y.F2 + 2.4, z, 4.4);
  // 扶梯上下口分别接入两层走廊，斜坡本体与 escalator 路由边完全重合。
  const lowX=graphX(720),highX=graphX(520),esZ=graphZ(320),dx=highX-lowX,dy=FLOOR_Y.F2-FLOOR_Y.F1;
  const escalator=new THREE.Mesh(new THREE.BoxGeometry(Math.hypot(dx,dy),0.9,2.4),new THREE.MeshStandardMaterial({color:0xF97360,emissive:0xF97360,emissiveIntensity:0.18}));
  escalator.position.set((lowX+highX)/2,FLOOR_Y.F2/2+0.9,esZ);escalator.rotation.z=Math.atan2(dy,dx);scene.add(escalator);
  addLabel(scene,'扶梯 1F',lowX,FLOOR_Y.F1+2.2,esZ,4.2);addLabel(scene,'扶梯 2F',highX,FLOOR_Y.F2+2.2,esZ,4.2);
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

// 路线只消费后端 route graph 坐标，保证与 corridor_only 路网一致。
function drawRoute(route) {
  if (!scene) return;   // 场景还没初始化（onMounted init 之前），跳过，避免 scene.add 报错
  clearRoute();
  if (!route || !route.stops || !route.stops.length) return;
  const mat = new THREE.LineBasicMaterial({ color: 0x2BB673 });   // 参考图路线绿色
  route.stops.forEach((s, i) => {
    if (i >= route.stops.length - 1) return;
    const b = route.stops[i + 1];
    const y1 = FLOOR_Y[s.floor] + 1.2, y2 = FLOOR_Y[b.floor] + 1.2;
    const geom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(s.x, y1, s.z), new THREE.Vector3(b.x, y2, b.z)]);
    const line = new THREE.Line(geom, mat);
    scene.add(line); routeLines.push(line);
  });
  if (route.stops.length > 1) animateRoute(route.stops);
}
function animateRoute(stops) {
  if (routeAnimation) cancelAnimationFrame(routeAnimation);
  const markerMat = new THREE.MeshStandardMaterial({ color: 0xEF4444, emissive: 0xEF4444, emissiveIntensity: 0.8 });
  routeMarker = new THREE.Mesh(new THREE.SphereGeometry(0.75, 20, 20), markerMat);
  scene.add(routeMarker);
  let segment = 0; let started = performance.now(); const duration = 1200;
  const step = now => {
    const a = stops[segment], b = stops[segment + 1];
    const t = Math.min(1, (now - started) / duration);
    const smooth = t * t * (3 - 2 * t);
    routeMarker.position.set(a.x + (b.x-a.x)*smooth, FLOOR_Y[a.floor] + 1.8 + ((FLOOR_Y[b.floor]-FLOOR_Y[a.floor])*smooth), a.z + (b.z-a.z)*smooth);
    if (t >= 1) {
      if (segment < stops.length - 2) { segment += 1; started = now; routeAnimation = requestAnimationFrame(step); }
      return;
    }
    routeAnimation = requestAnimationFrame(step);
  };
  routeAnimation = requestAnimationFrame(step);
}
function clearRoute() {
  if (routeAnimation) cancelAnimationFrame(routeAnimation);
  routeAnimation = null;
  routeLines.forEach(l => { scene.remove(l); if (l.geometry) l.geometry.dispose(); }); routeLines = [];
  if (routeMarker) { scene.remove(routeMarker); if (routeMarker.geometry) routeMarker.geometry.dispose(); routeMarker = null; }
}
function replayRoute() { drawRoute(props.route); }

onMounted(init);
onBeforeUnmount(() => { clearRoute(); if (raf) cancelAnimationFrame(raf); window.removeEventListener('resize', resize); if (renderer) renderer.dispose(); });
watch(() => props.route, drawRoute, { immediate: true });
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
    <button v-if="route && route.stops && route.stops.length > 1" class="f3d-replay" @click="replayRoute">重播路线</button>
    <div class="f3d-hint">🖱️ 拖拽旋转 · 滚轮缩放 · 点击店铺查询</div>
  </div>
</template>

<style scoped>
.f3d { position: relative; width: 100%; background: #F7F3FA; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 24px rgba(120,110,140,0.14); }
.f3d-canvas { width: 100%; height: 480px; }
.f3d-floors { position: absolute; top: 12px; left: 12px; display: flex; flex-direction: column; gap: 6px; }
.f3d-floor { width: 34px; height: 30px; border-radius: 8px; background: rgba(0,0,0,0.04); color: #7A6E8C; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; cursor: pointer; }
.f3d-floor.active { background: linear-gradient(135deg, #C9B6E8, #C5D0E8); color: #3A3550; }
.f3d-replay { position:absolute;right:12px;top:12px;border:1px solid #ded7e8;border-radius:18px;background:rgba(255,255,255,.88);color:#665b78;padding:7px 13px;cursor:pointer;box-shadow:0 4px 12px rgba(120,110,140,.12); }
.f3d-hint { position: absolute; bottom: 10px; width: 100%; text-align: center; color: rgba(122,110,140,0.7); font-size: 12px; pointer-events: none; }
</style>
