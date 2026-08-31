<script setup>
import { onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { queueState, stopQueueWatch } from './store/queue';
const route = useRoute();
const router = useRouter();
onBeforeUnmount(() => stopQueueWatch());

const tabs = [
  { path: '/home', label: '首页', icon: '🏠' },
  { path: '/chat', label: '对话', icon: '💬' },
  { path: '/map', label: '规划', icon: '🗺️' },
  { path: '/profile', label: '我的', icon: '👤' }
];

const showTabs = () => !!route.meta.tab && (localStorage.getItem('mall_role') || 'visitor') === 'visitor';
</script>

<template>
  <div class="app-shell">
    <!-- 顶部商场信息栏（登录后页面统一显示，登录页除外） -->
    <header v-if="route.path !== '/login'" class="mall-header">
      <div v-if="!showTabs()" class="mall-back" @click="router.back()">←</div>
      <div v-else class="mall-logo">🛍️</div>
      <div class="mall-info">
        <div class="mall-name">星河里 · 购物中心</div>
        <div class="mall-addr">上海市黄浦区南京东路 168 号</div>
      </div>
    </header>

    <!-- 全局到号提醒横幅（跨页面：确认后跳地图仍提醒） -->
    <transition name="fade">
      <div v-if="queueState.notices.length" class="queue-toast">
        <div v-for="n in queueState.notices" :key="n.id" class="qt-item">
          <span class="qt-text">{{ n.text }}</span>
          <span class="qt-close" @click="queueState.notices = queueState.notices.filter(x => x.id !== n.id)">×</span>
        </div>
      </div>
    </transition>

    <main class="app-main" :class="{ 'has-tabs': showTabs(), 'has-header': route.path !== '/login' }">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 底部 tab（仅对话/地图/我的显示） -->
    <nav v-if="showTabs()" class="tabbar">
      <div v-for="t in tabs" :key="t.path" class="tab"
           :class="{ active: route.path === t.path }" @click="router.push(t.path)">
        <span class="tab-icon">{{ t.icon }}</span>
        <span class="tab-label">{{ t.label }}</span>
      </div>
    </nav>
  </div>
</template>

<style scoped>
.mall-header {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 18px;
  background: linear-gradient(135deg, #7C3AED, #06B6D4);
  color: #fff; flex-shrink: 0;
}
.mall-logo {
  width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0;
  background: rgba(255,255,255,0.18); display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.mall-back {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0; cursor: pointer;
  background: rgba(255,255,255,0.18); color: #fff; font-size: 20px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.mall-info { display: flex; flex-direction: column; min-width: 0; }
.mall-name { font-size: 16px; font-weight: 800; letter-spacing: 0.5px; }
.mall-addr { font-size: 11px; color: rgba(255,255,255,0.85); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-toast { position: sticky; top: 0; z-index: 80; display: flex; flex-direction: column; gap: 8px; padding: 10px 14px; background: #ecfdf5; border-bottom: 1px solid #a7f3d0; }
.qt-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; background: #fff; border: 1px solid #a7f3d0; border-radius: 12px; padding: 10px 14px; font-size: 14px; color: #047857; box-shadow: 0 4px 14px rgba(16,185,129,0.12); }
.qt-text { flex: 1; }
.qt-close { font-size: 18px; color: #9CA3AF; cursor: pointer; padding: 0 4px; }
.tabbar {
  display: flex; border-top: 1px solid var(--border); background: #fff;
  padding-bottom: env(safe-area-inset-bottom); height: 60px; flex-shrink: 0;
}
.tab {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #9CA3AF; cursor: pointer; font-size: 12px;
}
.tab.active { color: var(--primary); }
.tab-icon { font-size: 20px; line-height: 22px; margin-bottom: 2px; }
</style>
